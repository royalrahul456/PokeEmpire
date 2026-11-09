"""
Guild Flag Catalog & Utilities for PokéEmpire.
Supports animated Telegram custom emojis (<tg-emoji emoji-id="...">...</tg-emoji>),
preset animated banners, and unicode flags.
"""
import re
import html
from typing import Dict, Any, Optional
from sqlalchemy import select
from database.models import GlobalSetting

# Built-in presets with fallback unicode icons
PRESET_GUILD_FLAGS: Dict[str, Dict[str, str]] = {
    "shield": {
        "name": "Golden Shield",
        "fallback": "🛡️",
        "tag": "🛡️",
        "emoji_id": None
    },
    "strawhat": {
        "name": "Straw Hat Pirates",
        "fallback": "🏴‍☠️",
        "tag": "🏴‍☠️",
        "emoji_id": None
    },
    "phoenix": {
        "name": "Blazing Phoenix",
        "fallback": "🔥",
        "tag": "🔥",
        "emoji_id": None
    },
    "jedi_blue": {
        "name": "Galactic Order (Blue)",
        "fallback": "💠",
        "tag": "💠",
        "emoji_id": None
    },
    "jedi_grey": {
        "name": "Grey Guardian (Silver)",
        "fallback": "⚔️",
        "tag": "⚔️",
        "emoji_id": None
    },
    "samurai": {
        "name": "Cyber Samurai",
        "fallback": "👹",
        "tag": "👹",
        "emoji_id": None
    },
    "dragon": {
        "name": "Imperial Dragon",
        "fallback": "🐉",
        "tag": "🐉",
        "emoji_id": None
    },
    "crown": {
        "name": "Royal Sovereign",
        "fallback": "👑",
        "tag": "👑",
        "emoji_id": None
    },
    "wolf": {
        "name": "Iron Wolf",
        "fallback": "🐺",
        "tag": "🐺",
        "emoji_id": None
    },
    "lightning": {
        "name": "Thunder Strike",
        "fallback": "⚡",
        "tag": "⚡",
        "emoji_id": None
    },
    "skull": {
        "name": "Shadow Skull",
        "fallback": "💀",
        "tag": "💀",
        "emoji_id": None
    },
    "star": {
        "name": "Celestial Star",
        "fallback": "⭐",
        "tag": "⭐",
        "emoji_id": None
    }
}


def format_guild_flag(flag_val: Optional[str], default: str = "🛡️") -> str:
    """
    Formats a stored flag string into a displayable HTML tag or emoji.
    Supports:
      - Raw <tg-emoji emoji-id="...">fallback</tg-emoji>
      - Preset flag key (e.g., 'strawhat', 'phoenix')
      - Numeric custom emoji ID (e.g. '5269563867305879894')
      - Plain unicode emoji (e.g. '🏴‍☠️', '🛡️')
    """
    if not flag_val:
        return default

    flag_val = str(flag_val).strip()
    if not flag_val:
        return default

    # If it's already an HTML tg-emoji tag
    if "<tg-emoji" in flag_val:
        return flag_val

    # If it matches a known preset
    lower_key = flag_val.lower()
    if lower_key in PRESET_GUILD_FLAGS:
        preset = PRESET_GUILD_FLAGS[lower_key]
        if preset.get("emoji_id"):
            return f'<tg-emoji emoji-id="{preset["emoji_id"]}">{preset["fallback"]}</tg-emoji>'
        return preset.get("tag", preset.get("fallback", default))

    # If it is a raw numeric Telegram custom emoji ID
    if flag_val.isdigit():
        return f'<tg-emoji emoji-id="{flag_val}">🛡️</tg-emoji>'

    return flag_val


def get_flag_display_name(flag_val: Optional[str]) -> str:
    """Returns a friendly label for the flag."""
    if not flag_val:
        return "Golden Shield"
    lower_key = str(flag_val).strip().lower()
    if lower_key in PRESET_GUILD_FLAGS:
        return PRESET_GUILD_FLAGS[lower_key]["name"]
    if "<tg-emoji" in flag_val or flag_val.isdigit():
        return "Custom Animated Flag"
    return "Custom Flag"


async def get_all_guild_flags(db=None) -> Dict[str, Dict[str, Any]]:
    """
    Returns full dictionary of available guild flags, merging built-in presets
    with any custom flags registered in GlobalSetting.
    """
    import json
    flags = dict(PRESET_GUILD_FLAGS)
    if not db:
        return flags

    try:
        stmt = select(GlobalSetting).where(GlobalSetting.key == "guild_custom_flags")
        res = await db.execute(stmt)
        record = res.scalar_one_or_none()
        if record and record.value:
            custom_dict = json.loads(record.value)
            for k, v in custom_dict.items():
                flags[k] = v
    except Exception:
        pass
    return flags


async def register_guild_flag(key: str, name: str, emoji_id: str, fallback: str, db) -> bool:
    """Registers or updates a custom flag in GlobalSetting."""
    import json
    try:
        stmt = select(GlobalSetting).where(GlobalSetting.key == "guild_custom_flags")
        res = await db.execute(stmt)
        record = res.scalar_one_or_none()
        current_data = {}
        if record and record.value:
            try:
                current_data = json.loads(record.value)
            except Exception:
                current_data = {}
        
        tag = f'<tg-emoji emoji-id="{emoji_id}">{fallback}</tg-emoji>'
        current_data[key.lower()] = {
            "name": name,
            "fallback": fallback,
            "tag": tag,
            "emoji_id": emoji_id
        }

        if record:
            record.value = json.dumps(current_data)
        else:
            db.add(GlobalSetting(key="guild_custom_flags", value=json.dumps(current_data)))
        
        await db.commit()
        return True
    except Exception as e:
        print(f"Error registering guild flag: {e}")
        return False
