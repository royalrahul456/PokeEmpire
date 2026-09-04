import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

import config
from aiogram import Bot

async def main():
    bot = Bot(token=config.BOT_TOKEN)
    try:
        me = await bot.get_me()
        print(f"Bot Username: @{me.username}")
        print(f"Bot Name: {me.first_name}")
        print(f"Bot ID: {me.id}")
        
        info = await bot.get_webhook_info()
        print(f"Webhook URL: '{info.url}'")
        print(f"Pending update count: {info.pending_update_count}")
        print(f"Last error: {info.last_error_message}")

        # Check latest updates
        updates = await bot.get_updates(limit=10)
        print(f"Retrieved {len(updates)} updates.")
        for u in updates:
            if u.message:
                print(f"Msg from {u.message.from_user.id}: {u.message.text}")
    except Exception as e:
        print(f"Error: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
