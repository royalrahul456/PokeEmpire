import os
import json
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import User

DATA_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "user_streaks.json")

# Lock to prevent concurrent JSON read/write issues
_lock = asyncio.Lock()

def _load_streaks() -> Dict[str, Dict[str, Any]]:
    if not os.path.exists(DATA_FILE):
        return {}
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_streaks(data: Dict[str, Dict[str, Any]]):
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

async def get_streak_data(user_id: int) -> Dict[str, Any]:
    """Retrieve streak data for a user and perform daily break checks."""
    async with _lock:
        data = _load_streaks()
        u_str = str(user_id)
        
        today = datetime.utcnow().date().isoformat()
        yesterday = (datetime.utcnow() - timedelta(days=1)).date().isoformat()
        
        u_data = data.get(u_str, {
            "current_streak": 0,
            "best_streak": 0,
            "last_secured_date": "",
            "last_catch_date": "",
            "catches_today": 0
        })
        
        # Check if the streak was broken
        last_sec = u_data.get("last_secured_date", "")
        if last_sec != today and last_sec != yesterday:
            u_data["current_streak"] = 0
            
        # Reset catches_today if we are on a new day
        if u_data.get("last_catch_date", "") != today:
            u_data["catches_today"] = 0
            
        # Ensure new fields are initialized
        if "best_streak" not in u_data:
            u_data["best_streak"] = u_data["current_streak"]
            
        data[u_str] = u_data
        _save_streaks(data)
        return u_data

async def increment_streak_catch(user_id: int) -> Tuple[bool, int]:
    """Increments the daily catch count and returns (secured_today, current_count)."""
    async with _lock:
        data = _load_streaks()
        u_str = str(user_id)
        
        today = datetime.utcnow().date().isoformat()
        yesterday = (datetime.utcnow() - timedelta(days=1)).date().isoformat()
        
        u_data = data.get(u_str, {
            "current_streak": 0,
            "best_streak": 0,
            "last_secured_date": "",
            "last_catch_date": "",
            "catches_today": 0
        })
        
        # Check if streak was broken before starting today's action
        last_sec = u_data.get("last_secured_date", "")
        if last_sec != today and last_sec != yesterday:
            u_data["current_streak"] = 0
            
        # Handle day transition for catching
        if u_data.get("last_catch_date", "") != today:
            u_data["catches_today"] = 1
            u_data["last_catch_date"] = today
        else:
            u_data["catches_today"] += 1
            
        secured_today = False
        if u_data["catches_today"] == 3:
            if u_data.get("last_secured_date", "") != today:
                if u_data.get("last_secured_date", "") == yesterday:
                    u_data["current_streak"] += 1
                else:
                    u_data["current_streak"] = 1
                
                u_data["last_secured_date"] = today
                u_data["best_streak"] = max(u_data.get("best_streak", 0), u_data["current_streak"])
                secured_today = True
                
        data[u_str] = u_data
        _save_streaks(data)
        return secured_today, u_data["catches_today"]

def get_streak_rank(streak: int) -> str:
    """Get the visual title associated with the user's current streak."""
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

async def get_top_streaks(limit: int = 10) -> list:
    """Get top users by best streak."""
    async with _lock:
        data = _load_streaks()
    
    # Sort users by best streak
    sorted_users = sorted(
        [(int(uid), uinfo) for uid, uinfo in data.items()],
        key=lambda x: x[1].get("best_streak", 0),
        reverse=True
    )
    return sorted_users[:limit]
