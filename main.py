import imghdr
import asyncio
import logging
import sys
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.types import TelegramObject
from typing import Callable, Dict, Any, Awaitable

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
else:
    try:
        import uvloop
        uvloop.install()
    except Exception:
        pass

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
    games_redirect,
    games_start,
    games,
    xo,
    mines,
    shop,
    trade,
    battle,
    redeem,
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
    from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats, MenuButtonCommands
    commands = [
        BotCommand(command="start", description="🚀 Open primary Hub Dashboard"),
        BotCommand(command="profile", description="👤 Check Trainer coins & metrics"),
        BotCommand(command="achievements", description="🏅 View Trainer achievement milestones"),
        BotCommand(command="balance", description="💰 Check current coin wallet balance"),
        BotCommand(command="bal", description="💳 Wallet Quick Balance"),
        BotCommand(command="pokemon", description="🎒 Browse caught collection bag"),
        BotCommand(command="pokedex", description="📖 Review Pokédex checklist"),
        BotCommand(command="rankings", description="📈 Chat activity leaderboard"),
        BotCommand(command="claim", description="🎁 Claim a free daily random Pokémon"),
        BotCommand(command="daily", description="📅 Claim daily bonus coins"),
        BotCommand(command="games", description="🎮 Play Mini-Games on PokeArena"),
        BotCommand(command="streak", description="🔥 View Catch Streak stats"),
        BotCommand(command="fine", description="🚨 Issue a 20% fine penalty (Bot Admin only)"),
        BotCommand(command="adminlist", description="👑 View Bot Admin Roster"),
        BotCommand(command="admins", description="🛡️ View Bot Admin Roster"),
        BotCommand(command="shop", description="🛒 Open Coin Shop"),
        BotCommand(command="redeem", description="🎟️ Claim a promo/gift code"),
        BotCommand(command="gen", description="🔑 Generate a redeem code (Owner only)"),
        BotCommand(command="panel", description="⚙️ Executive Owner Console (Owner only)"),
        BotCommand(command="ping", description="⚡ Check System & DB Latency"),
        BotCommand(command="addrarity", description="✨ Create custom Pokémon rarity tier"),
        BotCommand(command="addpokemon", description="➕ Register a new Pokémon in database"),
        BotCommand(command="setpokename", description="✏️ Rename a Pokémon in database (Admin only)"),
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
        BotCommand(command="broadcast", description="📢 Broadcast announcement to all groups & channels"),
        BotCommand(command="report", description="🚩 Report an error or bug to Creator"),
        BotCommand(command="help", description="ℹ️ Show complete guide instructions")
    ]
    try:
        await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
        await bot.set_my_commands(commands, scope=BotCommandScopeAllPrivateChats())
        await bot.set_my_commands(commands, scope=BotCommandScopeAllGroupChats())
        logger.info("✅ Registered bot commands menu across all scopes successfully")
    except Exception as e:
        logger.error(f"Failed to register bot commands: {e}")

    try:
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
        logger.info("✅ Reset Chat Menu Button to standard commands menu")
    except Exception as e:
        logger.error(f"Failed to reset chat menu button: {e}")

async def register_games_bot_commands(bot: Bot):
    from aiogram.types import BotCommand, BotCommandScopeDefault, BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats, MenuButtonCommands
    commands = [
        BotCommand(command="start", description="🎮 Launch PokeArena Games Hub"),
        BotCommand(command="games", description="🎰 Open Games Hub"),
        BotCommand(command="balance", description="💰 Check your Coins & Gems"),
        BotCommand(command="bal", description="💳 Wallet Quick Balance"),
        BotCommand(command="streak", description="🔥 View Daily Catch Streak"),
        BotCommand(command="whothat", description="👤 The Silhouette Trial"),
        BotCommand(command="blitz", description="⚡ Type Matchup Blitz"),
        BotCommand(command="voltorb", description="⚡ The Voltorb Lock (Num Guess)"),
        BotCommand(command="mines", description="💣 Play Mines Game"),
        BotCommand(command="ttc", description="❌ Play Tic-Tac-Toe PvP Duel"),
        BotCommand(command="spin", description="🎡 Free Hourly Fortune Wheel"),
        BotCommand(command="dice", description="🎲 Roll Dice Duel vs AI"),
        BotCommand(command="darts", description="🎯 Darts Target Challenge"),
        BotCommand(command="basketball", description="🏀 Basketball Free Throw"),
        BotCommand(command="football", description="⚽ Football Penalty Shootout"),
        BotCommand(command="bowling", description="🎳 Bowling Strike Alley"),
        BotCommand(command="coinflip", description="🪙 Flip Coin 50/50"),
        BotCommand(command="rps", description="✊ Play Rock Paper Scissors"),
        BotCommand(command="scribble", description="✏️ Play Drawing & Guessing"),
        BotCommand(command="nameguess", description="💡 Play Pokémon Name Quiz"),
        BotCommand(command="abort", description="🛑 Abort active mini-game in chat"),
        BotCommand(command="help", description="📖 How to Play Mini-Games"),
    ]
    try:
        await bot.set_my_commands(commands, scope=BotCommandScopeDefault())
        await bot.set_my_commands(commands, scope=BotCommandScopeAllPrivateChats())
        await bot.set_my_commands(commands, scope=BotCommandScopeAllGroupChats())
        logger.info("✅ Registered PokeArena games bot commands across all scopes successfully")
    except Exception as e:
        logger.warning(f"Failed to register PokeArena bot commands: {e}")

    try:
        await bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    except Exception:
        pass

