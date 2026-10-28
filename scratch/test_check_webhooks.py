import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from aiogram import Bot
import config

async def check_bots():
    print("Checking Webhooks and API status for both bots...")
    
    # 1. Main Bot
    try:
        b1 = Bot(config.BOT_TOKEN)
        me1 = await b1.get_me()
        wh1 = await b1.get_webhook_info()
        print(f"Main Bot @{me1.username} (ID: {me1.id}): Webhook URL='{wh1.url}', Pending Updates={wh1.pending_update_count}")
        if wh1.url:
            print("  Clearing webhook for Main Bot...")
            await b1.delete_webhook(drop_pending_updates=True)
            print("  Webhook cleared successfully!")
        await b1.session.close()
    except Exception as e:
        print(f"Main Bot Error: {e}")

    # 2. Games Bot
    try:
        b2 = Bot(config.GAMES_BOT_TOKEN)
        me2 = await b2.get_me()
        wh2 = await b2.get_webhook_info()
        print(f"Games Bot @{me2.username} (ID: {me2.id}): Webhook URL='{wh2.url}', Pending Updates={wh2.pending_update_count}")
        if wh2.url:
            print("  Clearing webhook for Games Bot...")
            await b2.delete_webhook(drop_pending_updates=True)
            print("  Webhook cleared successfully!")
        await b2.session.close()
    except Exception as e:
        print(f"Games Bot Error: {e}")

if __name__ == '__main__':
    asyncio.run(check_bots())
