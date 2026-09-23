import random
import time
import html
from datetime import datetime
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from typing import Callable, Dict, Any, Awaitable
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
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

        db: AsyncSession = data.get("db")
        user = event.from_user
        raw_text = event.text or event.caption or ""
        is_command = bool(raw_text and raw_text.strip().startswith("/"))

        # Commands bypass spam/ban word checks and spawn counting directly to handler
        if is_command:
            return await handler(event, data)

        try:
            # 1. Banned Words Detection (for regular messages)
            if user and not user.is_bot and raw_text:
                user_id = user.id
                from utils.ban_words import check_text_for_ban_words
                matched_word = check_text_for_ban_words(raw_text)
                if matched_word:
                    # Try to delete bad word message
                    try:
                        await event.delete()
                    except Exception as e:
                        print(f"Failed to delete bad word message: {e}")
                        
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
                    return None  # Stop handler execution for bad word message

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
                                    await event.answer(
                                        f"⚠️ {spammer_mention} you are fined 20k coins for your behaviour",
                                        parse_mode="HTML"
                                    )
                                    
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
                    return None  # Stop handler execution for flood message

            # 3. In-memory activity tracking for leaderboard stats
            if user and not user.is_bot:
                try:
                    track_user_chat_activity(chat.id, user, event)
                except Exception as track_err:
                    print(f"Error tracking user chat activity: {track_err}")

            # 4. Skip counting stickers for wild spawns
            if event.sticker:
                return await handler(event, data)

            # 5. Wild Spawn Progress Counter
            if db:
                chat_id = chat.id

                # Retrieve or initialize Group Settings from cache
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
                        
                        bot = data.get("bot") or event.bot
                        thread_id = getattr(event, "message_thread_id", None)
                        # Trigger wild spawn
                        await SpawnService.trigger_spawn(db, chat_id, bot, message_thread_id=thread_id)
                    else:
                        group_message_counters[chat_id] = current_count

        except Exception as e:
            print(f"Unhandled error in GroupActivityMiddleware: {e}")

        return await handler(event, data)


# In-memory buffer: (chat_id, user_id) -> message count delta
chat_activity_buffer: Dict[tuple, int] = {}
# user_id -> (username, first_name)
user_info_buffer: Dict[int, tuple] = {}
# chat_id -> event reference for reset announcements
chat_event_cache: Dict[int, Message] = {}


def track_user_chat_activity(chat_id: int, user, event: Message = None):
    """Instant in-memory buffering without synchronous DB queries."""
    if not user or user.is_bot:
        return
    user_id = user.id
    pair = (chat_id, user_id)
    chat_activity_buffer[pair] = chat_activity_buffer.get(pair, 0) + 1
    user_info_buffer[user_id] = (user.username, user.first_name)
    if event:
        chat_event_cache[chat_id] = event


