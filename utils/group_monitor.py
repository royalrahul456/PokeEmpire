import random
import time
import html
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from typing import Callable, Dict, Any, Awaitable
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import GroupSetting, User
from services.spawn_service import SpawnService
from utils.formatters import escape_md
import config

# In-memory caches to eliminate intermediate database UPDATE statements on every message
# chat_id -> {"spawn_threshold": int, "enabled": bool}
group_settings_cache = {}
# chat_id -> current message count (int)
group_message_counters = {}

# Anti-flood states
# user_id -> list of float timestamps of recent messages
recent_user_messages = {}
# user_id -> float (timestamp when they were last fined)
last_fine_time = {}

class GroupActivityMiddleware(BaseMiddleware):
    """Middleware that counts chat activity, manages anti-flood fines, and triggers wild spawns."""
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if not isinstance(event, Message):
            return await handler(event, data)

        chat = event.chat
        # Only monitor group or supergroup chats
        if chat.type not in ["group", "supergroup"]:
            return await handler(event, data)

        # 1. Banned Words Detection
        user = event.from_user
        if user and not user.is_bot:
            user_id = user.id
            text_to_check = event.text or event.caption
            if text_to_check:
                from utils.ban_words import check_text_for_ban_words
                matched_word = check_text_for_ban_words(text_to_check)
                if matched_word:
                    # Try to delete bad word message
                    try:
                        await event.delete()
                    except Exception as e:
                        print(f"Failed to delete bad word message: {e}")
                        
                    db: AsyncSession = data.get("db")
                    if db:
                        try:
                            spammer_stmt = select(User).where(User.id == user_id)
                            spammer_res = await db.execute(spammer_stmt)
                            spammer = spammer_res.scalar_one_or_none()
                            
                            if not spammer:
                                spammer = User(
                                    id=user_id,
                                    username=user.username,
                                    nickname=user.first_name or user.username or "Trainer",
                                    coins=500
                                )
                                db.add(spammer)
                                await db.flush()
                            
                            # Fine 50,000 coins
                            spammer.coins = max(0, spammer.coins - 50000)
                            
                            if config.ADMIN_IDS:
                                creator_id = config.ADMIN_IDS[0]
                                creator_stmt = select(User).where(User.id == creator_id)
                                creator_res = await db.execute(creator_stmt)
                                creator = creator_res.scalar_one_or_none()
                                
                                if not creator:
                                    creator = User(id=creator_id, username="creator", nickname="Creator")
                                    db.add(creator)
                                    await db.flush()
                                    
                                creator.coins += 50000
                                await db.commit()
                                
                                spammer_mention = user.mention_html()
                                # Tag person and tell they are fined
                                await event.answer(
                                    f"⚠️ {spammer_mention} you are fined 50k coins for your behaviour",
                                    parse_mode="HTML"
                                )
                                
                                # Send DM confirmation to bot owner
                                bot = data.get("bot") or event.bot
                                if bot:
                                    try:
                                        spammer_username_display = f"@{user.username}" if user.username else f"ID {user_id}"
                                        await bot.send_message(
                                            chat_id=creator_id,
                                            text=f"💸 <b>Bad Word Fine Transferred!</b>\n"
                                                 f"───────────────\n"
                                                 f"<blockquote>👤 Spammer: <b>{spammer_username_display}</b>\n"
                                                 f"🤬 Word match: <b>{html.escape(matched_word)}</b>\n"
                                                 f"💰 Fine: <b>+50k coins</b> (transferred to your balance)</blockquote>",
                                            parse_mode="HTML"
                                        )
                                    except Exception as dm_err:
                                        print(f"Failed to DM creator about bad word fine: {dm_err}")
                        except Exception as err:
                            await db.rollback()
                            print(f"Error executing bad word fine: {err}")
                    return None  # Stop handler execution for this message

        # 2. Anti-Flood / Anti-Spam Detection
        if user and not user.is_bot:
            user_id = user.id
            now = time.time()
            
            # Fetch user message history
            times = recent_user_messages.get(user_id, [])
            # Keep only messages from the last 3.0 seconds
            times = [t for t in times if now - t < 3.0]
            times.append(now)
            recent_user_messages[user_id] = times
            
            # If they sent more than 5 messages in 3 seconds, delete the message/sticker
            if len(times) > 5:
                try:
                    await event.delete()
                except Exception as e:
                    print(f"Failed to delete spam message: {e}")
                
                # Cooldown of 10 seconds between fines to prevent repeat alerts
                if now - last_fine_time.get(user_id, 0) > 10.0:
                    last_fine_time[user_id] = now
                    
                    db: AsyncSession = data.get("db")
                    if db:
                        try:
                            # Spammer User
                            spammer_stmt = select(User).where(User.id == user_id)
                            spammer_res = await db.execute(spammer_stmt)
                            spammer = spammer_res.scalar_one_or_none()
                            
                            if not spammer:
                                spammer = User(
                                    id=user_id,
                                    username=user.username,
                                    nickname=user.first_name or user.username or "Trainer",
                                    coins=500
                                )
                                db.add(spammer)
                                await db.flush()
                            
                            # Deduct 20,000 coins
                            spammer.coins = max(0, spammer.coins - 20000)
                            
                            # Bot Creator/Owner User
                            if config.ADMIN_IDS:
                                creator_id = config.ADMIN_IDS[0]
                                creator_stmt = select(User).where(User.id == creator_id)
                                creator_res = await db.execute(creator_stmt)
                                creator = creator_res.scalar_one_or_none()
                                
                                if not creator:
                                    creator = User(id=creator_id, username="creator", nickname="Creator")
                                    db.add(creator)
                                    await db.flush()
                                
                                creator.coins += 20000
                                await db.commit()
                                
                                spammer_mention = user.mention_html()
                                # Tag person and tell they are fined
                                await event.answer(
                                    f"⚠️ {spammer_mention} you are fined 20k coins for your behaviour",
                                    parse_mode="HTML"
                                )
                                
                                # Send DM confirmation to bot owner
                                bot = data.get("bot") or event.bot
                                if bot:
                                    try:
                                        spammer_username_display = f"@{user.username}" if user.username else f"ID {user_id}"
                                        await bot.send_message(
                                            chat_id=creator_id,
                                            text=f"💸 <b>Anti-Flood Spam Fine Transferred!</b>\n"
                                                 f"───────────────\n"
                                                 f"<blockquote>👤 Spammer: <b>{spammer_username_display}</b>\n"
                                                 f"💰 Fine: <b>+20k coins</b> (transferred to your balance)</blockquote>",
                                            parse_mode="HTML"
                                        )
                                    except Exception as dm_err:
                                        print(f"Failed to DM creator about anti-flood fine: {dm_err}")
                        except Exception as err:
                            await db.rollback()
                            print(f"Error executing anti-flood fine: {err}")
                return None  # Stop handler execution for this message

        # 2. Skip counting stickers for spawns
        if event.sticker:
            return await handler(event, data)

        # Skip counting bot commands to prevent spam exploits
        is_command = (event.text and event.text.startswith("/")) or (event.caption and event.caption.startswith("/"))
        if is_command:
            return await handler(event, data)

        db: AsyncSession = data.get("db")
        if not db:
            return await handler(event, data)

        chat_id = chat.id

        # Track user chat activity and rankings
        try:
            await track_user_chat_activity(db, chat_id, user, event)
        except Exception as track_err:
            print(f"Error tracking user chat activity: {track_err}")

        # 3. Retrieve or initialize Group Settings from cache
        if chat_id not in group_settings_cache:
            stmt = select(GroupSetting).where(GroupSetting.chat_id == chat_id)
            res = await db.execute(stmt)
            setting = res.scalar_one_or_none()

            if not setting:
                setting = GroupSetting(
                    chat_id=chat_id,
                    message_counter=0,
                    spawn_threshold=random.randint(50, 100),
                    enabled=True
                )
                db.add(setting)
                await db.commit()

            group_settings_cache[chat_id] = {
                "spawn_threshold": setting.spawn_threshold,
                "enabled": setting.enabled
            }

        cached_setting = group_settings_cache[chat_id]

        if cached_setting["enabled"]:
            # Auto-migrate/update old small thresholds on the fly in cache
            if cached_setting["spawn_threshold"] < 30:
                cached_setting["spawn_threshold"] = random.randint(50, 100)
                
            threshold = cached_setting["spawn_threshold"]
            current_count = group_message_counters.get(chat_id, 0) + 1
            
            if current_count >= threshold:
                # Immediately reset counter so subsequent messages count towards next spawn
                group_message_counters[chat_id] = 0
                # Set new random spawn threshold for variety
                cached_setting["spawn_threshold"] = random.randint(50, 100)
                
                bot = data.get("bot")
                # Trigger wild spawn
                await SpawnService.trigger_spawn(db, chat_id, bot)
            else:
                group_message_counters[chat_id] = current_count

        return await handler(event, data)


