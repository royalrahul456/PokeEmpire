# -*- coding: utf-8 -*-
import html
import asyncio
from typing import Callable, Dict, Any, Awaitable, Optional
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery
from utils.cooldowns import cooldowns
from utils.ban_check import is_banned
from utils.temp_ban import (
    is_temp_banned,
    apply_temp_ban,
    format_duration,
    record_and_check_reward_spam,
    should_notify_temp_ban,
    notify_owners_temp_ban,
    SPAM_TRIGGER_COMMANDS,
)
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


def _extract_command_name(text: Optional[str]) -> str:
    """Extracts base command name from raw message text (e.g. '/claim@PokeEmpireBot arg' -> 'claim')."""
    if not text:
        return ""
    stripped = text.strip()
    if not stripped.startswith("/"):
        return ""
    first_token = stripped.split()[0][1:]
    return first_token.split("@")[0].lower()


class AntiSpamMiddleware(BaseMiddleware):
    """aiogram Middleware that:
    1. Blocks globally banned users from all commands / callbacks.
    2. Enforces temporary bot bans for users caught spamming reward commands (claim, daily, spin).
    3. Detects and intercepts reward command spamming, automatically issuing temporary bot bans.
    4. Enforces bot maintenance mode for non-exempt users.
    5. Throttles rapid button clicks (CallbackQuery) per bot instance without dropping human commands.
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

        # ── 1. Permanent Ban Check (owner-level bot ban) ──────────────────────
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

        # ── 1.1. Temporary Ban Check (Anti-Spam temp ban) ─────────────────────
        is_tb, remaining_secs, tb_info = is_temp_banned(user_id)
        if is_tb and not is_exempt:
            if isinstance(event, Message):
                raw_t = (event.text or event.caption or "").strip()
                is_command = raw_t.startswith("/")
                is_private = bool(event.chat and event.chat.type == "private")
                if is_command or is_private:
                    chat_id = event.chat.id if event.chat else user_id
                    if should_notify_temp_ban(user_id, chat_id):
                        rem_str = format_duration(remaining_secs)
                        reason = tb_info.get("reason", "Spamming reward commands")
                        msg = (
                            f"⏳ <b>TEMPORARY BOT BAN ACTIVE</b>\n"
                            f"◈ ────────────────────────── ◈\n"
                            f"👤 <b>Trainer:</b> {html.escape(user.full_name or 'Trainer')} (<code>{user_id}</code>)\n"
                            f"⏱️ <b>Time Remaining:</b> <b>{rem_str}</b>\n"
                            f"📋 <b>Reason:</b> <i>{html.escape(reason)}</i>\n"
                            f"◈ ────────────────────────── ◈\n"
                            f"<i>You are temporarily blocked from using PokéEmpire. Your access will automatically be restored when the timer expires.</i>"
                        )
                        try:
                            await event.answer(msg, parse_mode="HTML")
                        except Exception:
                            pass
                return
            elif isinstance(event, CallbackQuery):
                rem_str = format_duration(remaining_secs)
                try:
                    await event.answer(
                        f"⏳ You are temporarily banned for spamming.\nTime remaining: {rem_str}",
                        show_alert=True
                    )
                except Exception:
                    pass
                return

        # ── 1.2. Anti-Spam Detection for claim / daily / spin ─────────────────
        if not is_exempt:
            bot_obj = getattr(event, "bot", None) or data.get("bot")

            # A) Check Message commands
            if isinstance(event, Message):
                raw_text = (event.text or event.caption or "").strip()
                cmd_name = _extract_command_name(raw_text)
                if cmd_name in SPAM_TRIGGER_COMMANDS:
                    action, count = record_and_check_reward_spam(user_id, cmd_name)
                    if action == "BAN":
                        tb_record = apply_temp_ban(
                            user_id=user_id,
                            reason=f"Spamming /{cmd_name} command ({count} attempts in 5s)",
                            username=user.username,
                            chat_id=event.chat.id if event.chat else None,
                            chat_title=event.chat.title if event.chat else "Private DM",
                        )
                        duration = tb_record.get("duration_seconds", 1800)
                        dur_str = format_duration(duration)
                        ban_alert = (
                            f"🚨 <b>ANTI-SPAM TEMPORARY BAN ISSUED</b> 🚨\n"
                            f"◈ ────────────────────────── ◈\n"
                            f"👤 <b>Trainer:</b> {html.escape(user.full_name or 'Trainer')} (<code>{user_id}</code>)\n"
                            f"⏱️ <b>Ban Duration:</b> <b>{dur_str}</b>\n"
                            f"📋 <b>Reason:</b> Excessive spamming of <code>/{cmd_name}</code>\n"
                            f"◈ ────────────────────────── ◈\n"
                            f"<i>You have been temporarily blocked from using PokéEmpire. All commands and buttons are disabled until the timer expires.</i>"
                        )
                        try:
                            await event.answer(ban_alert, parse_mode="HTML")
                        except Exception:
                            pass
                        if bot_obj:
                            asyncio.create_task(notify_owners_temp_ban(
                                bot_obj, user, cmd_name, count, duration, event.chat
                            ))
                        return
                    elif action == "WARN":
                        warn_msg = (
                            f"⚠️ <b>ANTI-SPAM WARNING!</b>\n"
                            f"<blockquote>Trainer {html.escape(user.first_name)}, slow down! Continuing to spam <code>/{cmd_name}</code> will result in an <b>immediate temporary ban from using the bot</b>.</blockquote>"
                        )
                        try:
                            await event.answer(warn_msg, parse_mode="HTML")
                        except Exception:
                            pass
                        return

            # B) Check CallbackQuery buttons (play_daily, play_spin, btn_launch_spin)
            elif isinstance(event, CallbackQuery):
                cb_data = (event.data or "").strip()
                if cb_data in {"play_daily", "play_spin", "btn_launch_spin"}:
                    action_key = "daily" if "daily" in cb_data else "spin"
                    action, count = record_and_check_reward_spam(user_id, action_key)
                    if action == "BAN":
                        tb_record = apply_temp_ban(
                            user_id=user_id,
                            reason=f"Spamming {action_key} button ({count} clicks in 5s)",
                            username=user.username,
                            chat_id=getattr(event.message, "chat", None).id if getattr(event, "message", None) and event.message.chat else None,
                            chat_title=getattr(event.message, "chat", None).title if getattr(event, "message", None) and event.message.chat else "Private DM",
                        )
                        duration = tb_record.get("duration_seconds", 1800)
                        dur_str = format_duration(duration)
                        try:
                            await event.answer(
                                f"🚨 Temp-Banned! Spammed {action_key}. Bot access locked for {dur_str}.",
                                show_alert=True
                            )
                        except Exception:
                            pass
                        if bot_obj:
                            asyncio.create_task(notify_owners_temp_ban(
                                bot_obj, user, action_key, count, duration, getattr(event.message, "chat", None)
                            ))
                        return
                    elif action == "WARN":
                        try:
                            await event.answer(
                                f"⚠️ Slow down! Continuing to spam {action_key} will result in a temporary ban.",
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
