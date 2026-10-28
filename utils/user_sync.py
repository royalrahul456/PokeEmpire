import html
import logging
from typing import Optional, Tuple, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from database.models import User

logger = logging.getLogger(__name__)

# Cache of last known identity in memory: user_id -> (username, nickname)
# Avoids performing database queries on every single message when identity has not changed.
_user_identity_cache: dict[int, tuple[Optional[str], str]] = {}


def get_cached_identity(user_id: int) -> Optional[tuple[Optional[str], str]]:
    return _user_identity_cache.get(user_id)


def set_cached_identity(user_id: int, username: Optional[str], nickname: str):
    _user_identity_cache[user_id] = (username, nickname)


def clear_cached_identity(user_id: int):
    _user_identity_cache.pop(user_id, None)


async def sync_user_identity(
    db: AsyncSession,
    event: Any,
    force: bool = False
) -> Tuple[Optional[User], bool]:
    """
    Synchronizes Telegram user profile details (username, display name)
    into the PokeEmpire database.
    
    Returns (user_obj, was_changed_or_created).
    """
    tg_user = getattr(event, "from_user", None)
    if not tg_user or getattr(tg_user, "is_bot", False):
        return None, False

    user_id = getattr(tg_user, "id", None)
    if not user_id or user_id <= 0:
        return None, False

    # Extract Telegram username (strip leading @ if any) and display name
    raw_username = getattr(tg_user, "username", None)
    curr_username = raw_username.strip().lstrip("@") if raw_username else None
    
    first_name = (getattr(tg_user, "first_name", "") or "").strip()
    last_name = (getattr(tg_user, "last_name", "") or "").strip()
    if first_name and last_name:
        curr_nickname = f"{first_name} {last_name}"[:100]
    elif first_name:
        curr_nickname = first_name[:100]
    else:
        curr_nickname = (curr_username or "Trainer")[:100]

    # Fast check against in-memory identity cache
    if not force:
        cached = _user_identity_cache.get(user_id)
        if cached is not None and cached == (curr_username, curr_nickname):
            return None, False

    try:
        stmt = select(User).where(User.id == user_id)
        res = await db.execute(stmt)
        user_obj = res.scalar_one_or_none()

        changed = False

        if user_obj:
            # Check if username changed
            if user_obj.username != curr_username:
                if curr_username:
                    # Clear this username from any other stale user to avoid duplicate key conflicts or search collisions
                    await db.execute(
                        update(User)
                        .where(func.lower(User.username) == curr_username.lower(), User.id != user_id)
                        .values(username=None)
                    )
                user_obj.username = curr_username
                changed = True

            # Check if nickname changed
            if user_obj.nickname != curr_nickname:
                user_obj.nickname = curr_nickname
                changed = True

            if changed:
                await db.commit()
                logger.info(
                    f"✅ User {user_id} profile updated in DB: username='{curr_username}', nickname='{curr_nickname}'"
                )
        else:
            # New user registration
            if curr_username:
                await db.execute(
                    update(User)
                    .where(func.lower(User.username) == curr_username.lower(), User.id != user_id)
                    .values(username=None)
                )
            user_obj = User(
                id=user_id,
                username=curr_username,
                nickname=curr_nickname,
                coins=500
            )
            db.add(user_obj)
            await db.commit()
            changed = True
            logger.info(
                f"✅ New user {user_id} registered in DB: username='{curr_username}', nickname='{curr_nickname}'"
            )

        _user_identity_cache[user_id] = (curr_username, curr_nickname)
        return user_obj, changed

    except Exception as e:
        logger.error(f"❌ Failed to sync user identity for {user_id}: {e}", exc_info=True)
        try:
            await db.rollback()
        except Exception:
            pass
        return None, False
