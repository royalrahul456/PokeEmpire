import imghdr
import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import TelegramObject, Message
from typing import Callable, Dict, Any, Awaitable

import config
from database.database import init_db, SessionLocal
from utils.anti_spam import AntiSpamMiddleware
from utils.group_monitor import GroupActivityMiddleware

# Import Game Handler Routers
from handlers import (
    games_start,
    games,
    xo,
    mines
)

# Set up logging configuration
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - [GAMES_BOT] - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("games_bot")

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

def apply_auto_reply_patch():
    """Monkey-patches Message.answer methods for group chats."""
    original_answer = Message.answer
    original_answer_photo = Message.answer_photo
    original_answer_video = Message.answer_video
    original_answer_animation = Message.answer_animation

    async def patched_answer(self: Message, *args, **kwargs):
        if self.chat.type != "private":
            try:
                return await self.reply(*args, **kwargs)
            except Exception:
                return await original_answer(self, *args, **kwargs)
        return await original_answer(self, *args, **kwargs)

    async def patched_answer_photo(self: Message, *args, **kwargs):
        if self.chat.type != "private":
            try:
                return await self.reply_photo(*args, **kwargs)
            except Exception:
                return await original_answer_photo(self, *args, **kwargs)
        return await original_answer_photo(self, *args, **kwargs)

    async def patched_answer_video(self: Message, *args, **kwargs):
        if self.chat.type != "private":
            try:
                return await self.reply_video(*args, **kwargs)
            except Exception:
                return await original_answer_video(self, *args, **kwargs)
        return await original_answer_video(self, *args, **kwargs)

    async def patched_answer_animation(self: Message, *args, **kwargs):
        if self.chat.type != "private":
            try:
                return await self.reply_animation(*args, **kwargs)
            except Exception:
                return await original_answer_animation(self, *args, **kwargs)
        return await original_answer_animation(self, *args, **kwargs)

    Message.answer = patched_answer
    Message.answer_photo = patched_answer_photo
    Message.answer_video = patched_answer_video
    Message.answer_animation = patched_answer_animation
    logger.info("Applied auto-reply monkey patch for group chats.")

async def register_games_bot_commands(bot: Bot):
    from aiogram.types import BotCommand
    commands = [
        BotCommand(command="start", description="🎮 Launch PokeArena Games Center"),
        BotCommand(command="games", description="🎰 Open Games Hub"),
        BotCommand(command="balance", description="💰 Check your Coins & Gems"),
        BotCommand(command="bal", description="💳 Wallet Quick Balance"),
        BotCommand(command="streak", description="🔥 Daily Catch Streak"),
        BotCommand(command="whothat", description="👤 The Silhouette Trial"),
        BotCommand(command="blitz", description="⚡ Type Matchup Blitz"),
        BotCommand(command="voltorb", description="⚡ The Voltorb Lock (Num Guess)"),
        BotCommand(command="mines", description="💣 Play Mines Game"),
        BotCommand(command="ttc", description="❌ Play Tic-Tac-Toe PvP Duel"),
        BotCommand(command="spin", description="🎡 Free Hourly Fortune Wheel"),
        BotCommand(command="rps", description="✊ Play Rock Paper Scissors"),
        BotCommand(command="scribble", description="✏️ Play Drawing & Guessing"),
        BotCommand(command="nameguess", description="💡 Play Pokémon Name Quiz"),
        BotCommand(command="fine", description="🚨 Fine user 20% balance (Admin)"),
        BotCommand(command="help", description="📖 How to Play Mini-Games"),
    ]
    try:
        await bot.set_my_commands(commands)
        logger.info("Registered Telegram menu commands for PokeArena.")
    except Exception as e:
        logger.warning(f"Failed to register Telegram menu commands: {e}")

async def main():
    token = config.GAMES_BOT_TOKEN or config.BOT_TOKEN
    if not token or token == "YOUR_BOT_TOKEN_HERE":
        logger.error("GAMES_BOT_TOKEN (or BOT_TOKEN) is missing or not set in environment! Exiting.")
        sys.exit(1)

    logger.info("Starting PokeEmpire Games Bot engine...")

    # Apply auto-reply patch
    apply_auto_reply_patch()

    # Initialize Database connection
    logger.info("Initializing database connection...")
    await init_db()
    logger.info("Database initialized successfully.")

    # Initialize sub-millisecond in-memory Pokemon Cache
    logger.info("Initializing Pokemon cache...")
    from utils.pokemon_cache import init_pokemon_cache
    async with SessionLocal() as db:
        await init_pokemon_cache(db)

    # Load settings cache
    logger.info("Loading settings cache...")
    from utils.settings import load_all_settings_into_cache
    await load_all_settings_into_cache()
    logger.info("Settings cache loaded successfully.")

    # Initialize Bot & Dispatcher
    if config.TELEGRAM_PROXY:
        from aiogram.client.session.aiohttp import AiohttpSession
        session = AiohttpSession(proxy=config.TELEGRAM_PROXY)
        bot = Bot(
            token=token,
            session=session,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
        )
    else:
        bot = Bot(
            token=token,
            default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
        )

    # Apply custom premium emoji patch
    from utils.emoji_patch import patch_bot_emojis
    patch_bot_emojis(bot)

    dp = Dispatcher()

    # Register Middlewares
    dp.update.outer_middleware(DbSessionMiddleware())
    dp.message.outer_middleware(GroupActivityMiddleware())
    dp.message.outer_middleware(AntiSpamMiddleware())
    dp.callback_query.outer_middleware(AntiSpamMiddleware())

    # Register Game Handlers
    dp.include_router(games_start.router)
    dp.include_router(games.router)
    dp.include_router(xo.router)
    dp.include_router(mines.router)

    logger.info("Games Bot handlers registered.")

    # Register bot commands menu in Telegram
    await register_games_bot_commands(bot)

    # Fetch bot info to store main bot username if available
    try:
        bot_info = await bot.get_me()
        logger.info(f"Games Bot active as @{bot_info.username}")
    except Exception as e:
        logger.warning(f"Could not fetch bot info: {e}")

    # Start Polling Loop
    ALLOWED_UPDATES = ["message", "edited_message", "callback_query", "chat_member", "my_chat_member", "inline_query"]
    try:
        retry_count = 0
        while True:
            try:
                try:
                    await bot.delete_webhook(drop_pending_updates=True)
                except Exception as wh_err:
                    logger.warning(f"Could not delete webhook: {wh_err}")
                await dp.start_polling(bot, allowed_updates=ALLOWED_UPDATES)
                break
            except Exception as e:
                retry_count += 1
                logger.error(f"Games Bot connection failed (attempt {retry_count}): {e}")
                logger.info("Retrying connection in 5 seconds...")
                await asyncio.sleep(5)
    finally:
        try:
            await bot.session.close()
        except Exception:
            pass

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Games Bot stopped by user.")