async def flush_chat_activity(target_chat_id: int = None):
    """Flushes buffered chat activity to the database in a single batch."""
    global chat_activity_buffer
    if not chat_activity_buffer:
        return

    if target_chat_id is not None:
        items_to_flush = {k: v for k, v in chat_activity_buffer.items() if k[0] == target_chat_id}
        for k in items_to_flush:
            chat_activity_buffer.pop(k, None)
    else:
        items_to_flush = dict(chat_activity_buffer)
        chat_activity_buffer.clear()

    if not items_to_flush:
        return

    from database.database import SessionLocal
    from database.models import User, ChatMessageStat

    now_dt = datetime.utcnow()
    today_str = now_dt.strftime("%Y-%m-%d")
    week_str = now_dt.strftime("%Y-%W")
    month_str = now_dt.strftime("%Y-%m")

    async with SessionLocal() as db:
        try:
            # 1. Ensure all buffered users exist in DB
            user_ids = list({uid for (_, uid) in items_to_flush.keys()})
            if user_ids:
                u_stmt = select(User.id).where(User.id.in_(user_ids))
                u_res = await db.execute(u_stmt)
                existing_uids = set(u_res.scalars().all())

                for uid in user_ids:
                    if uid not in existing_uids:
                        uname, nname = user_info_buffer.get(uid, (None, "Trainer"))
                        db.add(User(
                            id=uid,
                            username=uname,
                            nickname=nname or uname or "Trainer",
                            coins=500
                        ))
                await db.flush()

            # 2. Update/insert ChatMessageStats
            for (c_id, u_id), delta in items_to_flush.items():
                stmt = select(ChatMessageStat).where(
                    ChatMessageStat.chat_id == c_id,
                    ChatMessageStat.user_id == u_id
                )
                res = await db.execute(stmt)
                stat = res.scalar_one_or_none()

                if not stat:
                    stat = ChatMessageStat(
                        user_id=u_id,
                        chat_id=c_id,
                        daily_count=delta,
                        weekly_count=delta,
                        monthly_count=delta,
                        overall_count=delta,
                        last_daily_reset=today_str,
                        last_weekly_reset=week_str,
                        last_monthly_reset=month_str
                    )
                    db.add(stat)
                else:
                    # Weekly Reset Check & Reward
                    if stat.last_weekly_reset and stat.last_weekly_reset != week_str:
                        top_weekly_stmt = (
                            select(ChatMessageStat)
                            .where(ChatMessageStat.chat_id == c_id)
                            .order_by(ChatMessageStat.weekly_count.desc())
                            .limit(1)
                        )
                        top_res = await db.execute(top_weekly_stmt)
                        topper_stat = top_res.scalar_one_or_none()
                        ev = chat_event_cache.get(c_id)
                        if topper_stat and topper_stat.user_id == u_id and stat.weekly_count > 10 and ev:
                            await reward_chat_topper(db, c_id, u_id, "Weekly", stat.weekly_count, ev)

                        stat.weekly_count = delta
                        stat.last_weekly_reset = week_str
                    else:
                        stat.weekly_count += delta

                    # Monthly Reset Check & Reward
                    if stat.last_monthly_reset and stat.last_monthly_reset != month_str:
                        top_monthly_stmt = (
                            select(ChatMessageStat)
                            .where(ChatMessageStat.chat_id == c_id)
                            .order_by(ChatMessageStat.monthly_count.desc())
                            .limit(1)
                        )
                        top_res = await db.execute(top_monthly_stmt)
                        topper_stat = top_res.scalar_one_or_none()
                        ev = chat_event_cache.get(c_id)
                        if topper_stat and topper_stat.user_id == u_id and stat.monthly_count > 50 and ev:
                            await reward_chat_topper(db, c_id, u_id, "Monthly", stat.monthly_count, ev)

                        stat.monthly_count = delta
                        stat.last_monthly_reset = month_str
                    else:
                        stat.monthly_count += delta

                    # Daily Reset Check
                    if stat.last_daily_reset != today_str:
                        stat.daily_count = delta
                        stat.last_daily_reset = today_str
                    else:
                        stat.daily_count += delta

                    stat.overall_count += delta

            await db.commit()
        except Exception as e:
            await db.rollback()
            print(f"Error flushing chat activity: {e}")


async def start_chat_activity_worker():
    """Periodic background task that flushes in-memory chat activity every 20 seconds."""
    import asyncio
    print("🚀 Background Chat Activity Batch Worker Started (20s flush interval)...")
    while True:
        try:
            await asyncio.sleep(20)
            await flush_chat_activity()
        except asyncio.CancelledError:
            await flush_chat_activity()
            break
        except Exception as e:
            print(f"Error in chat activity worker loop: {e}")


async def reward_chat_topper(db: AsyncSession, chat_id: int, user_id: int, period: str, count: int, event: Message):
    """Gifts a shiny or normal Legendary or Mythical Pokemon (Form 0 only) to the weekly/monthly chat topper."""
    from database.models import User, Pokemon, UserPokemon
    from utils.formatters import get_rarity_emoji
    import random

    # Select random Legendary or Mythical Pokemon (Base form 0 only)
    stmt = (
        select(Pokemon)
        .where(Pokemon.rarity.in_(["Legendary", "Mythical"]))
        .order_by(func.random())
        .limit(1)
    )
    res = await db.execute(stmt)
    pokemon = res.scalar_one_or_none()

    if not pokemon:
        # Fallback to Mewtwo / Mew / ID 150 / 151 if table empty
        stmt_fb = select(Pokemon).where(Pokemon.id.in_([150, 151])).order_by(func.random()).limit(1)
        res_fb = await db.execute(stmt_fb)
        pokemon = res_fb.scalar_one_or_none()
        if not pokemon:
            return

    form_index = 0
    is_amv = False
    is_shiny = random.choice([True, False])  # 50% chance Shiny or Normal

    # Add reward Pokemon to winner's inventory
    reward_poke = UserPokemon(
        user_id=user_id,
        pokemon_id=pokemon.id,
        form_index=form_index,
        is_amv=is_amv,
        is_shiny=is_shiny,
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

    r_emoji = get_rarity_emoji(pokemon.rarity or "Legendary")
    shiny_tag = "✨ Shiny " if is_shiny else ""

    try:
        await event.answer(
            f"👑 <b>{period.upper()} CHAT TOPPER CROWNED!</b> 👑\n"
            f"───────────────\n"
            f"<blockquote>👤 Trainer: <b>{html.escape(topper_name)}</b>\n"
            f"📊 Activity: <b>{count:,} messages</b> sent this {period.lower()}!\n\n"
            f"🎁 <b>REWARD GIFT</b>: {r_emoji} <b>{shiny_tag}{pokemon.name.title()}</b> added directly to inventory! 🎉</blockquote>",
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Error sending chat topper announcement: {e}")
