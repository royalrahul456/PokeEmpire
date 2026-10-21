import json
import time
import html
from typing import Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.database import SessionLocal
from database.models import GlobalSetting
import config

# In-memory cache for ultra-fast zero-DB checks on every message / callback
# {"enabled": bool, "reason": str or None, "started_at": float or None, "enabled_by": int or None}
_maintenance_state: Dict[str, Any] = {
    "enabled": False,
    "reason": None,
    "started_at": None,
    "enabled_by": None
}

# Cooldown cache to throttle maintenance replies (user_id, chat_id) -> timestamp
_maintenance_warn_cooldown: Dict[tuple, float] = {}


def is_maintenance_mode() -> bool:
    """Returns True if the bot is currently in maintenance mode."""
    return bool(_maintenance_state.get("enabled", False))


def get_maintenance_info() -> Dict[str, Any]:
    """Returns a copy of the current maintenance state dictionary."""
    return dict(_maintenance_state)


def is_maintenance_exempt(user_id: Optional[int]) -> bool:
    """
    Checks if a user is authorized to bypass maintenance mode.
    Only Owner, Co-Owner, and Developers are exempt.
    """
    if not user_id:
        return False
    owner_ids = set(getattr(config, "OWNER_IDS", []))
    co_owner_ids = set(getattr(config, "CO_OWNER_IDS", []))
    dev_ids = set(getattr(config, "DEV_IDS", []))
    return (user_id in owner_ids) or (user_id in co_owner_ids) or (user_id in dev_ids)


def should_warn_maintenance(user_id: int, chat_id: int) -> bool:
    """
    Throttles maintenance warnings to once every 4 seconds per user & chat,
    preventing notification spam during active discussions or command bursts.
    """
    now = time.time()
    key = (user_id, chat_id)
    last_time = _maintenance_warn_cooldown.get(key, 0.0)
    if now - last_time < 4.0:
        return False
    _maintenance_warn_cooldown[key] = now

    # Housekeeping: prune old cooldown entries periodically
    if len(_maintenance_warn_cooldown) > 1000:
        for k in list(_maintenance_warn_cooldown.keys()):
            if now - _maintenance_warn_cooldown[k] > 60.0:
                _maintenance_warn_cooldown.pop(k, None)
    return True


def get_maintenance_message(reason: Optional[str] = None) -> str:
    """Generates the styled HTML notification card displayed to non-exempt users."""
    current_reason = reason or _maintenance_state.get("reason")
    reason_html = ""
    if current_reason:
        reason_html = f"📋 <b>Reason:</b> <code>{html.escape(current_reason)}</code>\n\n"

    return (
        "🚧 <b>BOT UNDER MAINTENANCE</b> 🚧\n"
        "◈ ────────────────────────── ◈\n"
        "<blockquote>⚠️ <b>PokéEmpire is currently undergoing maintenance.</b>\n\n"
        f"{reason_html}"
        "Our team is updating core systems to bring you performance improvements and new features.\n\n"
        "👑 <i>During this period, only the Owner, Co-Owner, and Developers can use the bot.</i>\n\n"
        "Please check back shortly! Thank you for your patience.</blockquote>\n"
        "◈ ────────────────────────── ◈"
    )


async def set_maintenance_mode(
    enabled: bool,
    reason: Optional[str] = None,
    enabled_by: Optional[int] = None,
    db: Optional[AsyncSession] = None
):
    """
    Toggles maintenance mode on or off, updates memory cache,
    and commits the state to database GlobalSetting.
    """
    global _maintenance_state
    _maintenance_state["enabled"] = bool(enabled)
    _maintenance_state["reason"] = reason.strip() if (enabled and reason and reason.strip()) else None
    _maintenance_state["started_at"] = time.time() if enabled else None
    _maintenance_state["enabled_by"] = enabled_by if enabled else None

    # Sync into global settings cache
    try:
        from utils.settings import global_settings_cache
        payload_str = json.dumps(_maintenance_state)
        global_settings_cache["maintenance_mode"] = payload_str
    except Exception:
        payload_str = json.dumps(_maintenance_state)

    # Persist into database GlobalSetting
    async def _save_record(session: AsyncSession):
        stmt = select(GlobalSetting).where(GlobalSetting.key == "maintenance_mode")
        res = await session.execute(stmt)
        gs = res.scalar_one_or_none()
        if gs:
            gs.value = payload_str
        else:
            session.add(GlobalSetting(key="maintenance_mode", value=payload_str))
        await session.commit()

    try:
        if db is not None:
            await _save_record(db)
        else:
            async with SessionLocal() as local_session:
                await _save_record(local_session)
    except Exception as e:
        print(f"[MAINTENANCE] Error saving state to DB (in-memory state updated): {e}")


async def load_maintenance_from_db():
    """Startup routine: pulls persistent maintenance state from database into in-memory cache."""
    global _maintenance_state
    try:
        async with SessionLocal() as db:
            stmt = select(GlobalSetting).where(GlobalSetting.key == "maintenance_mode")
            res = await db.execute(stmt)
            gs = res.scalar_one_or_none()
            if gs and gs.value:
                try:
                    data = json.loads(gs.value)
                    if isinstance(data, dict):
                        _maintenance_state.update(data)
                    elif str(data).lower() in ("true", "1", "yes"):
                        _maintenance_state["enabled"] = True
                except Exception:
                    if str(gs.value).lower() in ("true", "1", "yes"):
                        _maintenance_state["enabled"] = True
    except Exception as e:
        print(f"[MAINTENANCE] Error loading maintenance state from DB: {e}")
