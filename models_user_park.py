# models_user_park.py
from __future__ import annotations
import uuid
from sqlalchemy import String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from db_async import Base

class UserParkAccess(Base):
    __tablename__ = "user_park_access"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    park_id: Mapped[str] = mapped_column(String(100), nullable=False)

    # Relationships
    user = relationship("User", back_populates="parks")
