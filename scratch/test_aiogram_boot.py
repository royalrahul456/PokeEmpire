import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

import config
from database.database import SessionLocal, init_db
from aiogram import Bot

async def test_aiogram():
    print("1. Checking BOT_TOKEN...")
    token = config.BOT_TOKEN
    print(f"BOT_TOKEN set: {bool(token and token != 'YOUR_BOT_TOKEN_HERE')}")
    if not token or token == "YOUR_BOT_TOKEN_HERE":
        print("❌ ERROR: BOT_TOKEN is not set or using default value!")
        return

    print("2. Testing Aiogram Bot get_me()...")
    bot = Bot(token=token)
    try:
        me = await bot.get_me()
        print(f"✅ Bot initialized successfully! Name: {me.first_name}, Username: @{me.username}")
    except Exception as e:
        print(f"❌ Failed to connect to Telegram API: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(test_aiogram())
