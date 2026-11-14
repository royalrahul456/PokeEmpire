# -*- coding: utf-8 -*-
import os
import json
import time
import asyncio
import html
from typing import Dict, Tuple, List, Optional
from datetime import datetime
import config

DATA_DIR = getattr(config, "DATA_DIR", os.path.join(os.path.dirname(os.path.dirname(__file__)), "data"))
TEMP_BANS_FILE = os.path.join(DATA_DIR, "temp_bans.json")

# In-memory storage
_temp_bans: Dict[int, dict] = {}
_spam_attempts: Dict[int, Dict[str, List[float]]] = {}
_last_notify_time: Dict[str, float] = {}
_offense_history: Dict[int, int] = {}

# Monitored reward commands: claim, daily, spin, vipclaim, vipdaily and short aliases
SPAM_TRIGGER_COMMANDS = {"claim", "cl", "daily", "spin", "wheel", "vipclaim", "vc", "vipdaily", "vd"}


def format_duration(seconds: int) -> str:
    """Formats seconds into human-readable duration string (e.g. 1h 30m, 45s)."""
    seconds = max(0, int(seconds))
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts = []
    if days > 0:
        parts.append(f"{days}d")
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


def _load_temp_bans() -> None:
    """Loads active temp bans and offense history from disk."""
    global _temp_bans, _offense_history
    if not os.path.exists(TEMP_BANS_FILE):
        return
    try:
        with open(TEMP_BANS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        now = time.time()
        bans = data.get("bans", {})
        _offense_history = {int(k): int(v) for k, v in data.get("offenses", {}).items()}
        _temp_bans = {}
        for k, rec in bans.items():
            u_id = int(k)
            if rec.get("banned_until", 0) > now:
                _temp_bans[u_id] = rec
    except Exception as e:
        print(f"⚠️ Error loading temp bans from {TEMP_BANS_FILE}: {e}")


def _save_temp_bans() -> None:
    """Persists active temp bans and offense history to disk."""
    try:
        os.makedirs(os.path.dirname(TEMP_BANS_FILE), exist_ok=True)
        data = {
            "bans": {str(k): v for k, v in _temp_bans.items()},
            "offenses": {str(k): v for k, v in _offense_history.items()},
        }
        with open(TEMP_BANS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"⚠️ Error saving temp bans to {TEMP_BANS_FILE}: {e}")


# Initialize cache immediately on module import
_load_temp_bans()


def is_temp_banned(user_id: int) -> Tuple[bool, int, dict]:
    """
    Checks if a user has an active temporary ban.
    Returns:
      (is_banned: bool, remaining_seconds: int, ban_record: dict)
    """
    now = time.time()
    rec = _temp_bans.get(user_id)
    if not rec:
        return False, 0, {}

    banned_until = rec.get("banned_until", 0)
    if now < banned_until:
        remaining = int(banned_until - now)
        return True, remaining, rec
    else:
        # Expired - prune and save
        del _temp_bans[user_id]
        _save_temp_bans()
        return False, 0, {}


def get_next_ban_duration(user_id: int) -> int:
    """Calculates progressive ban duration based on previous offenses."""
    offenses = _offense_history.get(user_id, 0)
    default_mins = getattr(config, "TEMP_BAN_DEFAULT_MINUTES", 30)
    base_secs = default_mins * 60
    if offenses == 0:
        return base_secs
    elif offenses == 1:
        return max(base_secs, 3600)  # 1 hour
    elif offenses == 2:
        return 6 * 3600  # 6 hours
    else:
        return 24 * 3600  # 24 hours


def apply_temp_ban(
    user_id: int,
    duration_seconds: Optional[int] = None,
    reason: str = "Spamming reward commands",
    username: Optional[str] = None,
    chat_id: Optional[int] = None,
    chat_title: Optional[str] = None,
) -> dict:
    """Issues a temporary bot ban for the specified duration in seconds."""
    now = time.time()
    if duration_seconds is None:
        duration_seconds = get_next_ban_duration(user_id)

    banned_until = now + duration_seconds
    offenses = _offense_history.get(user_id, 0) + 1
    _offense_history[user_id] = offenses

    rec = {
        "user_id": user_id,
        "username": username,
        "banned_at": now,
        "banned_until": banned_until,
        "duration_seconds": duration_seconds,
        "reason": reason,
        "offense_count": offenses,
        "chat_id": chat_id,
        "chat_title": chat_title,
    }
    _temp_bans[user_id] = rec
    _spam_attempts.pop(user_id, None)
    _save_temp_bans()
    return rec


def remove_temp_ban(user_id: int) -> bool:
    """Removes a user's active temporary ban early. Returns True if removed."""
    if user_id in _temp_bans:
        del _temp_bans[user_id]
        _save_temp_bans()
        return True
    return False


def get_all_temp_bans() -> List[dict]:
    """Returns all active temporary bans sorted by remaining time."""
    now = time.time()
    active = []
    expired = []
    for uid, rec in list(_temp_bans.items()):
        banned_until = rec.get("banned_until", 0)
        if now < banned_until:
            rec_copy = dict(rec)
            rec_copy["remaining_seconds"] = int(banned_until - now)
            active.append(rec_copy)
        else:
            expired.append(uid)
    if expired:
        for uid in expired:
            _temp_bans.pop(uid, None)
        _save_temp_bans()
    active.sort(key=lambda x: x["remaining_seconds"])
    return active


def record_and_check_reward_spam(user_id: int, cmd: str) -> Tuple[str, int]:
    """
    Tracks and checks spamming for claim/daily/spin/vipclaim/vipdaily commands.
    Returns:
      ("BAN", count) -> Threshold exceeded, issue temporary ban immediately
      ("WARN", count) -> Warning threshold reached, warn the user
      ("OK", count)   -> Within normal limits
    """
    now = time.time()
    user_cmds = _spam_attempts.setdefault(user_id, {})

    # 1. Per-command tracking
    times = user_cmds.setdefault(cmd, [])
    window = getattr(config, "SPAM_COMMAND_WINDOW", 5.0)
    times = [t for t in times if now - t < window]
    times.append(now)
    user_cmds[cmd] = times
    cnt = len(times)

    # 2. Cross-reward tracking (any reward command within 4.0s)
    any_times = user_cmds.setdefault("__reward_any__", [])
    any_times = [t for t in any_times if now - t < 4.0]
    any_times.append(now)
    user_cmds["__reward_any__"] = any_times
    any_cnt = len(any_times)

    # Fast macro burst: 3+ attempts within <= 1.8 seconds
    if cnt >= 3 and (times[-1] - times[0] <= 1.8):
        return ("BAN", cnt)

    # Repeated spam: 4+ attempts within the window
    if cnt >= 4:
        return ("BAN", cnt)

    # Automated multi-command cycling: >= 5 reward commands in 4.0s
    if any_cnt >= 5:
        return ("BAN", any_cnt)

    # Warning on 3rd attempt
    if cnt == 3:
        return ("WARN", cnt)

    return ("OK", cnt)


def should_notify_temp_ban(user_id: int, chat_id: int, interval: float = 10.0) -> bool:
    """Rate-limits temp ban reminder notices per user/chat to prevent chat flood."""
    now = time.time()
    key = f"{user_id}_{chat_id}"
    last = _last_notify_time.get(key, 0)
    if now - last >= interval:
        _last_notify_time[key] = now
        return True
    return False


async def revoke_spammer_rewards(user_id: int, cmd_name: str, db=None) -> dict:
    """
    Revokes ill-gotten rewards (coins, gems, pokemon) when a user spams
    claim, daily, spin, vipclaim, or vipdaily and gets temp-banned.
    Returns a dict summarizing what was revoked.
    """
    revoked = {
        "coins": 0,
        "gems": 0,
        "pokemon": None,
        "details": []
    }

    from database.database import SessionLocal
    from database.models import User, UserPokemon, Pokemon
    from sqlalchemy import select

    async def _do_revoke(session):
        try:
            u_stmt = select(User).where(User.id == user_id)
            u_res = await session.execute(u_stmt)
            user = u_res.scalar_one_or_none()
            if not user:
                return

            now = datetime.utcnow()
            norm_cmd = cmd_name.lower().replace("/", "").replace("@", "").strip()

            # ── 1. Daily Coins Revocation ──
            if norm_cmd in {"daily"}:
                coins_to_revoke = 500
                user.coins = max(0, (user.coins or 0) - coins_to_revoke)
                revoked["coins"] += coins_to_revoke
                revoked["details"].append(f"• 💰 -{coins_to_revoke:,} Coins revoked (daily)")
                user.last_daily_at = now

            # ── 2. Lucky Spin Coins Revocation ──
            elif norm_cmd in {"spin", "wheel"}:
                coins_to_revoke = 350
                user.coins = max(0, (user.coins or 0) - coins_to_revoke)
                revoked["coins"] += coins_to_revoke
                revoked["details"].append(f"• 💰 -{coins_to_revoke:,} Coins revoked (spin)")
                user.last_spin_at = now

            # ── 3. VIP Daily Bundle Revocation ──
            elif norm_cmd in {"vipdaily", "vd"}:
                coins_to_revoke = 2500
                gems_to_revoke = 65
                user.coins = max(0, (user.coins or 0) - coins_to_revoke)
                cur_gems = getattr(user, "poke_gems", 0) or 0
                user.poke_gems = max(0, cur_gems - gems_to_revoke)
                revoked["coins"] += coins_to_revoke
                revoked["gems"] += gems_to_revoke
                revoked["details"].append(f"• 💰 -{coins_to_revoke:,} Coins revoked (VIP daily)")
                revoked["details"].append(f"• ⭐ -{gems_to_revoke} PokeGems revoked (VIP daily)")

                user.vip_daily_streak = 0
                user.last_vip_daily = now

                # Revoke the Pokémon granted from vipdaily
                p_stmt = (
                    select(UserPokemon, Pokemon)
                    .join(Pokemon, Pokemon.id == UserPokemon.pokemon_id)
                    .where(UserPokemon.user_id == user_id)
                    .order_by(UserPokemon.id.desc())
                    .limit(1)
                )
                p_res = await session.execute(p_stmt)
                row = p_res.first()
                if row:
                    up, p = row
                    p_name = p.name.title() if p else f"#{up.pokemon_id}"
                    revoked["pokemon"] = p_name
                    revoked["details"].append(f"• 👾 Revoked VIP Pokémon: <b>{p_name}</b>")
                    await session.delete(up)

            # ── 4. Standard Claim Pokémon Revocation ──
            elif norm_cmd in {"claim", "cl"}:
                p_stmt = (
                    select(UserPokemon, Pokemon)
                    .join(Pokemon, Pokemon.id == UserPokemon.pokemon_id)
                    .where(UserPokemon.user_id == user_id)
                    .order_by(UserPokemon.id.desc())
                    .limit(1)
                )
                p_res = await session.execute(p_stmt)
                row = p_res.first()
                if row:
                    up, p = row
                    p_name = p.name.title() if p else f"#{up.pokemon_id}"
                    revoked["pokemon"] = p_name
                    revoked["details"].append(f"• 👾 Revoked claimed Pokémon: <b>{p_name}</b>")
                    await session.delete(up)

                from utils.claim import update_claim_cooldown
                update_claim_cooldown(user_id)
                revoked["details"].append("• ⏳ Claim cooldown locked for 24h")

            # ── 5. VIP Claim Alternate Art Pokémon Revocation ──
            elif norm_cmd in {"vipclaim", "vc"}:
                p_stmt = (
                    select(UserPokemon, Pokemon)
                    .join(Pokemon, Pokemon.id == UserPokemon.pokemon_id)
                    .where(UserPokemon.user_id == user_id)
                    .order_by(UserPokemon.id.desc())
                    .limit(1)
                )
                p_res = await session.execute(p_stmt)
                row = p_res.first()
                if row:
                    up, p = row
                    p_name = p.name.title() if p else f"#{up.pokemon_id}"
                    revoked["pokemon"] = p_name
                    revoked["details"].append(f"• 🎨 Revoked VIP alternate art Pokémon: <b>{p_name}</b>")
                    await session.delete(up)

                from utils.claim import update_vip_claim_cooldown
                update_vip_claim_cooldown(user_id)
                revoked["details"].append("• ⏳ VIP claim cooldown locked for 24h")

            # Log transaction in financial history if coins were revoked
            if revoked["coins"] > 0:
                try:
                    from utils.trainer_level import log_transaction
                    await log_transaction(
                        user_id,
                        -revoked["coins"],
                        "SPAM_PENALTY",
                        f"Revoked rewards for spamming /{norm_cmd}",
                        session
                    )
                except Exception:
                    pass

            await session.commit()
        except Exception as e:
            try:
                await session.rollback()
            except Exception:
                pass
            print(f"⚠️ Error revoking spammer rewards: {e}")

    try:
        if db:
            await _do_revoke(db)
        else:
            async with SessionLocal() as session:
                await _do_revoke(session)
    except Exception as e:
        print(f"⚠️ Session error during reward revocation: {e}")

    return revoked


async def notify_owners_temp_ban(bot, user, cmd_name: str, count: int, duration_seconds: int, chat=None, revoked_info: Optional[dict] = None):
    """Sends a private DM to bot owners when a user is temp-banned for spamming."""
    if not bot:
        return
    owner_ids = getattr(config, "OWNER_IDS", [])
    if not owner_ids:
        return

    user_id = user.id
    username_str = f"@{user.username}" if getattr(user, "username", None) else "No Username"
    name = getattr(user, "full_name", None) or getattr(user, "first_name", "Trainer")
    chat_info = f"{chat.title} (<code>{chat.id}</code>)" if (chat and getattr(chat, "title", None)) else "Private Chat"
    dur_str = format_duration(duration_seconds)

    revoked_str = "None"
    if revoked_info and revoked_info.get("details"):
        revoked_str = "\n".join(revoked_info["details"])

    alert_text = (
        f"🚨 <b>ANTI-SPAM ALERT: User Temp-Banned</b>\n"
        f"◈ ────────────────────────── ◈\n"
        f"👤 <b>User:</b> {html.escape(name)} ({username_str})\n"
        f"🆔 <b>User ID:</b> <code>{user_id}</code>\n"
        f"⏱️ <b>Ban Duration:</b> <b>{dur_str}</b>\n"
        f"📋 <b>Trigger:</b> Spammed <code>/{cmd_name}</code> ({count} attempts in 5s)\n"
        f"⚠️ <b>Rewards Revoked:</b>\n{revoked_str}\n"
        f"💬 <b>Chat:</b> {html.escape(chat_info)}\n"
        f"◈ ────────────────────────── ◈\n"
        f"<i>To lift ban early: <code>/untempban {user_id}</code></i>"
    )

    for oid in owner_ids:
        try:
            await bot.send_message(chat_id=oid, text=alert_text, parse_mode="HTML")
        except Exception:
            pass
