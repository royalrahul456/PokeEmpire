import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc
from database.models import User
from database.database import SessionLocal

import config
from collections import defaultdict

_user_locks: Dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)

DATA_DIR = getattr(config, "DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"))
FREEZES_FILE = os.path.join(DATA_DIR, "streak_freezes.json")

_freeze_cache: Dict[str, dict] = {}
_freeze_loaded = False


class StreakCatchResult(tuple):
    """
    Subclass of tuple (secured, current_count, streak_days) providing full backward
    compatibility for existing 3-tuple unpacking while exposing extra frozen metadata.
    """
    def __new__(cls, secured: bool, current_count: int, streak_days: int, was_defrosted: bool = False, was_frozen_saved: bool = False):
        instance = super().__new__(cls, (secured, current_count, streak_days))
        instance._was_defrosted = was_defrosted
        instance._was_frozen_saved = was_frozen_saved
        return instance

    @property
    def secured(self) -> bool:
        return self[0]

    @property
    def current_count(self) -> int:
        return self[1]

    @property
    def streak_days(self) -> int:
        return self[2]

    @property
    def was_defrosted(self) -> bool:
        return getattr(self, "_was_defrosted", False)

    @property
    def was_frozen_saved(self) -> bool:
        return getattr(self, "_was_frozen_saved", False)


