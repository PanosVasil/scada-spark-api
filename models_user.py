# models_user.py
from __future__ import annotations
from typing import Optional, List
import uuid
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from fastapi_users_db_sqlalchemy import SQLAlchemyBaseUserTableUUID
from db_async import Base

class User(SQLAlchemyBaseUserTableUUID, Base):
    __tablename__ = "users"
    organization_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    default_park_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # relationship to parks
    parks: Mapped[List["UserParkAccess"]] = relationship(
        "UserParkAccess",
        back_populates="user",
        cascade="all, delete-orphan",
    )
