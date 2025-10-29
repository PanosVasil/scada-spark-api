# db_async.py
from __future__ import annotations
import os
from pathlib import Path
from typing import AsyncGenerator

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# Load .env from project root
load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

ASYNC_DATABASE_URL = os.getenv("ASYNC_DATABASE_URL")
if not ASYNC_DATABASE_URL:
    raise RuntimeError("ASYNC_DATABASE_URL not set in .env")

engine = create_async_engine(ASYNC_DATABASE_URL, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class Base(DeclarativeBase):
    pass

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session
