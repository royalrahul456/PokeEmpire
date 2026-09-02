import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

import config
from aiogram import Bot

async def test_get_updates():
    bot = Bot(token=config.BOT_TOKEN)
    try:
        updates = await bot.get_updates(limit=5)
        print(f"📥 Received {len(updates)} pending updates from Telegram:")
        for u in updates:
            msg = u.message or u.edited_message or u.callback_query
            if u.message:
                print(f"   [User {u.message.from_user.id} (@{u.message.from_user.username})]: {u.message.text}")
            elif u.callback_query:
                print(f"   [Callback from User {u.callback_query.from_user.id}]: {u.callback_query.data}")
    except Exception as e:
        print(f"❌ Error getting updates: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(test_get_updates())