def _load_freezes() -> None:
    global _freeze_cache, _freeze_loaded
    if _freeze_loaded:
        return
    if not os.path.exists(FREEZES_FILE):
        _freeze_cache = {}
        _freeze_loaded = True
        return
    try:
        with open(FREEZES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            _freeze_cache = data.get("users", {})
        _freeze_loaded = True
    except Exception as e:
        print(f"[STREAK FREEZE] Error loading {FREEZES_FILE}: {e}")
        _freeze_cache = {}
        _freeze_loaded = True


def _save_freezes() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp_file = f"{FREEZES_FILE}.tmp"
    try:
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump({"users": _freeze_cache, "updated_at": datetime.utcnow().isoformat()}, f, indent=2)
        os.replace(tmp_file, FREEZES_FILE)
    except Exception as e:
        print(f"[STREAK FREEZE] Error saving {FREEZES_FILE}: {e}")
        try:
            if os.path.exists(tmp_file):
                os.remove(tmp_file)
        except Exception:
            pass


def get_freeze_info(user_id: int) -> dict:
    """Gets or initializes the user's freeze record (defaults to 1 free shield available)."""
    _load_freezes()
    uid = str(user_id)
    if uid not in _freeze_cache:
        _freeze_cache[uid] = {
            "freezes_available": 1,
            "frozen_for_date": None,
            "last_freeze_used_date": None,
            "consecutive_secured_days": 0
        }
        _save_freezes()
    return _freeze_cache[uid]


async def get_streak_data(user_id: int, db: Optional[AsyncSession] = None) -> Dict[str, Any]:
    """Retrieve streak data for a user directly from DB with 1-day freeze protection & break checks."""
    async with _user_locks[user_id]:
        today = datetime.utcnow().date().isoformat()
        yesterday = (datetime.utcnow() - timedelta(days=1)).date().isoformat()
        day_before_yesterday = (datetime.utcnow() - timedelta(days=2)).date().isoformat()

        async def _process(session: AsyncSession):
            stmt = select(User).where(User.id == user_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()

            frz = get_freeze_info(user_id)

            if not user:
                return {
                    "current_streak": 0,
                    "best_streak": 0,
                    "last_secured_date": "",
                    "last_catch_date": "",
                    "catches_today": 0,
                    "is_frozen": False,
                    "frozen_date": None,
                    "freezes_available": frz.get("freezes_available", 1),
                    "was_auto_frozen": False
                }

            last_sec = user.last_secured_date or ""
            is_frozen = False
            was_auto_frozen = False

            # Streak break & 1-day freeze check
            if last_sec:
                if last_sec == today:
                    is_frozen = False
                elif last_sec == yesterday:
                    # Active for today. Check if protected by yesterday's freeze
                    if frz.get("frozen_for_date") == yesterday:
                        is_frozen = True
                elif last_sec == day_before_yesterday and user.current_streak > 0:
                    # Missed yesterday! Activate or acknowledge 1-day freeze
                    if frz.get("frozen_for_date") == yesterday:
                        user.last_secured_date = yesterday
                        is_frozen = True
                    elif frz.get("freezes_available", 1) > 0:
                        # Auto-consume 1-day freeze shield to preserve streak
                        frz["freezes_available"] = max(0, frz.get("freezes_available", 1) - 1)
                        frz["frozen_for_date"] = yesterday
                        frz["last_freeze_used_date"] = today
                        frz["consecutive_secured_days"] = 0
                        _save_freezes()

                        user.last_secured_date = yesterday
                        is_frozen = True
                        was_auto_frozen = True
                    else:
                        # No freeze shield available -- streak breaks
                        user.current_streak = 0
                        frz["frozen_for_date"] = None
                        _save_freezes()
                else:
                    # Missed 2 or more days -- streak breaks
                    user.current_streak = 0
                    if frz.get("frozen_for_date"):
                        frz["frozen_for_date"] = None
                        _save_freezes()

            if user.last_catch_date != today:
                user.catches_today = 0

            await session.commit()
            return {
                "current_streak": user.current_streak,
                "best_streak": user.best_streak,
                "last_secured_date": user.last_secured_date or "",
                "last_catch_date": user.last_catch_date or "",
                "catches_today": user.catches_today,
                "is_frozen": is_frozen,
                "frozen_date": frz.get("frozen_for_date"),
                "freezes_available": frz.get("freezes_available", 1),
                "was_auto_frozen": was_auto_frozen
            }

        if db:
            return await _process(db)
        else:
            async with SessionLocal() as session:
                return await _process(session)


async def increment_streak_catch(user_id: int, db: Optional[AsyncSession] = None) -> StreakCatchResult:
    """
    Increments daily catch count in DB. Automatically manages 1-day freeze, defrosts on completion,
    recharges freeze shield on milestones, and returns StreakCatchResult(secured_today, current_count, current_streak).
    """
    async with _user_locks[user_id]:
        today = datetime.utcnow().date().isoformat()
        yesterday = (datetime.utcnow() - timedelta(days=1)).date().isoformat()
        day_before_yesterday = (datetime.utcnow() - timedelta(days=2)).date().isoformat()

        async def _process(session: AsyncSession):
            stmt = select(User).where(User.id == user_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()

            if not user:
                user = User(id=user_id, nickname="Trainer")
                session.add(user)
                await session.flush()

            frz = get_freeze_info(user_id)
            last_sec = user.last_secured_date or ""
            is_frozen = False
            was_frozen_saved = False

            # Check streak break before today's action
            if last_sec:
                if last_sec == today:
                    is_frozen = False
                elif last_sec == yesterday:
                    if frz.get("frozen_for_date") == yesterday:
                        is_frozen = True
                elif last_sec == day_before_yesterday and user.current_streak > 0:
                    if frz.get("frozen_for_date") == yesterday:
                        user.last_secured_date = yesterday
                        is_frozen = True
                    elif frz.get("freezes_available", 1) > 0:
                        frz["freezes_available"] = max(0, frz.get("freezes_available", 1) - 1)
                        frz["frozen_for_date"] = yesterday
                        frz["last_freeze_used_date"] = today
                        frz["consecutive_secured_days"] = 0
                        _save_freezes()

                        user.last_secured_date = yesterday
                        is_frozen = True
                        was_frozen_saved = True
                    else:
                        user.current_streak = 0
                        frz["frozen_for_date"] = None
                        _save_freezes()
                else:
                    user.current_streak = 0
                    if frz.get("frozen_for_date"):
                        frz["frozen_for_date"] = None
                        _save_freezes()

            # Handle day transition for catching
            if user.last_catch_date != today:
                user.catches_today = 1
                user.last_catch_date = today
            else:
                user.catches_today += 1

            secured_today = False
            was_defrosted = False
            if user.catches_today == 3:
                if (user.last_secured_date or "") != today:
                    if is_frozen or (frz.get("frozen_for_date") == yesterday):
                        was_defrosted = True
                        frz["frozen_for_date"] = None
                        frz["consecutive_secured_days"] = 1
                        _save_freezes()

                    if (user.last_secured_date or "") == yesterday:
                        user.current_streak += 1
                    else:
                        user.current_streak = 1
                    
                    user.last_secured_date = today
                    user.best_streak = max(user.best_streak, user.current_streak)
                    secured_today = True

                    # Progress consecutive secured days to recharge shield
                    if not was_defrosted:
                        consec = frz.get("consecutive_secured_days", 0) + 1
                        frz["consecutive_secured_days"] = consec
                        # Replenish freeze shield after 3 days streak maintenance if depleted
                        if consec >= 3 and frz.get("freezes_available", 0) < 1:
                            frz["freezes_available"] = 1
                            frz["consecutive_secured_days"] = 0
                        # Or at 7-day milestones
                        if user.current_streak % 7 == 0 and frz.get("freezes_available", 0) < 2:
                            frz["freezes_available"] = min(2, frz.get("freezes_available", 0) + 1)
                        _save_freezes()

            await session.commit()
            return StreakCatchResult(
                secured_today,
                user.catches_today,
                user.current_streak,
                was_defrosted=was_defrosted,
                was_frozen_saved=was_frozen_saved
            )

        if db:
            return await _process(db)
        else:
            async with SessionLocal() as session:
                return await _process(session)


async def restore_highest_streak(
    user_id: int,
    is_admin: bool = False,
    target_streak: Optional[int] = None,
    db: Optional[AsyncSession] = None
) -> Tuple[bool, str, int]:
    """
    Restores user's current streak back to their highest recorded streak (or target_streak if admin).
    Deducts 5,000 Coins (or 25 PokeGems) for regular users; free for admins.
    Sets last_secured_date to yesterday so today remains open to secure and grow the streak.
    Recharges the 1-Day Freeze shield.
    """
    async with _user_locks[user_id]:
        yesterday = (datetime.utcnow() - timedelta(days=1)).date().isoformat()

        async def _process(session: AsyncSession):
            stmt = select(User).where(User.id == user_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()

            if not user:
                return False, "User not found! Register with /start or catch a Pokémon first.", 0

            # Determine streak to restore to
            if target_streak is not None and target_streak > 0:
                restore_to = target_streak
            else:
                restore_to = user.best_streak

            if restore_to <= 0:
                return False, "You do not have any recorded highest streak to restore! Catch 3 Pokémon today to start your streak.", 0

            if user.current_streak >= restore_to:
                return False, f"Your current streak ({user.current_streak} days) is already at or above your highest streak ({restore_to} days)!", user.current_streak

            # Balance check & deduction if not admin
            if not is_admin:
                cost_coins = 5000
                cost_gems = 25
                if user.coins >= cost_coins:
                    user.coins -= cost_coins
                    try:
                        from utils.trainer_level import log_transaction
                        await log_transaction(user_id, -cost_coins, "STREAK_RESTORE", f"Restored {restore_to}-day streak", session)
                    except Exception:
                        pass
                elif getattr(user, "poke_gems", 0) >= cost_gems:
                    user.poke_gems -= cost_gems
                    try:
                        from utils.trainer_level import log_transaction
                        await log_transaction(user_id, -cost_gems, "STREAK_RESTORE_GEMS", f"Restored {restore_to}-day streak", session)
                    except Exception:
                        pass
                else:
                    return False, (
                        f"Insufficient balance!\n"
                        f"Restoring your highest streak ({restore_to} days) costs 5,000 Coins (or 25 PokeGems).\n"
                        f"• Your Coins: {user.coins:,}\n"
                        f"• Your PokeGems: {getattr(user, 'poke_gems', 0):,}"
                    ), user.current_streak

            # Apply streak restoration
            user.current_streak = restore_to
            user.best_streak = max(user.best_streak, restore_to)
            user.last_secured_date = yesterday

            # Recharge streak freeze shield
            frz = get_freeze_info(user_id)
            frz["freezes_available"] = max(frz.get("freezes_available", 0), 1)
            frz["frozen_for_date"] = None
            frz["consecutive_secured_days"] = 0
            _save_freezes()

            await session.commit()
            return True, f"Successfully restored streak to {restore_to} days!", restore_to

        if db:
            return await _process(db)
        else:
            async with SessionLocal() as session:
                return await _process(session)


async def buy_streak_freeze(user_id: int, db: Optional[AsyncSession] = None) -> Tuple[bool, str, int]:
    """
    Purchases a 1-Day Streak Freeze Shield for 1,500 Coins (or 10 PokeGems). Max 2 shields stored.
    """
    async with _user_locks[user_id]:
        async def _process(session: AsyncSession):
            stmt = select(User).where(User.id == user_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()

            if not user:
                return False, "User not found. Register first with /start!", 0

            frz = get_freeze_info(user_id)
            current_freezes = frz.get("freezes_available", 0)
            if current_freezes >= 2:
                return False, f"You already have the maximum number of Freeze Shields stored (2/2)!", current_freezes

            cost_coins = 1500
            cost_gems = 10
            if user.coins >= cost_coins:
                user.coins -= cost_coins
                try:
                    from utils.trainer_level import log_transaction
                    await log_transaction(user_id, -cost_coins, "FREEZE_BUY", "Purchased 1-Day Streak Freeze Shield", session)
                except Exception:
                    pass
            elif getattr(user, "poke_gems", 0) >= cost_gems:
                user.poke_gems -= cost_gems
                try:
                    from utils.trainer_level import log_transaction
                    await log_transaction(user_id, -cost_gems, "FREEZE_BUY_GEMS", "Purchased 1-Day Streak Freeze Shield", session)
                except Exception:
                    pass
            else:
                return False, (
                    f"Insufficient balance! A Streak Freeze Shield costs 1,500 Coins (or 10 PokeGems).\n"
                    f"• Your Coins: {user.coins:,}\n"
                    f"• Your PokeGems: {getattr(user, 'poke_gems', 0):,}"
                ), current_freezes

            frz["freezes_available"] = current_freezes + 1
            _save_freezes()
            await session.commit()
            return True, f"Successfully purchased 1-Day Streak Freeze Shield! Total shields: {frz['freezes_available']}/2", frz["freezes_available"]

        if db:
            return await _process(db)
        else:
            async with SessionLocal() as session:
                return await _process(session)


def get_streak_rank(streak: int) -> str:
    """Get visual title associated with user's current streak."""
    if streak >= 30:
        return "👑 Diamond Streak"
    elif streak >= 15:
        return "💫 Gold Streak"
    elif streak >= 7:
        return "⚡ Silver Streak"
    elif streak >= 3:
        return "🔥 Bronze Streak"
    else:
        return "🏓 No Streak"


async def get_top_streaks(limit: int = 10, db: Optional[AsyncSession] = None) -> list:
    """Get top users by best streak directly from DB."""
    async def _process(session: AsyncSession):
        stmt = select(User).where(User.best_streak > 0).order_by(desc(User.best_streak)).limit(limit)
        res = await session.execute(stmt)
        users = res.scalars().all()
        return [
            (u.id, {
                "username": u.username,
                "nickname": u.nickname,
                "current_streak": u.current_streak,
                "best_streak": u.best_streak,
                "last_secured_date": u.last_secured_date or "",
                "last_catch_date": u.last_catch_date or "",
                "catches_today": u.catches_today
            })
            for u in users
        ]

    if db:
        return await _process(db)
    else:
        async with SessionLocal() as session:
            return await _process(session)
