# main.py — SCADA Web API + FastAPI-Users v14.x
from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Union
from uuid import UUID

# --- Parks & Access ---
from parks_routes import router as parks_router
from models_user_park import UserParkAccess
from parks import PARKS

# --- FastAPI Core ---
from dotenv import load_dotenv
from fastapi import (
    Body,
    Depends,
    FastAPI,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
    Query,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi_users.exceptions import UserAlreadyExists
from pydantic import BaseModel

# --- OPC UA ---
from opcua import ua, Client
from opcua.ua.uaerrors import UaStatusCodeError

# --- Auth / DB pieces ---
from auth import (
    fastapi_users,
    auth_backend,
    current_user,
    current_superuser,
    get_jwt_strategy,
    get_user_manager,
)
from schemas_user import UserRead, UserCreate, UserUpdate
from models_user import User as DBUser
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from db_async import get_async_session

# ---------------------------------------------------------------------
# CONFIG / ENV
# ---------------------------------------------------------------------
ROOT_DIR = Path(__file__).resolve().parent
load_dotenv(dotenv_path=ROOT_DIR / ".env")

try:
    with open(ROOT_DIR / "config.json", "r", encoding="utf-8") as f:
        config = json.load(f)
    PLC_CONFIG = config["plc_config"]
    COMMON_ROOT_NODE_ID = config["common_root_node_id"]
    BROADCAST_INTERVAL_SECONDS = float(config["broadcast_interval_seconds"])
    PLC_RECONNECT_DELAY_MINUTES = int(config["plc_reconnect_delay_minutes"])
except Exception as e:
    raise RuntimeError(f"Failed to load config.json: {e}")

# ---------------------------------------------------------------------
# APP + LOGGING + CORS
# ---------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(threadName)s - %(levelname)s - %(message)s",
)
logging.getLogger("opcua").setLevel(logging.WARNING)

app = FastAPI(title="SCADA Web API", version="1.0")

