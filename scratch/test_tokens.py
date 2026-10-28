import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from aiogram import Bot
import config

async def test_tokens():
    print(f"Loaded config.BOT_TOKEN: {config.BOT_TOKEN[:15]}...")
    print("Testing Main Bot Token...")
    try:
        b1 = Bot(config.BOT_TOKEN)
        me1 = await b1.get_me()
        print(f"Main Bot SUCCESS: @{me1.username} (ID: {me1.id})")
        await b1.session.close()
    except Exception as e:
        print(f"Main Bot FAILED: {type(e).__name__}: {e}")

    print("\nTesting Games Bot Token...")
    try:
        b2 = Bot(config.GAMES_BOT_TOKEN)
        me2 = await b2.get_me()
        print(f"Games Bot SUCCESS: @{me2.username} (ID: {me2.id})")
        await b2.session.close()
    except Exception as e:
        print(f"Games Bot FAILED: {type(e).__name__}: {e}")

if __name__ == '__main__':
    asyncio.run(test_tokens())
