from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from utils.cooldowns import cooldowns

class AntiSpamMiddleware(BaseMiddleware):
    """aiogram Middleware that restricts users from firing handlers too rapidly (0.5s global throttle)."""
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        # Extract the user from the update
        user = data.get("event_from_user")
        if not user:
            return await handler(event, data)

        # Do not throttle normal chat messages (only throttle commands and callbacks)
        if isinstance(event, Message):
            is_command = (event.text and event.text.startswith("/")) or (event.caption and event.caption.startswith("/"))
            if not is_command:
                return await handler(event, data)

        user_id = user.id
        action = "global_anti_spam"
        
        # Check if the user is spamming commands/buttons
        remaining = cooldowns.get_remaining_time(user_id, action)
        if remaining > 0.0:
            # If it's a callback click, alert the user quietly
            if isinstance(event, CallbackQuery):
                try:
                    await event.answer("⚠️ Slow down! Please wait a moment between actions.", show_alert=False)
                except Exception:
                    pass
            # Stop the handler from running
            return

        # Set a quick 0.5-second throttle
        cooldowns.set_cooldown(user_id, action, 0.5)
        
        return await handler(event, data)