async def track_user_chat_activity(db: AsyncSession, chat_id: int, user, event: Message):
    if not user or user.is_bot:
        return
    user_id = user.id
    now_dt = datetime.utcnow()
    today_str = now_dt.strftime("%Y-%m-%d")
    week_str = now_dt.strftime("%Y-%W")
    month_str = now_dt.strftime("%Y-%m")

    from database.models import ChatMessageStat
    stmt = select(ChatMessageStat).where(
        ChatMessageStat.user_id == user_id,
        ChatMessageStat.chat_id == chat_id
    )
    res = await db.execute(stmt)
    stat = res.scalar_one_or_none()

    if not stat:
        stat = ChatMessageStat(
            user_id=user_id,
            chat_id=chat_id,
            daily_count=1,
            weekly_count=1,
            monthly_count=1,
            overall_count=1,
            last_daily_reset=today_str,
            last_weekly_reset=week_str,
            last_monthly_reset=month_str
        )
        db.add(stat)
        await db.commit()
        return

    # Check reset periods
    # 1. Weekly Reset Check & Reward
    if stat.last_weekly_reset and stat.last_weekly_reset != week_str:
        top_weekly_stmt = (
            select(ChatMessageStat)
            .where(ChatMessageStat.chat_id == chat_id)
            .order_by(ChatMessageStat.weekly_count.desc())
            .limit(1)
        )
        top_res = await db.execute(top_weekly_stmt)
        topper_stat = top_res.scalar_one_or_none()
        if topper_stat and topper_stat.user_id == user_id and stat.weekly_count > 10:
            await reward_chat_topper(db, chat_id, user_id, "Weekly", stat.weekly_count, event)

        stat.weekly_count = 1
        stat.last_weekly_reset = week_str
    else:
        stat.weekly_count += 1

    # 2. Monthly Reset Check & Reward
    if stat.last_monthly_reset and stat.last_monthly_reset != month_str:
        top_monthly_stmt = (
            select(ChatMessageStat)
            .where(ChatMessageStat.chat_id == chat_id)
            .order_by(ChatMessageStat.monthly_count.desc())
            .limit(1)
        )
        top_res = await db.execute(top_monthly_stmt)
        topper_stat = top_res.scalar_one_or_none()
        if topper_stat and topper_stat.user_id == user_id and stat.monthly_count > 50:
            await reward_chat_topper(db, chat_id, user_id, "Monthly", stat.monthly_count, event)

        stat.monthly_count = 1
        stat.last_monthly_reset = month_str
    else:
        stat.monthly_count += 1

    # 3. Daily Reset Check
    if stat.last_daily_reset != today_str:
        stat.daily_count = 1
        stat.last_daily_reset = today_str
    else:
        stat.daily_count += 1

    stat.overall_count += 1
    await db.commit()


