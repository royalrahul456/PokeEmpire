import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import asyncio
from sqlalchemy import select
from database.database import SessionLocal
from database.models import User
from handlers.profile import get_pokedex_data

async def test_cmd_profile_pokedex():
    print("Testing /profile and /pokedex database queries...", flush=True)

    async with SessionLocal() as db:
        # Get first user in database
        stmt = select(User).limit(1)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()

        if not user:
            print("No users found in database to test.", flush=True)
            return

        print(f"Testing for User ID: {user.id} ({user.username or user.nickname})...", flush=True)

        # Test get_pokedex_data
        try:
            text, page, max_page = await get_pokedex_data(user.id, user.nickname or "Trainer", 1, "All", db)
            print(f"✅ get_pokedex_data SUCCESS!")
            print(f"   Page: {page}/{max_page}")
            print(f"   Preview:\n{text[:200]}...")
        except Exception as e:
            import traceback
            print(f"❌ get_pokedex_data FAILED: {e}")
            traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test_cmd_profile_pokedex())
