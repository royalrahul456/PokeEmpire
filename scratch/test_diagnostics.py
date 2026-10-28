import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from aiogram import Bot
import config
from database.database import init_db, SessionLocal
from sqlalchemy import text

async def run_diagnostics():
    print("==================================================")
    print("         POKEEMPIRE BOTH BOTS DIAGNOSTICS         ")
    print("==================================================")

    # 1. Database Check
    print("\n[1/3] Testing Database Connection...")
    try:
        await init_db()
        async with SessionLocal() as db:
            res = await db.execute(text("SELECT COUNT(*) FROM users"))
            user_count = res.scalar()
            print(f"  ✅ Database Connected! Total registered users: {user_count}")
    except Exception as e:
        print(f"  ❌ Database Connection Failed: {e}")

    # 2. Main Bot Token Check
    print("\n[2/3] Testing Main Bot Token (@pokeempirebot)...")
    if not config.BOT_TOKEN:
        print("  ❌ BOT_TOKEN is missing in .env")
    else:
        try:
            bot1 = Bot(token=config.BOT_TOKEN)
            me1 = await bot1.get_me()
            print(f"  ✅ Main Bot Verified: @{me1.username} (ID: {me1.id})")
            await bot1.session.close()
        except Exception as e:
            print(f"  ❌ Main Bot Token Failed: {type(e).__name__}: {e}")

    # 3. Games Bot Token Check
    print("\n[3/3] Testing Games Bot Token (@PokeXArenaBot)...")
    if not config.GAMES_BOT_TOKEN:
        print("  ❌ GAMES_BOT_TOKEN is missing in .env")
    else:
        try:
            bot2 = Bot(token=config.GAMES_BOT_TOKEN)
            me2 = await bot2.get_me()
            print(f"  ✅ Games Bot Verified: @{me2.username} (ID: {me2.id})")
            await bot2.session.close()
        except Exception as e:
            print(f"  ❌ Games Bot Token Failed: {type(e).__name__}: {e}")

    print("\n==================================================")

if __name__ == "__main__":
    asyncio.run(run_diagnostics())
