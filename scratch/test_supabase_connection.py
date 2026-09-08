import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

async def test_conn(password: str):
    url = f"postgresql+asyncpg://postgres:{password}@db.dlxlqrerxplqevvutgsn.supabase.co:5432/postgres"
    print(f"Testing Supabase Direct connection...")
    try:
        engine = create_async_engine(url)
        async with engine.begin() as conn:
            res = await conn.execute(text("SELECT version();"))
            row = res.scalar()
            print(f"✅ Supabase Connection Successful! PostgreSQL Version: {row}")
        await engine.dispose()
        return True
    except Exception as e:
        print(f"❌ Supabase Connection Failed: {e}")
        return False

if __name__ == "__main__":
    if len(sys.argv) > 1:
        pwd = sys.argv[1]
        asyncio.run(test_conn(pwd))
    else:
        print("Please provide password as command line argument.")
