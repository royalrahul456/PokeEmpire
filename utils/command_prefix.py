# -*- coding: utf-8 -*-
from typing import Callable, Dict, Any, Awaitable
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message

COMMAND_ALIASES = {
    "vd": "vipdaily",
    "vc": "vipclaim",
    "vp": "vipplan",
    "cl": "claim",
    "pf": "profile",
    "pr": "profile",
    "sh": "shop",
    "tr": "trade",
    "r": "redeem",
    "c": "check",
    "ch": "check",
    "dex": "pokedex",
    "pd": "pokedex",
    "bal": "balance",
    "lb": "leaderboard",
}

def _apply_aliases(text: str) -> str:
    """Expands short form command aliases (e.g. /vd -> /vipdaily)."""
    if not text.startswith("/"):
        return text
    parts = text[1:].split(maxsplit=1)
    if parts:
        cmd_mention = parts[0]
        cmd, at, mention = cmd_mention.partition("@")
        low_cmd = cmd.lower()
        if low_cmd in COMMAND_ALIASES:
            target_cmd = COMMAND_ALIASES[low_cmd]
            new_cmd_mention = f"{target_cmd}{at}{mention}" if at else target_cmd
            return f"/{new_cmd_mention}" + (f" {parts[1]}" if len(parts) > 1 else "")
    return text

def normalize_command_text(raw_text: str) -> str:
    """
    Normalizes command triggers from alternative prefixes ('.', '!', 'pe ', 'poke ')
    and short form aliases into standard Telegram Bot API '/' commands.
    """
    if not raw_text or not isinstance(raw_text, str):
        return raw_text
    lraw = raw_text.lstrip()
    if not lraw:
        return raw_text

    # 1. Custom prefixes '.' or '!' (must be followed by an alphanumeric character, e.g. .profile, !claim)
    if lraw.startswith((".", "!")) and len(lraw) > 1 and lraw[1].isalnum():
        converted = "/" + lraw[1:]
        return _apply_aliases(converted)

    # 2. Bot short name triggers ('pe' or 'poke' case-insensitive)
    low = lraw.lower()
    if low in ("pe", "poke"):
        return "/help"

    if low.startswith(("pe.", "pe!", "pe/")) and len(lraw) > 3 and lraw[3:].strip():
        converted = "/" + lraw[3:].lstrip()
        return _apply_aliases(converted)

    if low.startswith(("poke.", "poke!", "poke/")) and len(lraw) > 5 and lraw[5:].strip():
        converted = "/" + lraw[5:].lstrip()
        return _apply_aliases(converted)

    if low.startswith(("pe ", "pe\t", "pe\n")):
        remainder = lraw[3:].lstrip()
        if remainder:
            if remainder.startswith(("/", ".", "!")):
                remainder = remainder[1:].lstrip()
            converted = "/" + remainder
            return _apply_aliases(converted)

    if low.startswith(("poke ", "poke\t", "poke\n")):
        remainder = lraw[5:].lstrip()
        if remainder:
            if remainder.startswith(("/", ".", "!")):
                remainder = remainder[1:].lstrip()
            converted = "/" + remainder
            return _apply_aliases(converted)

    # 3. Check existing '/' command for short form aliases
    if lraw.startswith("/"):
        return _apply_aliases(lraw)

    # 4. Direct command words without prefix (e.g. 'check 1', 'c 1', 'check pikachu')
    parts = lraw.split(maxsplit=1)
    if parts:
        first_word = parts[0].lower()
        if first_word in ("check", "pokedex"):
            converted = f"/{first_word}" + (f" {parts[1]}" if len(parts) > 1 else "")
            return _apply_aliases(converted)
        if first_word in ("c", "ch"):
            converted = "/check" + (f" {parts[1]}" if len(parts) > 1 else "")
            return converted

    return raw_text


class CommandPrefixMiddleware(BaseMiddleware):
    """
    Outer middleware that normalizes messages starting with '.', '!', 'pe ', 'poke ',
    'pe.', 'pe!', 'pe/' into standard '/' commands before any filter or handler runs.
    Also expands short command aliases (vd, vc, vp, cl, pf, etc.).
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        if isinstance(event, Message):
            if event.text:
                new_text = normalize_command_text(event.text)
                if new_text != event.text:
                    object.__setattr__(event, "text", new_text)
            elif event.caption:
                new_caption = normalize_command_text(event.caption)
                if new_caption != event.caption:
                    object.__setattr__(event, "caption", new_caption)

        return await handler(event, data)
