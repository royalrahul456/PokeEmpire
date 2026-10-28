import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
import config
from database.database import init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("live_test")

async def test_polling():
    await init_db()
    print("Testing Main Bot get_me...")
    b1 = Bot(config.BOT_TOKEN)
    me1 = await b1.get_me()
    print(f"Main Bot connected: @{me1.username}")

    print("Testing Games Bot get_me...")
    b2 = Bot(config.GAMES_BOT_TOKEN)
    me2 = await b2.get_me()
    print(f"Games Bot connected: @{me2.username}")

    await b1.delete_webhook(drop_pending_updates=True)
    await b2.delete_webhook(drop_pending_updates=True)
    print("Cleared webhooks for both bots.")

    dp1 = Dispatcher()
    dp2 = Dispatcher()

    @dp1.message()
    async def on_main_msg(msg):
        print(f"[MAIN BOT] Received update from {msg.from_user.username}: {msg.text}")
        await msg.answer("🤖 Main bot is alive!")

    @dp2.message()
    async def on_games_msg(msg):
        print(f"[GAMES BOT] Received update from {msg.from_user.username}: {msg.text}")
        await msg.answer("🎮 Games bot is alive!")

    print("\nStarting live polling on local machine for 20 seconds...")
    print("SEND A MESSAGE TO @PokeEmpireBot OR @PokeXArenaBot ON TELEGRAM NOW!")

    t1 = asyncio.create_task(dp1.start_polling(b1))
    t2 = asyncio.create_task(dp2.start_polling(b2))

    await asyncio.sleep(20)

    print("Stopping test polling...")
    t1.cancel()
    t2.cancel()
    await b1.session.close()
    await b2.session.close()

if __name__ == '__main__':
    try:
        asyncio.run(test_polling())
    except Exception as e:
        print(f"Test exception: {e}")
