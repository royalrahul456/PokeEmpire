import imghdr
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
# from utils.membership import MembershipMiddleware


# Import Routers
from handlers import (
    start,
    profile,
    catch,
    admin,
    games,
    shop,
    trade,
    battle,
    xo,
    redeem,
    mines,
    auction,
    quests,
    guilds,
    mystery_events
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

    # 1. Database file migration
    force_restore = os.getenv("FORCE_DB_RESTORE", "0") == "1"
    if os.path.exists(dest_dir) and (not os.path.exists(dest_path) or force_restore):
        if os.path.exists(src_path):
            logger.info("Migrating existing pokeempire.db to Render Persistent Disk...")
            try:
                shutil.copy2(src_path, dest_path)
                logger.info("Database migrated to persistent storage successfully!")
            except Exception as e:
                logger.error(f"Failed to migrate database to persistent storage: {e}")
        else:
            logger.info("No source database found in code directory. A new database will be initialized.")

    # 2. Data directory copy (seed files)
    if os.path.exists(dest_dir):
        dest_data_dir = os.path.join(dest_dir, "data")
        os.makedirs(dest_data_dir, exist_ok=True)
        
        src_data_dir = "/app/data"
        if os.path.exists(src_data_dir):
            for filename in os.listdir(src_data_dir):
                src_file = os.path.join(src_data_dir, filename)
                dest_file = os.path.join(dest_data_dir, filename)
                if os.path.isfile(src_file) and not os.path.exists(dest_file):
                    logger.info(f"Copying seed file {filename} to persistent storage...")
                    try:
                        shutil.copy2(src_file, dest_file)
                    except Exception as e:
                        logger.error(f"Failed to copy seed file {filename}: {e}")

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

_dummy_server_running = False

async def start_dummy_server():
    global _dummy_server_running
    if _dummy_server_running:
        return
    _dummy_server_running = True

    import os
    from aiohttp import web
    port = int(os.getenv("PORT", "8000"))
    
    app = web.Application()
    
    async def health_check(request):
        return web.Response(text="OK", content_type="text/plain")
        
    app.router.add_get("/", health_check)
    app.router.add_get("/healthz", health_check)
    app.router.add_get("/api/health", health_check)
    
    try:
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, "0.0.0.0", port)
        await site.start()
        logger.info(f"✅ Web health check server active on port {port}")
    except Exception as e:
        logger.error(f"Failed to start web health check server: {e}")

async def register_bot_commands(bot: Bot):
    from aiogram.types import BotCommand
    commands = [
        BotCommand(command="start", description="🚀 Open primary Hub Dashboard"),
        BotCommand(command="profile", description="👤 Check Trainer coins & metrics"),
        BotCommand(command="achievements", description="🏅 View Trainer achievement milestones"),
        BotCommand(command="balance", description="💰 Check current coin wallet balance"),
        BotCommand(command="pokemon", description="🎒 Browse caught collection bag"),
        BotCommand(command="pokedex", description="📖 Review Pokédex checklist"),
        BotCommand(command="rankings", description="📈 Chat activity leaderboard"),
        BotCommand(command="claim", description="🎁 Claim a free daily random Pokémon"),
        BotCommand(command="xo", description="❌ Play Tic Tac Toe (AI or PvP)"),
        BotCommand(command="coinflip", description="🪙 Bet coins on a coin flip"),
        BotCommand(command="rps", description="✂️ Play Rock-Paper-Scissors"),
        BotCommand(command="trivia", description="❓ Answer trivia for coins"),
        BotCommand(command="streak", description="🔥 View Catch Streak stats"),
        BotCommand(command="shop", description="🛒 Open Coin Shop"),
        BotCommand(command="mines", description="💣 Play 5x5 Mines betting game"),
        BotCommand(command="endmines", description="🛑 Forcibly end active Mines game"),
        BotCommand(command="redeem", description="🎟️ Claim a promo/gift code"),
        BotCommand(command="gen", description="🔑 Generate a redeem code (Owner only)"),
        BotCommand(command="panel", description="⚙️ Executive Owner Console (Owner only)"),
        BotCommand(command="addrarity", description="✨ Create custom Pokémon rarity tier"),
        BotCommand(command="addpokemon", description="➕ Register a new Pokémon in database"),
        BotCommand(command="syncdatabase", description="🔄 Synchronize database records to channel"),
        BotCommand(command="au", description="🔨 Toggle global auction system"),
        BotCommand(command="auction", description="🏷️ List a Pokémon for auction"),
        BotCommand(command="auctions", description="🏛️ Browse and bid on active auctions"),
        BotCommand(command="cancelauction", description="❌ Cancel an active auction"),
        BotCommand(command="leaderboard", description="🏆 Global standings ranks"),
        BotCommand(command="banword", description="⛔ Ban a word in group chats"),
        BotCommand(command="removebanword", description="✅ Unban a word"),
        BotCommand(command="banwords", description="📋 Show all banned words"),
        BotCommand(command="app", description="⚡ Open PokeEmpire Mini App"),
        BotCommand(command="quests", description="⚔️ View Daily & Weekly Bounties"),
        BotCommand(command="guild", description="🏰 Manage Trainer Guild & Clan"),
        BotCommand(command="transactions", description="💳 View coin transaction history"),
        BotCommand(command="report", description="🚩 Report an error or bug to Creator"),
        BotCommand(command="help", description="ℹ️ Show complete guide instructions")
    ]
    try:
        await bot.set_my_commands(commands)
        logger.info("✅ Registered bot commands menu successfully")
    except Exception as e:
        logger.error(f"Failed to register bot commands: {e}")

    try:
        from aiogram.types import MenuButtonCommands
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logger.info("✅ Reset Chat Menu Button to standard commands menu")
    except Exception as e:
        logger.error(f"Failed to reset chat menu button: {e}")

