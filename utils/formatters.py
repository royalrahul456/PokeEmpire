from typing import Dict, Any, Optional

def get_hp_bar(current: int, max_hp: int, length: int = 10) -> str:
    """Generates a text-based progress bar representing health percentage."""
    if max_hp <= 0:
        return "░" * length
    
    percent = max(0.0, min(1.0, current / max_hp))
    filled_len = int(round(length * percent))
    # Avoid showing 0 HP as filled if they fainted
    if current > 0 and filled_len == 0:
        filled_len = 1
    elif current <= 0:
        filled_len = 0
        
    bar = "█" * filled_len + "░" * (length - filled_len)
    
    # Add coloring representation for HP zones
    color_emoji = "🟢"
    if percent <= 0.2:
        color_emoji = "🔴"  # Danger zone
    elif percent <= 0.5:
        color_emoji = "🟡"  # Caution zone
        
    return f"`[{bar}]` {color_emoji} **{current}/{max_hp}**"

def get_rarity_emoji(tier: str) -> str:
    """Returns a representative emoji for a rarity tier."""
    emojis = {
        "Common": "⚪",
        "Uncommon": "🟢",
        "Rare": "💎",
        "Epic": "🔮",
        "Legendary": "👑",
        "Mythical": "🌌"
    }
    return emojis.get(tier, "⚪")

def format_monster_stats(base_stats: Dict[str, int], ivs: Optional[Dict[str, int]] = None) -> str:
    """Formats a beautiful grid of stats, including IV adjustments if provided."""
    if not ivs:
        ivs = {"hp": 0, "atk": 0, "def": 0, "spd": 0, "sp_atk": 0, "sp_def": 0}

    lines = [
        f"❤️ **HP**: {base_stats['hp']} `(IV: +{ivs.get('hp', 0)})`",
        f"⚔️ **Attack**: {base_stats['atk']} `(IV: +{ivs.get('atk', 0)})` | 🛡️ **Defense**: {base_stats['def']} `(IV: +{ivs.get('def', 0)})`",
        f"⚡ **Speed**: {base_stats['spd']} `(IV: +{ivs.get('spd', 0)})`",
        f"🔮 **Sp. Atk**: {base_stats['sp_atk']} `(IV: +{ivs.get('sp_atk', 0)})` | 🧿 **Sp. Def**: {base_stats['sp_def']} `(IV: +{ivs.get('sp_def', 0)})`"
    ]
    return "\n".join(lines)

def format_card_title(name: str, is_shiny: bool, tier: str) -> str:
    """Creates a beautifully styled, emoji-decorated card title."""
    badge = "✨ SHINY " if is_shiny else ""
    rarity_icon = get_rarity_emoji(tier)
    return f"{rarity_icon} **{badge}{name.upper()}** {rarity_icon}"

def get_progress_bar(current: float, total: float, length: int = 10, fill_char: str = "█", empty_char: str = "░") -> str:
    """Generates a text-based progress bar representing a percentage/progress."""
    if total <= 0:
        return empty_char * length
    percent = max(0.0, min(1.0, current / total))
    filled_len = int(round(length * percent))
    if current > 0 and filled_len == 0:
        filled_len = 1
    elif current <= 0:
        filled_len = 0
    return fill_char * filled_len + empty_char * (length - filled_len)

def escape_md(text: str) -> str:
    """Escapes Markdown special characters to prevent Telegram parse errors."""
    if not text:
        return ""
    # Escape legacy Markdown special characters: *, _, `, [
    for char in ["*", "_", "`", "["]:
        text = text.replace(char, f"\\{char}")
    return text
