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

_lock = asyncio.Lock()

async def get_streak_data(user_id: int, db: Optional[AsyncSession] = None) -> Dict[str, Any]:
    """Retrieve streak data for a user directly from DB with daily break checks."""
    async with _lock:
        today = datetime.utcnow().date().isoformat()
        yesterday = (datetime.utcnow() - timedelta(days=1)).date().isoformat()

        async def _process(session: AsyncSession):
            stmt = select(User).where(User.id == user_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()

            if not user:
                return {
                    "current_streak": 0,
                    "best_streak": 0,
                    "last_secured_date": "",
                    "last_catch_date": "",
                    "catches_today": 0
                }

            # Check streak breaks
            last_sec = user.last_secured_date or ""
            if last_sec and last_sec != today and last_sec != yesterday:
                user.current_streak = 0

            if user.last_catch_date != today:
                user.catches_today = 0

            await session.commit()
            return {
                "current_streak": user.current_streak,
                "best_streak": user.best_streak,
                "last_secured_date": user.last_secured_date or "",
                "last_catch_date": user.last_catch_date or "",
                "catches_today": user.catches_today
            }

        if db:
            return await _process(db)
        else:
            async with SessionLocal() as session:
                return await _process(session)

async def increment_streak_catch(user_id: int, db: Optional[AsyncSession] = None) -> Tuple[bool, int]:
    """Increments daily catch count in DB and returns (secured_today, current_count)."""
    async with _lock:
        today = datetime.utcnow().date().isoformat()
        yesterday = (datetime.utcnow() - timedelta(days=1)).date().isoformat()

        async def _process(session: AsyncSession):
            stmt = select(User).where(User.id == user_id)
            res = await session.execute(stmt)
            user = res.scalar_one_or_none()

            if not user:
                user = User(id=user_id, nickname="Trainer")
                session.add(user)
                await session.flush()

            # Check streak break before todays action
            last_sec = user.last_secured_date or ""
            if last_sec and last_sec != today and last_sec != yesterday:
                user.current_streak = 0

            # Handle day transition for catching
            if user.last_catch_date != today:
                user.catches_today = 1
                user.last_catch_date = today
            else:
                user.catches_today += 1

            secured_today = False
            if user.catches_today == 3:
                if (user.last_secured_date or "") != today:
                    if (user.last_secured_date or "") == yesterday:
                        user.current_streak += 1
                    else:
                        user.current_streak = 1
                    
                    user.last_secured_date = today
                    user.best_streak = max(user.best_streak, user.current_streak)
                    secured_today = True

            await session.commit()
            return secured_today, user.catches_today

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
