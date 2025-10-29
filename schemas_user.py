# schemas_user.py
from __future__ import annotations
from typing import Optional
import uuid
from fastapi_users import schemas

class UserRead(schemas.BaseUser[uuid.UUID]):
    organization_id: Optional[str] = None
    default_park_id: Optional[str] = None

class UserCreate(schemas.BaseUserCreate):
    organization_id: Optional[str] = None
    default_park_id: Optional[str] = None

class UserUpdate(schemas.BaseUserUpdate):
    organization_id: Optional[str] = None
    default_park_id: Optional[str] = None
