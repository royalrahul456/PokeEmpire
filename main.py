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
    trade
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

async def main():
    logger.info("Initializing PokeEmpire Spawn Bot engine...")

    # Initialize Database tables and seeds
    await init_db()
    logger.info("Database initialized and seeded successfully.")

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

    logger.info("Bot handlers and routers registered.")
    
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
