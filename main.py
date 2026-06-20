import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import TelegramObject
from typing import Callable, Dict, Any, Awaitable

import config
from database.database import init_db, SessionLocal
from utils.anti_spam import AntiSpamMiddleware
from utils.group_monitor import GroupActivityMiddleware

# Import Routers
from handlers import (
    start,
    profile,
    catch,
    admin,
    games,
    shop,
    trade,
    hunt,
    xo
)

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def check_and_copy_sqlite_db():
    import os
    import shutil
    dest_dir = "/app/data_volume"
    dest_path = os.path.join(dest_dir, "pokeempire.db")
    src_path = "/app/pokeempire.db"

    if os.path.exists(dest_dir) and not os.path.exists(dest_path):
        if os.path.exists(src_path):
            logger.info("Migrating existing pokeempire.db to Render Persistent Disk...")
            try:
                shutil.copy2(src_path, dest_path)
                logger.info("Database migrated to persistent storage successfully!")
            except Exception as e:
                logger.error(f"Failed to migrate database to persistent storage: {e}")
        else:
            logger.info("No source database found in code directory. A new database will be initialized.")

class DbSessionMiddleware:
    """aiogram Middleware that opens a SQLAlchemy async session for each update."""
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        async with SessionLocal() as session:
            data["db"] = session
            return await handler(event, data)

async def start_dummy_server():
    import os
    port = int(os.getenv("PORT", "8000"))
    
    async def handle_client(reader, writer):
        try:
            await reader.read(1024)
        except Exception:
            pass
        response = (
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: text/plain\r\n"
            "Content-Length: 2\r\n"
            "Connection: close\r\n\r\n"
            "OK"
        )
        try:
            writer.write(response.encode("utf-8"))
            await writer.drain()
            writer.close()
            await writer.wait_closed()
        except Exception:
            pass
        
    try:
        server = await asyncio.start_server(handle_client, "0.0.0.0", port)
        logger.info(f"Dummy HTTP server started on port {port} for health checks")
        asyncio.create_task(server.serve_forever())
    except Exception as e:
        logger.error(f"Failed to start dummy HTTP server: {e}")

async def register_bot_commands(bot: Bot):
    from aiogram.types import BotCommand
    commands = [
        BotCommand(command="start", description="Open primary Hub Dashboard"),
        BotCommand(command="profile", description="Check Trainer coins & metrics"),
        BotCommand(command="pokemon", description="Browse caught collection bag"),
        BotCommand(command="pokedex", description="Review Pokédex checklist"),
        BotCommand(command="xo", description="Play Tic Tac Toe (AI or PvP)"),
        BotCommand(command="coinflip", description="Bet coins on a coin flip"),
        BotCommand(command="rps", description="Play Rock-Paper-Scissors"),
        BotCommand(command="trivia", description="Answer trivia for coins"),
        BotCommand(command="streak", description="View Catch Streak stats"),
        BotCommand(command="shop", description="Open Coin Shop"),
        BotCommand(command="leaderboard", description="Global standings ranks"),
        BotCommand(command="help", description="Show complete guide instructions")
    ]
    try:
        await bot.set_my_commands(commands)
        logger.info("✅ Registered bot commands menu successfully")
    except Exception as e:
        logger.error(f"Failed to register bot commands: {e}")

async def main():
    # Run database migration check before initializing connection
    check_and_copy_sqlite_db()

    logger.info("Initializing PokeEmpire Spawn Bot engine...")


    # Initialize Database tables and seeds
    await init_db()
    logger.info("Database initialized and seeded successfully.")

    # Load settings cache and migrate json configs
    from utils.settings import load_all_settings_into_cache
    await load_all_settings_into_cache()
    logger.info("Settings cache loaded successfully.")

    # Validate token presence
    if not config.BOT_TOKEN or config.BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        logger.error("BOT_TOKEN is missing or not set in the environment (.env) file! Exiting.")
        sys.exit(1)

    # Initialize Bot & Dispatcher
    if config.TELEGRAM_PROXY:
        from aiogram.client.session.aiohttp import AiohttpSession
        session = AiohttpSession(proxy=config.TELEGRAM_PROXY)
        bot = Bot(
            token=config.BOT_TOKEN,
            session=session,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
        )
        logger.info(f"Bot client configured to route traffic via proxy: {config.TELEGRAM_PROXY}")
    else:
        bot = Bot(
            token=config.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
        )
    dp = Dispatcher()

    # Register Middlewares
    dp.update.outer_middleware(DbSessionMiddleware())
    dp.update.outer_middleware(AntiSpamMiddleware())
    
    # Message outer middleware to count group conversation activity
    dp.message.outer_middleware(GroupActivityMiddleware())

    # Register Handler Routers
    dp.include_router(start.router)
    dp.include_router(profile.router)
    dp.include_router(catch.router)
    dp.include_router(admin.router)
    dp.include_router(games.router)
    dp.include_router(shop.router)
    dp.include_router(trade.router)
    dp.include_router(hunt.router)
    dp.include_router(xo.router)

    logger.info("Bot handlers and routers registered.")

    # Register bot menu commands
    await register_bot_commands(bot)
    
    # Start a dummy HTTP server in the background for Render health checks
    await start_dummy_server()

    
    # Start polling updates with proxy failure resilience
    try:
        retry_count = 0
        while True:
            try:
                await dp.start_polling(bot, skip_updates=True)
                break
            except Exception as e:
                retry_count += 1
                logger.error(f"Connection failed at startup (attempt {retry_count}): {e}")
                logger.info("Retrying connection in 5 seconds...")
                await asyncio.sleep(5)
    finally:
        await bot.session.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
