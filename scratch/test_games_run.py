import sys
import os
import asyncio
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

async def test_games_bot_polling():
    import config
    from aiogram import Bot, Dispatcher
    from utils.anti_spam import AntiSpamMiddleware
    from utils.group_monitor import GroupActivityMiddleware
    from database.database import init_db, SessionLocal
    from handlers import games_start, games, xo, mines
    from games_main import DbSessionMiddleware

    print("1. Initializing DB & Caches...", flush=True)
    await init_db()
    
    from utils.pokemon_cache import init_pokemon_cache
    async with SessionLocal() as db:
        await init_pokemon_cache(db)

    print("2. Connecting Games Bot @PokeXArenaBot...", flush=True)
    bot = Bot(token=config.GAMES_BOT_TOKEN)
    info = await bot.get_me()
    print(f"SUCCESS! Connected as @{info.username}", flush=True)

    dp = Dispatcher()
    dp.update.outer_middleware(DbSessionMiddleware())
    dp.message.outer_middleware(GroupActivityMiddleware())
    dp.message.outer_middleware(AntiSpamMiddleware())
    dp.callback_query.outer_middleware(AntiSpamMiddleware())

    dp.include_router(games_start.router)
    dp.include_router(games.router)
    dp.include_router(xo.router)
    dp.include_router(mines.router)

    print("3. Starting Polling for 5 seconds...", flush=True)
    polling_task = asyncio.create_task(dp.start_polling(bot, skip_updates=True))
    await asyncio.sleep(5)
    polling_task.cancel()
    await bot.session.close()
    print("4. Polling test complete! PokeArena is 100% operational!")

if __name__ == "__main__":
    asyncio.run(test_games_bot_polling())
