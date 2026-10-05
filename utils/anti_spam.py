from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from utils.cooldowns import cooldowns
from utils.ban_check import is_banned
import config

# ── Message shown to banned users ────────────────────────────────────────────
_BAN_MSG = (
    "🚫 <b>You have been banned from using PokeEmpire.</b>\n"
    "◈ ────────────────── ◈\n"
    "<i>If you believe this is a mistake, contact the bot owner.</i>"
)

class AntiSpamMiddleware(BaseMiddleware):
    """aiogram Middleware that:
    1. Blocks globally banned users from all commands / callbacks.
    2. Restricts users from firing handlers too rapidly (0.5 s global throttle).
    """
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

        # ── 1. Ban Check (owner-level bot ban) ────────────────────────────────
        if is_banned(user.id) and user.id not in config.OWNER_IDS:
            if isinstance(event, Message):
                is_command = (event.text and event.text.startswith("/")) or (
                    event.caption and event.caption.startswith("/")
                )
                if is_command:
                    try:
                        await event.answer(_BAN_MSG, parse_mode="HTML")
                    except Exception:
                        pass
                # Silently drop non-command messages from banned users
                return
            elif isinstance(event, CallbackQuery):
                try:
                    await event.answer(
                        "🚫 You are banned from using this bot.",
                        show_alert=True
                    )
                except Exception:
                    pass
                return

        # ── 2. Anti-Spam throttle (commands & callbacks only) ────────────────
        # Do not throttle normal chat messages (only throttle commands and callbacks)
        if isinstance(event, Message):
            raw_t = (event.text or event.caption or "").strip()
            is_command = raw_t.startswith("/")
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

        # Set a quick 0.15-second throttle to block machine-rate flooding without dropping fast human commands
        cooldowns.set_cooldown(user_id, action, 0.15)
        
        return await handler(event, data)

