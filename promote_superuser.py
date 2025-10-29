# promote_superuser.py — safe CLI promotion tool
import asyncio
from sqlalchemy import select
from db_async import get_async_session
from models_user import User
import models_user_park  # <-- import here so UserParkAccess exists

async def promote(email: str):
    async for session in get_async_session():
        result = await session.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if not user:
            print(f"❌ No user found with email {email}")
            return
        user.is_superuser = True
        await session.commit()
        print(f"✅ {email} promoted to superuser")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python promote_superuser.py <email>")
    else:
        asyncio.run(promote(sys.argv[1]))