def apply_auto_reply_patch():
    from aiogram.types import Message
    
    original_answer = Message.answer
    original_answer_photo = Message.answer_photo
    original_answer_video = Message.answer_video
    original_answer_animation = Message.answer_animation
    original_reply = Message.reply
    original_reply_photo = Message.reply_photo
    original_reply_video = Message.reply_video
    original_reply_animation = Message.reply_animation

    async def patched_reply(self: Message, *args, **kwargs):
        try:
            return await original_reply(self, *args, **kwargs)
        except Exception:
            try:
                return await original_answer(self, *args, **kwargs)
            except Exception:
                kwargs_plain = dict(kwargs)
                kwargs_plain["parse_mode"] = None
                return await original_answer(self, *args, **kwargs_plain)

    async def patched_answer(self: Message, *args, **kwargs):
        if self.chat.type != "private":
            try:
                return await original_reply(self, *args, **kwargs)
            except Exception:
                pass
        try:
            return await original_answer(self, *args, **kwargs)
        except Exception as e:
            try:
                kwargs_plain = dict(kwargs)
                kwargs_plain["parse_mode"] = None
                return await original_answer(self, *args, **kwargs_plain)
            except Exception:
                raise e

    async def patched_answer_photo(self: Message, *args, **kwargs):
        if self.chat.type != "private":
            try:
                return await original_reply_photo(self, *args, **kwargs)
            except Exception:
                pass
        try:
            return await original_answer_photo(self, *args, **kwargs)
        except Exception as err:
            logger.warning(f"Failed to send photo in chat {self.chat.id}: {err}. Falling back to text message.")
            caption = kwargs.get("caption") or (args[1] if len(args) > 1 and isinstance(args[1], str) else None)
            reply_markup = kwargs.get("reply_markup")
            parse_mode = kwargs.get("parse_mode", "HTML")
            if caption:
                try:
                    return await self.answer(text=caption, reply_markup=reply_markup, parse_mode=parse_mode)
                except Exception:
                    return await self.answer(text=caption, reply_markup=reply_markup, parse_mode=None)
            raise err

    async def patched_answer_video(self: Message, *args, **kwargs):
        if self.chat.type != "private":
            try:
                return await original_reply_video(self, *args, **kwargs)
            except Exception:
                pass
        try:
            return await original_answer_video(self, *args, **kwargs)
        except Exception as err:
            logger.warning(f"Failed to send video in chat {self.chat.id}: {err}. Falling back to text message.")
            caption = kwargs.get("caption") or (args[1] if len(args) > 1 and isinstance(args[1], str) else None)
            reply_markup = kwargs.get("reply_markup")
            parse_mode = kwargs.get("parse_mode", "HTML")
            if caption:
                try:
                    return await self.answer(text=caption, reply_markup=reply_markup, parse_mode=parse_mode)
                except Exception:
                    return await self.answer(text=caption, reply_markup=reply_markup, parse_mode=None)
            raise err

    async def patched_answer_animation(self: Message, *args, **kwargs):
        if self.chat.type != "private":
            try:
                return await original_reply_animation(self, *args, **kwargs)
            except Exception:
                pass
        try:
            return await original_answer_animation(self, *args, **kwargs)
        except Exception as err:
            logger.warning(f"Failed to send animation in chat {self.chat.id}: {err}. Falling back to text message.")
            caption = kwargs.get("caption") or (args[1] if len(args) > 1 and isinstance(args[1], str) else None)
            reply_markup = kwargs.get("reply_markup")
            parse_mode = kwargs.get("parse_mode", "HTML")
            if caption:
                try:
                    return await self.answer(text=caption, reply_markup=reply_markup, parse_mode=parse_mode)
                except Exception:
                    return await self.answer(text=caption, reply_markup=reply_markup, parse_mode=None)
            raise err

    Message.answer = patched_answer
    Message.reply = patched_reply
    Message.answer_photo = patched_answer_photo
    Message.answer_video = patched_answer_video
    Message.answer_animation = patched_answer_animation
    logger.info("Applied resilient global auto-reply monkey patch to Message class for all chats.")

