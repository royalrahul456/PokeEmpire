from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Any
import config

def get_start_welcome_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⚡ OPEN POKEEMPIRE MINI APP 🎮", web_app=WebAppInfo(url=getattr(config, "WEBAPP_URL", "https://royalrahul456.github.io/PokeEmpire/webapp/")))
    )
    builder.row(
        InlineKeyboardButton(text="👑 Owner", url="https://t.me/TheDarkKratosX"),
        InlineKeyboardButton(text="👥 Official Group", url="https://t.me/pokeempireunion")
    )
    builder.row(
        InlineKeyboardButton(text="📢 Updates Channel", url="https://t.me/pokeempireupdates"),
        InlineKeyboardButton(text="➕ Add to your Group", url=f"https://t.me/{bot_username}?startgroup=true")
    )
    return builder.as_markup()

def get_dm_menu_keyboard() -> InlineKeyboardMarkup:
    """Generates the primary Hub menu keyboard for DMs."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⚡ OPEN POKEEMPIRE MINI APP 🎮", web_app=WebAppInfo(url=getattr(config, "WEBAPP_URL", "https://royalrahul456.github.io/PokeEmpire/webapp/")))
    )
    builder.row(
        InlineKeyboardButton(text="👤 Profile", callback_data="dm_profile"),
        InlineKeyboardButton(text="🏆 Pokédex", callback_data="dm_dex_1")
    )
    builder.row(
        InlineKeyboardButton(text="⚔️ Quests", callback_data="refresh_quests"),
        InlineKeyboardButton(text="🏰 Guilds", callback_data="dm_guild_info")
    )
    builder.row(
        InlineKeyboardButton(text="📜 Transactions", callback_data="dm_transactions"),
        InlineKeyboardButton(text="🎒 My Bag", callback_data="dm_bag_1")
    )
    builder.row(
        InlineKeyboardButton(text="📊 Leaderboard", callback_data="dm_leaderboard"),
        InlineKeyboardButton(text="🛡️ Battle", callback_data="dm_battle_menu")
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Trade", callback_data="dm_trade_info"),
        InlineKeyboardButton(text="🎁 Redeem", callback_data="dm_redeem_info")
    )
    builder.row(
        InlineKeyboardButton(text="🛂 Shop", callback_data="dm_shop"),
        InlineKeyboardButton(text="🎮 Games Center", callback_data="dm_games")
    )
    builder.row(
        InlineKeyboardButton(text="🔥 Streak", callback_data="dm_streak"),
        InlineKeyboardButton(text="📈 Chat Rankings", callback_data="dm_rankings_info")
    )
    builder.row(
        InlineKeyboardButton(text="❓ Guide", callback_data="dm_help")
    )
    return builder.as_markup()

def get_bag_pagination_keyboard(page: int, max_page: int) -> InlineKeyboardMarkup:
    """Generates navigation buttons for browsing caught Pokémon in DM."""
    builder = InlineKeyboardBuilder()
    
    # Prev/Next row
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"dm_bag_{page-1}"))
    if page < max_page:
        nav_buttons.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"dm_bag_{page+1}"))
    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="🔙 Back to Hub Menu", callback_data="dm_home"))
    return builder.as_markup()

def get_dex_pagination_keyboard(page: int, max_page: int) -> InlineKeyboardMarkup:
    """Generates navigation buttons for browsing Pokédex in DM."""
    builder = InlineKeyboardBuilder()
    
    # Prev/Next row
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"dm_dex_{page-1}"))
    if page < max_page:
        nav_buttons.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"dm_dex_{page+1}"))
    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="🔙 Back to Hub Menu", callback_data="dm_home"))
    return builder.as_markup()

def get_back_to_hub_keyboard() -> InlineKeyboardMarkup:
    """Simple back navigation button."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Back to Hub Menu", callback_data="dm_home"))
    return builder.as_markup()

def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Generates the primary Hub menu keyboard for DMs (Admin/Owner)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👤 Profile", callback_data="dm_profile"),
        InlineKeyboardButton(text="🏆 Pokédex", callback_data="dm_dex_1")
    )
    builder.row(
        InlineKeyboardButton(text="🎒 My Bag", callback_data="dm_bag_1"),
        InlineKeyboardButton(text="📊 Leaderboard", callback_data="dm_leaderboard")
    )
    builder.row(
        InlineKeyboardButton(text="🛡️ Battle", callback_data="dm_battle_menu"),
        InlineKeyboardButton(text="⚔️ Duel Trainer", callback_data="dm_duel_info")
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Trade", callback_data="dm_trade_info"),
        InlineKeyboardButton(text="🎁 Redeem", callback_data="dm_redeem_info")
    )
    builder.row(
        InlineKeyboardButton(text="🛂 Shop", callback_data="dm_shop"),
        InlineKeyboardButton(text="🎮 Games Center", callback_data="dm_games")
    )
    builder.row(
        InlineKeyboardButton(text="🔥 Streak", callback_data="dm_streak"),
        InlineKeyboardButton(text="📈 Chat Rankings", callback_data="dm_rankings_info")
    )
    builder.row(
        InlineKeyboardButton(text="❓ Guide", callback_data="dm_help")
    )
    builder.row(
        InlineKeyboardButton(text="👑 Executive Panel (/panel)", callback_data="owner_panel"),
        InlineKeyboardButton(text="🛠️ Owner Tools", callback_data="owner_tools")
    )
    return builder.as_markup()

def get_uploader_menu_keyboard() -> InlineKeyboardMarkup:
    """Generates the primary Hub menu keyboard for DMs (Uploader)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👤 Profile", callback_data="dm_profile"),
        InlineKeyboardButton(text="🏆 Pokédex", callback_data="dm_dex_1")
    )
    builder.row(
        InlineKeyboardButton(text="🎒 My Bag", callback_data="dm_bag_1"),
        InlineKeyboardButton(text="📊 Leaderboard", callback_data="dm_leaderboard")
    )
    builder.row(
        InlineKeyboardButton(text="🛡️ Battle", callback_data="dm_battle_menu"),
        InlineKeyboardButton(text="⚔️ Duel Trainer", callback_data="dm_duel_info")
    )
    builder.row(
        InlineKeyboardButton(text="🔄 Trade", callback_data="dm_trade_info"),
        InlineKeyboardButton(text="🎁 Redeem", callback_data="dm_redeem_info")
    )
    builder.row(
        InlineKeyboardButton(text="🛂 Shop", callback_data="dm_shop"),
        InlineKeyboardButton(text="🎮 Games Center", callback_data="dm_games")
    )
    builder.row(
        InlineKeyboardButton(text="🔥 Streak", callback_data="dm_streak"),
        InlineKeyboardButton(text="❓ Guide", callback_data="dm_help")
    )
    builder.row(
        InlineKeyboardButton(text="📋 View Media IDs", callback_data="owner_medialist")
    )
    return builder.as_markup()
