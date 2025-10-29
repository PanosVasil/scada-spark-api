# init_db_async.py
import asyncio
from db_async import engine, Base
from models_user import User
from models_user_park import UserParkAccess

async def main():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ Tables created.")

if __name__ == "__main__":
    asyncio.run(main())
