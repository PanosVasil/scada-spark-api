from sqlalchemy import create_engine, text
from dotenv import load_dotenv
from pathlib import Path
import os

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

url = os.getenv("DATABASE_URL")
print("DATABASE_URL:", url)

engine = create_engine(url, pool_pre_ping=True, future=True)
with engine.connect() as conn:
    who = conn.execute(text("SELECT current_user, current_database();")).one()
    print("Connected as:", who)