async def _bg_sync_retroactive_levels():
    try:
        from utils.trainer_level import sync_retroactive_levels
        async with SessionLocal() as db:
            await sync_retroactive_levels(db)
    except Exception as e:
        logger.warning(f"Background retroactive level sync exception: {e}")

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

    # Initialize sub-millisecond in-memory Pokemon Cache
    from utils.pokemon_cache import init_pokemon_cache
    async with SessionLocal() as db:
        await init_pokemon_cache(db)

    # Launch retroactive level sync in background so polling starts immediately
    asyncio.create_task(_bg_sync_retroactive_levels())

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

    # Validate bot token with Telegram API before starting polling
    try:
        bot_info = await bot.get_me()
        logger.info(f"✅ Main Bot authenticated successfully as @{bot_info.username} (ID: {bot_info.id})")
    except Exception as e:
        logger.error(f"❌ Main Bot authentication failed: Telegram API returned ({e}). Please get a fresh token from @BotFather!")
        return

    dp = Dispatcher()

    @dp.error()
    async def global_main_error_handler(event):
        logger.error(f"⚠️ Main Bot unhandled error: {event.exception}", exc_info=True)

    # Register Middlewares
    dp.update.outer_middleware(DbSessionMiddleware())
    dp.message.outer_middleware(GroupActivityMiddleware())
    dp.message.outer_middleware(AntiSpamMiddleware())
    dp.callback_query.outer_middleware(AntiSpamMiddleware())

    # Check if dual bot configuration is active
    is_dual_bot = bool(
        config.GAMES_BOT_TOKEN 
        and config.GAMES_BOT_TOKEN != config.BOT_TOKEN 
        and config.GAMES_BOT_TOKEN != "YOUR_BOT_TOKEN_HERE"
    )

    # Start the Auction settlement background loop worker task
    from handlers.auction import auction_settlement_worker
    asyncio.create_task(auction_settlement_worker(bot))

    # Start the in-memory chat activity batch flusher worker task
    from utils.group_monitor import start_chat_activity_worker
    asyncio.create_task(start_chat_activity_worker())

    if is_dual_bot:
        logger.info("🚀 Dual-Bot Mode active: Starting PokeEmpire (Main) + PokeArena (Games) concurrently.")
        
        # Main bot handles RPG gameplay and redirects game commands to PokeArena
        dp.include_router(admin.router)
        dp.include_router(start.router)
        dp.include_router(profile.router)
        dp.include_router(catch.router)
        dp.include_router(games_redirect.router)
        dp.include_router(shop.router)
        dp.include_router(trade.router)
        dp.include_router(battle.router)
        dp.include_router(redeem.router)
        dp.include_router(auction.router)
        dp.include_router(quests.router)
        dp.include_router(guilds.router)
        dp.include_router(mystery_events.router)
        
        # Setup Games bot
        if config.TELEGRAM_PROXY:
            from aiogram.client.session.aiohttp import AiohttpSession
            games_session = AiohttpSession(proxy=config.TELEGRAM_PROXY)
            games_bot = Bot(
                token=config.GAMES_BOT_TOKEN,
                session=games_session,
                default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
            )
        else:
            games_bot = Bot(
                token=config.GAMES_BOT_TOKEN,
                default=DefaultBotProperties(parse_mode=ParseMode.MARKDOWN)
            )
            
        patch_bot_emojis(games_bot)
        
        dp_games = Dispatcher()

        @dp_games.error()
        async def global_games_error_handler(event):
            logger.error(f"⚠️ Games Bot unhandled error: {event.exception}", exc_info=True)

        dp_games.update.outer_middleware(DbSessionMiddleware())
        dp_games.message.outer_middleware(AntiSpamMiddleware())
        dp_games.callback_query.outer_middleware(AntiSpamMiddleware())
        
        dp_games.include_router(games_start.router)
        dp_games.include_router(games.router)
        dp_games.include_router(xo.router)
        dp_games.include_router(mines.router)
        
        logger.info("Both Main and Games Bot handlers registered.")
        
        # Verify Bot Tokens with Telegram
        try:
            bot_info = await bot.get_me()
            logger.info(f"✅ Main Bot authenticated: @{bot_info.username} (ID: {bot_info.id})")
        except Exception as e:
            logger.error(f"❌ Main Bot token verification failed: {e}")

        try:
            games_bot_info = await games_bot.get_me()
            logger.info(f"✅ Games Bot authenticated: @{games_bot_info.username} (ID: {games_bot_info.id})")
        except Exception as e:
            logger.error(f"❌ Games Bot token verification failed: {e}")

        await register_bot_commands(bot)
        await register_games_bot_commands(games_bot)
        
        ALLOWED_UPDATES = ["message", "edited_message", "callback_query", "chat_member", "my_chat_member", "inline_query"]

        async def run_main_bot():
            retry_count = 0
            while True:
                try:
                    logger.info("Main Bot (PokeEmpire) clearing webhook and starting polling...")
                    try:
                        await bot.delete_webhook(drop_pending_updates=True)
                    except Exception as wh_err:
                        logger.warning(f"Could not delete webhook for Main Bot: {wh_err}")
                    await dp.start_polling(bot, allowed_updates=ALLOWED_UPDATES, handle_signals=True)
                    break
                except Exception as e:
                    retry_count += 1
                    logger.error(f"Main Bot connection failed (attempt {retry_count}): {e}")
                    logger.info("Retrying Main Bot connection in 5 seconds...")
                    await asyncio.sleep(5)

        async def run_games_bot():
            retry_count = 0
            while True:
                try:
                    logger.info("Games Bot (PokeArena) clearing webhook and starting polling...")
                    try:
                        await games_bot.delete_webhook(drop_pending_updates=True)
                    except Exception as wh_err:
                        logger.warning(f"Could not delete webhook for Games Bot: {wh_err}")
                    await dp_games.start_polling(games_bot, allowed_updates=ALLOWED_UPDATES, handle_signals=False)
                    break
                except Exception as e:
                    retry_count += 1
                    logger.error(f"Games Bot connection failed (attempt {retry_count}): {e}")
                    logger.info("Retrying Games Bot connection in 5 seconds...")
                    await asyncio.sleep(5)

        try:
            await asyncio.gather(run_main_bot(), run_games_bot(), return_exceptions=True)
        finally:
            try:
                await bot.session.close()
            except Exception:
                pass
            try:
                await games_bot.session.close()
            except Exception:
                pass
    else:
        logger.info("⚡ Single-Bot Mode active: All gameplay and mini-games handled on PokeEmpire.")
        dp.include_router(admin.router)
        dp.include_router(start.router)
        dp.include_router(profile.router)
        dp.include_router(catch.router)
        dp.include_router(games_start.router)
        dp.include_router(games.router)
        dp.include_router(xo.router)
        dp.include_router(mines.router)
        dp.include_router(shop.router)
        dp.include_router(trade.router)
        dp.include_router(battle.router)
        dp.include_router(redeem.router)
        dp.include_router(auction.router)
        dp.include_router(quests.router)
        dp.include_router(guilds.router)
        dp.include_router(mystery_events.router)

        logger.info("Bot handlers and routers registered.")
        await register_bot_commands(bot)
        
        ALLOWED_UPDATES = ["message", "edited_message", "callback_query", "chat_member", "my_chat_member", "inline_query"]
        try:
            retry_count = 0
            while True:
                try:
                    logger.info("PokeEmpire Bot clearing webhook and starting polling...")
                    try:
                        await bot.delete_webhook(drop_pending_updates=True)
                    except Exception as wh_err:
                        logger.warning(f"Could not delete webhook: {wh_err}")
                    await dp.start_polling(bot, allowed_updates=ALLOWED_UPDATES, handle_signals=True)
                    break
                except Exception as e:
                    retry_count += 1
                    logger.error(f"Connection failed at startup (attempt {retry_count}): {e}")
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
        logger.info("Bot stopped by user.")
