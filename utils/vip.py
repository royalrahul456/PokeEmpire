from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User
import config

def is_user_vip(user: Optional[User]) -> bool:
    """
    Returns True if the user has an active VIP membership,
    or is an Owner, Co-Owner, or Developer.
    """
    if not user:
        return False

    user_id = getattr(user, "id", None)
    if user_id:
        owner_ids = set(getattr(config, "OWNER_IDS", []))
        co_owner_ids = set(getattr(config, "CO_OWNER_IDS", []))
        dev_ids = set(getattr(config, "DEV_IDS", []))
        if user_id in owner_ids or user_id in co_owner_ids or user_id in dev_ids:
            return True

    if not getattr(user, "is_vip", False):
        return False

    expiry = getattr(user, "vip_expiry", None)
    if not expiry:
        # Indefinite VIP flag set
        return True

    now = datetime.utcnow()
    # Normalize naive / aware datetimes
    if expiry.tzinfo is not None:
        expiry = expiry.replace(tzinfo=None)

    return expiry > now


def get_vip_details(user: Optional[User]) -> Dict[str, Any]:
    """
    Returns formatted dictionary of a user's VIP standing,
    remaining time, tier, gems, and daily streak.
    """
    if not user:
        return {
            "is_vip": False,
            "tier": "None",
            "is_lifetime": False,
            "expires_at": None,
            "days_remaining": 0,
            "hours_remaining": 0,
            "poke_gems": 0,
            "streak": 0
        }

    user_id = getattr(user, "id", None)
    owner_ids = set(getattr(config, "OWNER_IDS", []))
    co_owner_ids = set(getattr(config, "CO_OWNER_IDS", []))
    dev_ids = set(getattr(config, "DEV_IDS", []))
    is_staff = (user_id in owner_ids or user_id in co_owner_ids or user_id in dev_ids)

    poke_gems = getattr(user, "poke_gems", 0) or 0
    streak = getattr(user, "vip_daily_streak", 0) or 0

    if is_staff:
        return {
            "is_vip": True,
            "tier": "👑 Executive Lifetime VIP",
            "is_lifetime": True,
            "expires_at": None,
            "days_remaining": 9999,
            "hours_remaining": 999999,
            "poke_gems": poke_gems,
            "streak": streak
        }

    is_vip_flag = getattr(user, "is_vip", False)
    expiry = getattr(user, "vip_expiry", None)
    tier = getattr(user, "vip_tier", None) or "Standard VIP"

    if not is_vip_flag:
        return {
            "is_vip": False,
            "tier": "None",
            "is_lifetime": False,
            "expires_at": None,
            "days_remaining": 0,
            "hours_remaining": 0,
            "poke_gems": poke_gems,
            "streak": streak
        }

    if not expiry:
        return {
            "is_vip": True,
            "tier": tier,
            "is_lifetime": True,
            "expires_at": None,
            "days_remaining": 9999,
            "hours_remaining": 999999,
            "poke_gems": poke_gems,
            "streak": streak
        }

    now = datetime.utcnow()
    if expiry.tzinfo is not None:
        expiry = expiry.replace(tzinfo=None)

    if expiry <= now:
        return {
            "is_vip": False,
            "tier": "Expired",
            "is_lifetime": False,
            "expires_at": expiry,
            "days_remaining": 0,
            "hours_remaining": 0,
            "poke_gems": poke_gems,
            "streak": streak
        }

    remaining_delta = expiry - now
    days = remaining_delta.days
    hours = remaining_delta.seconds // 3600

    return {
        "is_vip": True,
        "tier": tier,
        "is_lifetime": False,
        "expires_at": expiry,
        "days_remaining": days,
        "hours_remaining": hours,
        "poke_gems": poke_gems,
        "streak": streak
    }


async def set_user_vip(
    db: AsyncSession,
    user: User,
    days: int,
    tier_name: Optional[str] = None
) -> User:
    """
    Grants or extends VIP access for a given number of days.
    If already active, appends to existing expiry.
    """
    now = datetime.utcnow()
    current_expiry = getattr(user, "vip_expiry", None)

    if current_expiry and current_expiry.tzinfo is not None:
        current_expiry = current_expiry.replace(tzinfo=None)

    if current_expiry and current_expiry > now:
        new_expiry = current_expiry + timedelta(days=days)
    else:
        new_expiry = now + timedelta(days=days)

    if not tier_name:
        if days <= 7:
            tier_name = "🥉 Weekly Plan"
        elif days <= 30:
            tier_name = "🥈 Monthly Plan"
        elif days <= 60:
            tier_name = "🥇 2-Month Plan"
        elif days <= 90:
            tier_name = "👑 3-Month Plan"
        else:
            tier_name = f"🌟 VIP ({days} Days)"

    user.is_vip = True
    user.vip_expiry = new_expiry
    user.vip_tier = tier_name
    await db.commit()
    return user


async def remove_user_vip(db: AsyncSession, user: User) -> User:
    """Revokes VIP privileges from a user."""
    user.is_vip = False
    user.vip_expiry = None
    user.vip_tier = None
    await db.commit()
    return user


async def add_poke_gems(db: AsyncSession, user: User, amount: int) -> int:
    """Increments a user's PokeGems balance."""
    current = getattr(user, "poke_gems", 0) or 0
    new_balance = max(0, current + amount)
    user.poke_gems = new_balance
    await db.commit()
    return new_balance