def apply_auto_reply_patch():
    from aiogram.types import Message
    
    original_answer = Message.answer
    original_answer_photo = Message.answer_photo
    original_answer_video = Message.answer_video
    original_answer_animation = Message.answer_animation

    async def patched_answer(self: Message, *args, **kwargs):
        if self.chat.type != "private":
            return await self.reply(*args, **kwargs)
        return await original_answer(self, *args, **kwargs)

    async def patched_answer_photo(self: Message, *args, **kwargs):
        if self.chat.type != "private":
            return await self.reply_photo(*args, **kwargs)
        return await original_answer_photo(self, *args, **kwargs)

    async def patched_answer_video(self: Message, *args, **kwargs):
        if self.chat.type != "private":
            return await self.reply_video(*args, **kwargs)
        return await original_answer_video(self, *args, **kwargs)

    async def patched_answer_animation(self: Message, *args, **kwargs):
        if self.chat.type != "private":
            return await self.reply_animation(*args, **kwargs)
        return await original_answer_animation(self, *args, **kwargs)

    Message.answer = patched_answer
    Message.answer_photo = patched_answer_photo
    Message.answer_video = patched_answer_video
    Message.answer_animation = patched_answer_animation
    logger.info("Applied global auto-reply monkey patch to Message class for group chats.")

async def main():
    # Start web health check server FIRST so Render detects port immediately
    await start_dummy_server()
    
    # Apply the global auto-reply patch for group chats
    apply_auto_reply_patch()
    
    # Run database migration check before initializing connection
    check_and_copy_sqlite_db()

    logger.info("Initializing PokeEmpire Spawn Bot engine...")


    # Initialize Database tables and seeds
    await init_db()
    logger.info("Database initialized and seeded successfully.")

    # Retroactively calculate trainer levels for old players
    from utils.trainer_level import sync_retroactive_levels
    async with SessionLocal() as db:
        await sync_retroactive_levels(db)

    # Load dynamic admins and uploaders from database
    from database.models import GlobalSetting
    from sqlalchemy import select
    try:
        async with SessionLocal() as db:
            # Admins
            stmt = select(GlobalSetting).where(GlobalSetting.key == "dynamic_admin_ids")
            res = await db.execute(stmt)
            setting = res.scalar_one_or_none()
            if setting and setting.value:
                for val in setting.value.split(","):
                    if val.strip().isdigit():
                        uid = int(val)
                        if uid not in config.ADMIN_IDS:
                            config.ADMIN_IDS.append(uid)
            # Uploaders
            stmt = select(GlobalSetting).where(GlobalSetting.key == "dynamic_uploader_ids")
            res = await db.execute(stmt)
            setting = res.scalar_one_or_none()
            if setting and setting.value:
                for val in setting.value.split(","):
                    if val.strip().isdigit():
                        uid = int(val)
                        if uid not in config.UPLOADER_IDS:
                            config.UPLOADER_IDS.append(uid)
        logger.info("Dynamic Admin & Uploader IDs synced from database successfully.")
    except Exception as e:
        logger.error(f"Failed to sync dynamic IDs from database: {e}")

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
    
    # Apply custom premium emoji patch
    from utils.emoji_patch import patch_bot_emojis
    patch_bot_emojis(bot)

    dp = Dispatcher()

    # Register Middlewares
    dp.update.outer_middleware(DbSessionMiddleware())
    
    # Group Activity Middleware must run before membership & antispam checks
    # so that banned words and flood spams are deleted/fined immediately for all users.
    dp.message.outer_middleware(GroupActivityMiddleware())
    
    # Enforce membership checks on messages and callbacks - DISABLED
    # dp.message.outer_middleware(MembershipMiddleware())
    # dp.callback_query.outer_middleware(MembershipMiddleware())
    
    # Throttle commands and button clicks
    dp.message.outer_middleware(AntiSpamMiddleware())
    dp.callback_query.outer_middleware(AntiSpamMiddleware())

    # Register Handler Routers
    dp.include_router(admin.router)
    dp.include_router(start.router)
    dp.include_router(profile.router)
    dp.include_router(catch.router)
    dp.include_router(games.router)
    dp.include_router(shop.router)
    dp.include_router(trade.router)
    dp.include_router(battle.router)
    dp.include_router(xo.router)
    dp.include_router(redeem.router)
    dp.include_router(mines.router)
    dp.include_router(auction.router)
    dp.include_router(quests.router)
    dp.include_router(guilds.router)
    dp.include_router(mystery_events.router)

    logger.info("Bot handlers and routers registered.")

    # Register bot menu commands
    await register_bot_commands(bot)
    
    # Start a dummy HTTP server in the background for Render health checks
    await start_dummy_server()

    # Start the Auction settlement background loop worker task
    from handlers.auction import auction_settlement_worker
    asyncio.create_task(auction_settlement_worker(bot))

    
    # Start polling updates with proxy failure resilience
    try:
        retry_count = 0
        while True:
            try:
                await dp.start_polling(bot, skip_updates=False)
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
