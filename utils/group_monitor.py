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
            if event.text:
                from utils.ban_words import check_text_for_ban_words
                matched_word = check_text_for_ban_words(event.text)
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
                            
                            if spammer:
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
                                    
                                    spammer_display = f"@{html.escape(user.username)}" if user.username else f"<b>{html.escape(user.first_name)}</b>"
                                    
                                    # Send warning to chat
                                    await event.answer(
                                        f"⚠️ <b>BAD WORD DETECTED!</b> ⚠️\n"
                                        f"<blockquote>👤 Trainer: <b>{spammer_display}</b>\n"
                                        f"💸 Fine: <b>50,000 coins</b> (transferred to Bot Creator)</blockquote>\n"
                                        f"<i>Using inappropriate words is prohibited. Keep the chat clean!</i>",
                                        parse_mode="HTML"
                                    )
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
            
            # Trigger fine if they sent more than 5 messages in 3 seconds
            # Cooldown of 10 seconds between fines to prevent repeat alerts
            if len(times) > 5 and now - last_fine_time.get(user_id, 0) > 10.0:
                last_fine_time[user_id] = now
                
                db: AsyncSession = data.get("db")
                if db:
                    try:
                        # Spammer User
                        spammer_stmt = select(User).where(User.id == user_id)
                        spammer_res = await db.execute(spammer_stmt)
                        spammer = spammer_res.scalar_one_or_none()
                        
                        if spammer:
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
                                
                                spammer_display = f"@{html.escape(user.username)}" if user.username else f"<b>{html.escape(user.first_name)}</b>"
                                
                                await event.reply(
                                    f"⚠️ <b>ANTI-FLOOD ALERT!</b> ⚠️\n"
                                    f"<blockquote>👤 Trainer: <b>{spammer_display}</b>\n"
                                    f"💸 Fine: <b>20,000 coins</b> (transferred to Bot Creator)</blockquote>\n"
                                    f"<i>Flooding the chat is prohibited. Please slow down!</i>",
                                    parse_mode="HTML"
                                )
                    except Exception as err:
                        await db.rollback()
                        print(f"Error executing anti-flood fine: {err}")

        # 2. Skip counting stickers for spawns
        if event.sticker:
            return await handler(event, data)

        # Skip counting bot commands to prevent spam exploits
        if event.text and event.text.startswith("/"):
            return await handler(event, data)

        db: AsyncSession = data.get("db")
        if not db:
            return await handler(event, data)

        chat_id = chat.id

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
                bot = data.get("bot")
                # Trigger wild spawn
                await SpawnService.trigger_spawn(db, chat_id, bot)
                # Reset counter
                current_count = 0

            group_message_counters[chat_id] = current_count

        return await handler(event, data)
