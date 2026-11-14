# -*- coding: utf-8 -*-
"""
Fast in-memory ban cache for the bot-level user ban system.
The cache is populated on bot startup from the DB, then kept in sync via
add_ban() / remove_ban() when owner commands run.
Also links to temporary bans via utils.temp_ban.
"""
from typing import Set

# In-memory set of permanently banned user IDs (BigInt Telegram IDs)
_banned_ids: Set[int] = set()


def is_banned(user_id: int) -> bool:
    """Returns True if the user is currently permanently banned from using the bot."""
    return user_id in _banned_ids


def add_ban(user_id: int) -> None:
    """Mark a user as permanently banned in the in-memory cache."""
    _banned_ids.add(user_id)


def remove_ban(user_id: int) -> None:
    """Remove a user's permanent ban from the in-memory cache and lift any active temp ban."""
    _banned_ids.discard(user_id)
    try:
        from utils.temp_ban import remove_temp_ban
        remove_temp_ban(user_id)
    except Exception:
        pass


async def load_bans_from_db() -> None:
    """Called once at bot startup to populate the in-memory cache from the DB."""
    global _banned_ids
    try:
        from database.database import SessionLocal
        from database.models import BannedUser
        from sqlalchemy import select
        async with SessionLocal() as db:
            res = await db.execute(select(BannedUser.user_id))
            _banned_ids = set(res.scalars().all())
        print(f"🚫 Ban cache loaded: {len(_banned_ids)} banned user(s).")
    except Exception as e:
        print(f"⚠️ Could not load ban cache from DB: {e}")
