import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

import config
from database.database import init_db, SessionLocal
from handlers import start, profile, catch, admin

async def test_routers():
    print("1. Initializing DB...")
    await init_db()
    print("✅ DB ready!")

    print("2. Checking router registrations...")
    print(f"Start router: {start.router.name}")
    print("✅ Routers loaded with 0 syntax errors!")

if __name__ == "__main__":
    asyncio.run(test_routers())
