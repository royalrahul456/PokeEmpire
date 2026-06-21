from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Any

def get_dm_menu_keyboard() -> InlineKeyboardMarkup:
    """Generates the primary Hub menu keyboard for DMs."""
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
