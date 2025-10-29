# parks.py — single source of truth via config.json
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, Set, Iterable, List

# Optional: safe slug for fallback park_id if "id" missing
_slug_re = re.compile(r"[^a-z0-9]+")

def slugify(value: str) -> str:
    s = value.strip().lower()
    s = _slug_re.sub("_", s).strip("_")
    return s or "park"

# --- Load from config.json (only source of truth) ---
ROOT_DIR = Path(__file__).resolve().parent
CONFIG_PATH = ROOT_DIR / "config.json"

try:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        _config = json.load(f)
    _plc_config = _config.get("plc_config", [])
except Exception as e:
    raise RuntimeError(f"Failed to load {CONFIG_PATH}: {e}")

# Build PARKS from config.json
# Expect each item to have: id (preferred), name, url
PARKS: Dict[str, Dict[str, str]] = {}
for item in _plc_config:
    name = item.get("name") or ""
    url = item.get("url") or ""
    park_id = item.get("id") or slugify(name)
    if not url:
        # ignore incomplete entries silently (or raise if you prefer)
        continue
    PARKS[park_id] = {"name": name or park_id, "url": url}

# Convenience set
_KNOWN_PARKS: Set[str] = set(PARKS.keys())

def is_valid_park(park_id: str) -> bool:
    return park_id in PARKS

def map_park_ids_to_urls(park_ids: Iterable[str]) -> Set[str]:
    """Return a set of OPC UA URLs for the provided park_ids (unknown ids ignored)."""
    urls: Set[str] = set()
    for pid in park_ids:
        info = PARKS.get(pid)
        if info and info.get("url"):
            urls.add(info["url"])
    return urls

# ---- DB helpers to use when authorizing per-park access ----
# We import here to avoid import cycles at module import time.
from typing import Optional
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

async def user_allowed_park_ids(session: AsyncSession, user) -> Set[str]:
    """
    Return the set of park_ids the user can view/control.
    Uses the UserParkAccess table.
    """
    from models_user_park import UserParkAccess  # local import to avoid circulars
    rows = (await session.execute(
        select(UserParkAccess.park_id).where(UserParkAccess.user_id == user.id)
    )).scalars().all()
    # ensure only park_ids that still exist in config.json are returned
    return {pid for pid in rows if is_valid_park(pid)}

async def user_allowed_urls(session: AsyncSession, user) -> Set[str]:
    """Map the user's allowed park_ids to OPC-UA URLs via config.json."""
    pids = await user_allowed_park_ids(session, user)
    return map_park_ids_to_urls(pids)
