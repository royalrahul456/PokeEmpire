from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from utils.cooldowns import cooldowns
from utils.ban_check import is_banned
from utils.maintenance import (
    is_maintenance_mode,
    is_maintenance_exempt,
    should_warn_maintenance,
    get_maintenance_message,
)
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
    2. Enforces bot maintenance mode for non-exempt users.
    3. Throttles rapid button clicks (CallbackQuery) per bot instance without dropping human commands.
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

        user_id = user.id

        # ── 0. Exempt Owners, Co-Owners, Developers, and Admins from any ban or throttle ──
        is_exempt = (
            user_id in getattr(config, "OWNER_IDS", [])
            or user_id in getattr(config, "CO_OWNER_IDS", [])
            or user_id in getattr(config, "DEV_IDS", [])
            or user_id in getattr(config, "ADMIN_IDS", [])
        )

        # ── 1. Ban Check (owner-level bot ban) ────────────────────────────────
        if is_banned(user_id) and not is_exempt:
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

        # ── 2. Maintenance Mode Check ─────────────────────────────────────────
        if is_maintenance_mode() and not is_maintenance_exempt(user_id):
            if isinstance(event, Message):
                raw_t = (event.text or event.caption or "").strip()
                is_command = raw_t.startswith("/")
                is_private = bool(event.chat and event.chat.type == "private")
                if is_command or is_private:
                    if should_warn_maintenance(user_id, event.chat.id):
                        try:
                            await event.answer(get_maintenance_message(), parse_mode="HTML")
                        except Exception:
                            pass
                return
            elif isinstance(event, CallbackQuery):
                try:
                    await event.answer(
                        "🚧 PokéEmpire is currently under maintenance.\nOnly Owner, Co-Owner & Developers can use it.",
                        show_alert=True
                    )
                except Exception:
                    pass
                return

        # Exempt users bypass throttling completely
        if is_exempt:
            return await handler(event, data)

        # ── 3. Anti-Spam throttle (CallbackQuery buttons only) ────────────────
        # Human Message commands are NEVER silently dropped!
        if isinstance(event, CallbackQuery):
            bot_obj = getattr(event, "bot", None) or data.get("bot")
            bot_id = getattr(bot_obj, "id", "default")
            action = f"btn_spam_{bot_id}"
            
            remaining = cooldowns.get_remaining_time(user_id, action)
            if remaining > 0.0:
                try:
                    await event.answer("⚠️ Slow down! Please wait a moment between actions.", show_alert=False)
                except Exception:
                    pass
                return
            cooldowns.set_cooldown(user_id, action, 0.1)

        return await handler(event, data)
