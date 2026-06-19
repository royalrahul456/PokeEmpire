import random
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message
from typing import Callable, Dict, Any, Awaitable
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import GroupSetting
from services.spawn_service import SpawnService

class GroupActivityMiddleware(BaseMiddleware):
    """Middleware that counts chat activity and triggers wild Pokémon spawns in groups."""
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

        # Skip counting bot commands to prevent spam exploits
        if event.text and event.text.startswith("/"):
            return await handler(event, data)

        db: AsyncSession = data.get("db")
        if not db:
            return await handler(event, data)

        # Retrieve or initialize Group settings
        stmt = select(GroupSetting).where(GroupSetting.chat_id == chat.id)
        res = await db.execute(stmt)
        setting = res.scalar_one_or_none()

        if not setting:
            setting = GroupSetting(
                chat_id=chat.id,
                message_counter=0,
                spawn_threshold=random.randint(50, 100),
                enabled=True
            )
            db.add(setting)
            await db.commit()

        if setting.enabled:
            # Auto-migrate/update old small thresholds to a valid range on the fly
            if setting.spawn_threshold < 30:
                setting.spawn_threshold = random.randint(50, 100)

            setting.message_counter += 1
            if setting.message_counter >= setting.spawn_threshold:
                bot = data.get("bot")
                # Trigger wild spawn
                await SpawnService.trigger_spawn(db, chat.id, bot)
                
                # Reset counter
                setting.message_counter = 0
                
            await db.commit()

        return await handler(event, data)
