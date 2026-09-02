import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

import config
from database.database import SessionLocal, init_db

async def test_boot():
    print("1. Checking config...")
    print(f"BOT_TOKEN set: {bool(config.BOT_TOKEN)}")
    print(f"ADMIN_IDS: {config.ADMIN_IDS}")
    print(f"DATABASE_URL: {config.DATABASE_URL[:40]}...")

    print("\n2. Initializing database connection...")
    try:
        await init_db()
        print("✅ Database initialized successfully!")
    except Exception as e:
        print(f"❌ Database error: {e}")
        return

    print("\n3. Testing telegram ApplicationBuilder...")
    try:
        from telegram.ext import ApplicationBuilder
        app = ApplicationBuilder().token(config.BOT_TOKEN).build()
        await app.initialize()
        bot_info = await app.bot.get_me()
        print(f"✅ Bot connected successfully as @{bot_info.username} ({bot_info.first_name})!")
        await app.shutdown()
    except Exception as e:
        print(f"❌ Telegram bot error: {e}")

if __name__ == "__main__":
    asyncio.run(test_boot())