# ✅ CORS from .env
_origins_env = os.getenv("CORS_ALLOW_ORIGINS", "")
origins = [o.strip() for o in _origins_env.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins or ["http://127.0.0.1:3000", "http://localhost:3000", "http://127.0.0.1:5173", "http://localhost:5173", "http://127.0.0.1:8080", "http://localhost:8080"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------
# FASTAPI-USERS ROUTERS (v14 compliant)
# ---------------------------------------------------------------------
app.include_router(fastapi_users.get_auth_router(auth_backend), prefix="/auth/jwt", tags=["auth"])
app.include_router(fastapi_users.get_reset_password_router(), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_verify_router(UserRead), prefix="/auth", tags=["auth"])
app.include_router(fastapi_users.get_users_router(UserRead, UserUpdate), prefix="/users", tags=["users"])
app.include_router(parks_router)

# ---------------------------------------------------------------------
# CUSTOM REGISTRATION
# ---------------------------------------------------------------------
@app.post("/auth/register", response_model=UserRead, tags=["auth"])
async def custom_register(
    user_create: UserCreate = Body(...),
    manager=Depends(get_user_manager),
):
    try:
        created_user = await manager.create(user_create)
        return created_user
    except UserAlreadyExists:
        return JSONResponse(status_code=400, content={"detail": "User already exists."})
    except Exception as e:
        logging.error(f"Registration failed: {e}")
        raise HTTPException(status_code=500, detail="Registration failed.")

# ---------------------------------------------------------------------
# MODELS / TYPES
# ---------------------------------------------------------------------
class APICurrentUser(BaseModel):
    id: str
    email: str
    organization_id: Optional[str] = None
    default_park_id: Optional[str] = None
    is_superuser: bool
    is_active: bool

class WriteRequest(BaseModel):
    plc_url: str
    node_name: str
    value: Union[float, List[bool], int, str]

class AdminUserSummary(BaseModel):
    id: UUID
    email: str
    is_superuser: bool
    is_active: bool
    organization_id: Optional[str] = None
    default_park_id: Optional[str] = None

# ---------------------------------------------------------------------
# OPC UA CLIENT
# ---------------------------------------------------------------------
class ConnectionStatus(str, Enum):
    CONNECTED = "CONNECTED"
    CONNECTING = "CONNECTING"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"

class OpcUaClient:
    def __init__(self, url: str, custom_name: str, root_node_id: str):
        self.url = url
        self.name = custom_name
        self.server_name = ""
        self.root_node_id = root_node_id
        self.client: Optional[Client] = None
        self.nodes: Dict[str, Any] = {}
        self.status = ConnectionStatus.DISCONNECTED
        self.last_reconnect_attempt: Optional[datetime] = None

    def _get_readable_nodes(self, node) -> dict:
        nodes_dict: Dict[str, Any] = {}
        try:
            if node.get_node_class() == ua.NodeClass.Variable:
                nodes_dict[node.get_browse_name().Name] = node
        except Exception:
            pass
        try:
            for child in node.get_children():
                nodes_dict.update(self._get_readable_nodes(child))
        except Exception:
            pass
        return nodes_dict

    def connect_and_discover(self) -> bool:
        self.last_reconnect_attempt = datetime.now()
        if self.client:
            try:
                self.client.disconnect()
            except Exception:
                pass
        self.client = Client(self.url, timeout=40)
        self.status = ConnectionStatus.CONNECTING
        self.nodes = {}
        logging.info(f"'{self.name}': 🔄 Connecting...")
        try:
            self.client.connect()
            try:
                self.server_name = self.client.get_node("ns=0;i=2254").get_value() or ""
            except Exception:
                self.server_name = ""
            root_node = self.client.get_node(self.root_node_id)
            self.nodes = self._get_readable_nodes(root_node)
            self.status = ConnectionStatus.CONNECTED
            logging.info(f"{self.name}: ✅ CONNECTED ({len(self.nodes)} nodes)")
            return True
        except Exception as e:
            self.status = ConnectionStatus.DISCONNECTED
            logging.error(f"{self.name}: ❌ Connection error: {e}")
            self.client = None
            return False

    def read_data(self) -> Dict[str, Any]:
        data = {"name": self.name, "status": self.status.value, "url": self.url, "nodes": {}}
        if self.status != ConnectionStatus.CONNECTED or not self.client:
            return data
        try:
            ids = list(self.nodes.values())
            names = list(self.nodes.keys())
            if not ids:
                data["error"] = "No readable nodes."
                return data
            values = self.client.get_values(ids)
            for n, v in zip(names, values):
                data["nodes"][n] = str(v)
        except UaStatusCodeError as e:
            self.status = ConnectionStatus.ERROR
            data["error"] = f"OPC UA read error: {e}"
        except Exception:
            data["error"] = "Temporary read failure."
        return data

# ---------------------------------------------------------------------
# THREADING & BROADCAST LOOP
# ---------------------------------------------------------------------
stop_event = threading.Event()
plc_clients: List[OpcUaClient] = []
active_ws_connections: Dict[str, Set[WebSocket]] = {}
executor = ThreadPoolExecutor(max_workers=max(len(PLC_CONFIG) * 2, 2))

def data_broadcast_loop(loop: asyncio.AbstractEventLoop):
    reconnect_delay = timedelta(minutes=PLC_RECONNECT_DELAY_MINUTES)
    logging.info("Background broadcast started.")
    while not stop_event.is_set():
        try:
            # reconnect any dropped/error clients
            reconnect_list = [
                p for p in plc_clients
                if p.status in (ConnectionStatus.DISCONNECTED, ConnectionStatus.ERROR)
                and (not p.last_reconnect_attempt or (datetime.now() - p.last_reconnect_attempt) > reconnect_delay)
            ]
            if reconnect_list:
                list(executor.map(lambda p: p.connect_and_discover(), reconnect_list))

            # read all data
            all_plc_data = list(executor.map(lambda p: p.read_data(), plc_clients))

            # ✅ Broadcast filtered data to each websocket (wrapped for the UI)
            for user_id, sockets in list(active_ws_connections.items()):
                for ws in sockets:
                    try:
                        allowed = getattr(ws, "allowed_urls", None)
                        visible_data = (
                            [d for d in all_plc_data if d["url"] in allowed]
                            if allowed else all_plc_data
                        )
                        payload = {
                            "type": "telemetry_update",
                            "data": {"plc_clients": visible_data},
                        }
                        asyncio.run_coroutine_threadsafe(ws.send_json(payload), loop)
                    except Exception as e:
                        logging.error(f"WebSocket send error for {user_id}: {e}")

            # sleep until next tick
            for _ in range(int(BROADCAST_INTERVAL_SECONDS)):
                if stop_event.is_set():
                    break
                time.sleep(1)
        except Exception as e:
            logging.error(f"Broadcast error: {e}")
            time.sleep(5)
    logging.info("Broadcast stopped.")

# ---------------------------------------------------------------------
# LIFESPAN
# ---------------------------------------------------------------------
@app.on_event("startup")
async def on_startup():
    for cfg in PLC_CONFIG:
        plc_clients.append(OpcUaClient(cfg["url"], cfg["name"], COMMON_ROOT_NODE_ID))
    loop = asyncio.get_running_loop()
    threading.Thread(target=data_broadcast_loop, args=(loop,), daemon=True).start()
    logging.info("Startup complete.")

@app.on_event("shutdown")
async def on_shutdown():
    logging.info("Shutting down...")
    stop_event.set()
    executor.shutdown(wait=False, cancel_futures=True)
    for p in plc_clients:
        try:
            if p.client:
                p.client.disconnect()
        except Exception:
            pass
    logging.info("Shutdown complete.")

# ---------------------------------------------------------------------
# JWT HELPERS
# ---------------------------------------------------------------------
jwt_strategy = get_jwt_strategy()

async def get_user_by_id(user_id: str) -> Optional[DBUser]:
    # Explicitly cast string to UUID (Postgres-safe)
    try:
        uuid_id = UUID(user_id)
    except Exception:
        return None
    async for session in get_async_session():
        res = await session.execute(select(DBUser).where(DBUser.id == uuid_id))
        return res.scalar_one_or_none()

async def user_from_token(token: str) -> Optional[DBUser]:
    try:
        payload = await jwt_strategy.read_token(token, None)
        return await get_user_by_id(payload.get("sub"))
    except Exception:
        return None

# ---------------------------------------------------------------------
# ROUTES
# ---------------------------------------------------------------------
@app.get("/me", response_model=APICurrentUser)
async def who_am_i(user: DBUser = Depends(current_user)):
    return APICurrentUser(
        id=str(user.id),
        email=user.email,
        organization_id=user.organization_id,
        default_park_id=user.default_park_id,
        is_superuser=user.is_superuser,
        is_active=user.is_active,
    )

@app.get("/admin/ping")
async def admin_ping(_: DBUser = Depends(current_superuser)):
    return {"ok": True}

@app.get("/admin/users", response_model=List[AdminUserSummary], tags=["admin"])
async def list_users(
    q: Optional[str] = Query(None, description="Search by email (contains, case-insensitive)"),
    is_superuser: Optional[bool] = Query(None),
    is_active: Optional[bool] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    _: DBUser = Depends(current_superuser),
    session: AsyncSession = Depends(get_async_session),
):
    stmt = select(DBUser)
    if q:
        like = f"%{q}%"
        stmt = stmt.where(func.lower(DBUser.email).like(func.lower(like)))
    if is_superuser is not None:
        stmt = stmt.where(DBUser.is_superuser == is_superuser)
    if is_active is not None:
        stmt = stmt.where(DBUser.is_active == is_active)
    stmt = stmt.order_by(DBUser.email).limit(limit).offset(offset)

    result = await session.execute(stmt)
    users = result.scalars().all()

    return [
        AdminUserSummary(
            id=u.id,
            email=u.email,
            is_superuser=bool(u.is_superuser),
            is_active=bool(u.is_active),
            organization_id=u.organization_id,
            default_park_id=u.default_park_id,
        )
        for u in users
    ]

@app.post("/write_value")
async def write_plc_value(req: WriteRequest, user: DBUser = Depends(current_user)):
    if not user.is_superuser:
        raise HTTPException(403, "Write requires superuser privileges.")
    target = next((p for p in plc_clients if p.url == req.plc_url), None)
    if not target or target.status != ConnectionStatus.CONNECTED:
        raise HTTPException(404, "PLC not connected.")
    node = target.nodes.get(req.node_name)
    if not node:
        raise HTTPException(404, f"Node '{req.node_name}' not found.")
    try:
        vt = node.get_data_type_as_variant_type()
        v = int(req.value) if isinstance(req.value, float) else req.value
        dv = ua.DataValue(ua.Variant(v, vt))
        node.set_attribute(ua.AttributeIds.Value, dv)
        logging.info(f"Write {v} to '{req.node_name}' on {target.name}")
        return {"status": "success"}
    except Exception as e:
        logging.error(f"Write failed: {e}")
        raise HTTPException(500, f"Write failed: {e}")

# ---------------------------------------------------------------------
# DATA ACCESS CONTROL
# ---------------------------------------------------------------------
@app.get("/data")
async def get_initial_data(
    user: DBUser = Depends(current_user),
    session: AsyncSession = Depends(get_async_session),
):
    """
    Return initial telemetry in the same shape the frontend expects:
    { "plc_clients": [...] }
    """
    if not plc_clients:
        return {"plc_clients": []}

    if user.is_superuser:
        allowed = {cfg["url"] for cfg in PLC_CONFIG}
    else:
        res = await session.execute(select(UserParkAccess.park_id).where(UserParkAccess.user_id == user.id))
        park_ids = [r[0] for r in res.all()]
        allowed = {PARKS[p]["url"] for p in park_ids if p in PARKS}

    visible_clients = [p for p in plc_clients if p.url in allowed]
    data_list = list(executor.map(lambda p: p.read_data(), visible_clients))
    return {"plc_clients": data_list}

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    """
    Robust WebSocket endpoint:
    - Accepts token from query (?token=), Sec-WebSocket-Protocol, or Authorization header.
    - Keeps connection alive and logs detailed reason for closures.
    """
    proto = websocket.headers.get("Sec-WebSocket-Protocol") or ""
    auth_header = websocket.headers.get("Authorization")
    token = None

    # Extract token
    try:
        if proto.startswith("bearer,"):
            token = proto.split(",", 1)[1].strip()
            await websocket.accept(subprotocol=proto)
        elif "token" in websocket.query_params:
            token = websocket.query_params["token"]
            await websocket.accept()
        elif auth_header and auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1]
            await websocket.accept()
        else:
            await websocket.accept()
    except Exception as e:
        logging.error(f"WS accept error: {e}")
        return

    if not token:
        logging.warning("WS: missing token → closing.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user = await user_from_token(token)
    if not user or not user.is_active:
        logging.warning("WS: invalid or inactive token → closing.")
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    # Allowed URLs for user
    async for session in get_async_session():
        if user.is_superuser:
            allowed_urls = {cfg["url"] for cfg in PLC_CONFIG}
        else:
            res = await session.execute(
                select(UserParkAccess.park_id).where(UserParkAccess.user_id == user.id)
            )
            park_ids = [r[0] for r in res.all()]
            allowed_urls = {PARKS[p]["url"] for p in park_ids if p in PARKS}

    websocket.allowed_urls = allowed_urls
    user_key = str(user.id)
    active_ws_connections.setdefault(user_key, set()).add(websocket)
    logging.info(f"✅ WS connected: {user.email}")

    try:
        while True:
            await asyncio.sleep(30)
            try:
                await websocket.send_json({"type": "keepalive"})
            except Exception as e:
                logging.warning(f"WS send error ({user.email}): {e}")
                break
    except WebSocketDisconnect:
        logging.info(f"⚠️ WS disconnected: {user.email}")
    finally:
        conns = active_ws_connections.get(user_key)
        if conns:
            conns.discard(websocket)
            if not conns:
                active_ws_connections.pop(user_key, None)
        logging.info(f"🔌 WS cleanup complete for {user.email}")