async def reward_chat_topper(db: AsyncSession, chat_id: int, user_id: int, period: str, count: int, event: Message):
    """Gifts a random Art/AMV or Custom Form Pokemon to the weekly/monthly chat topper."""
    from database.models import User, Pokemon, UserPokemon, PokemonFormMedia
    import random

    # Get random Art/AMV or form entry from PokemonFormMedia
    stmt = select(PokemonFormMedia).order_by(func.random()).limit(1)
    res = await db.execute(stmt)
    pfm = res.scalar_one_or_none()

    if pfm:
        pokemon_id = pfm.pokemon_id
        form_index = pfm.form_index
    else:
        pokemon_id = random.randint(1, 151)
        form_index = 1

    # Fetch Pokemon details
    p_stmt = select(Pokemon).where(Pokemon.id == pokemon_id)
    p_res = await db.execute(p_stmt)
    pokemon = p_res.scalar_one_or_none()
    if not pokemon:
        return

    # Add reward Pokemon to winner's inventory
    reward_poke = UserPokemon(
        user_id=user_id,
        pokemon_id=pokemon.id,
        form_index=form_index,
        is_amv=(form_index == 1),
        is_shiny=False,
        level=100,
        serial_number="#TOPPER"
    )
    db.add(reward_poke)
    await db.commit()

    # Announce in group
    user_stmt = select(User).where(User.id == user_id)
    user_res = await db.execute(user_stmt)
    topper_user = user_res.scalar_one_or_none()
    topper_name = topper_user.nickname if topper_user else "Trainer"

    from utils.settings import get_custom_rarity_forms
    custom_forms = await get_custom_rarity_forms(db)
    from handlers.profile import get_form_label
    form_lbl = get_form_label(form_index, pfm.media_value if pfm else None, custom_forms)

    try:
        await event.answer(
            f"👑 <b>{period.upper()} CHAT TOPPER CROWNED!</b> 👑\n"
            f"───────────────\n"
            f"<blockquote>👤 Trainer: <b>{html.escape(topper_name)}</b>\n"
            f"📊 Activity: <b>{count:,} messages</b> sent this {period.lower()}!\n\n"
            f"🎨 <b>REWARD GIFT</b>: <b>{pokemon.name.title()} ({form_lbl})</b> added directly to inventory! 🎉</blockquote>",
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Error sending chat topper announcement: {e}")
