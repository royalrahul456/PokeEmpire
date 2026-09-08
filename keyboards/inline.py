from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Any
import config

def create_styled_button(
    text: str,
    key: str = None,
    url: str = None,
    callback_data: str = None,
    style: str = None,
    icon_custom_emoji_id: str = None,
    web_app: WebAppInfo = None
) -> InlineKeyboardButton:
    """Helper to construct InlineKeyboardButton with native custom emoji icon and color style."""
    emoji_id = icon_custom_emoji_id or (getattr(config, "CUSTOM_EMOJI_IDS", {}).get(key) if key else None)
    btn_style = style or (getattr(config, "BUTTON_STYLES", {}).get(key) if key else None)
    kwargs = {"text": text}
    if url:
        kwargs["url"] = url
    if callback_data:
        kwargs["callback_data"] = callback_data
    if web_app:
        kwargs["web_app"] = web_app
    if emoji_id:
        kwargs["icon_custom_emoji_id"] = emoji_id
    if btn_style:
        kwargs["style"] = btn_style
    return InlineKeyboardButton(**kwargs)

def get_start_welcome_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    """Generates primary start welcome keyboard with native Telegram Custom Emoji icons and Button Color Styles."""
    builder = InlineKeyboardBuilder()
    
    # Row 1 (Full Width): Add to Group
    builder.row(
        create_styled_button(
            text="Add to Group",
            key="add_to_group",
            url=f"https://t.me/{bot_username}?startgroup=true"
        )
    )
    # Row 2: Updates & Support
    updates_username = getattr(config, "UPDATES_CHANNEL", "@pokeempireupdates").replace("@", "")
    builder.row(
        create_styled_button(
            text="Updates",
            key="updates",
            url=f"https://t.me/{updates_username}"
        ),
        create_styled_button(
            text="Support",
            key="support",
            url="https://t.me/pokeempireunion"
        )
    )
    # Row 3: Help & Stats
    builder.row(
        create_styled_button(
            text="Help",
            key="help",
            callback_data="dm_help"
        ),
        create_styled_button(
            text="Stats",
            key="stats",
            callback_data="dm_rankings_info"
        )
    )
    return builder.as_markup()

def get_dm_menu_keyboard() -> InlineKeyboardMarkup:
    """Generates the primary Hub menu keyboard for DMs with native custom emojis & color styles."""
    builder = InlineKeyboardBuilder()
    builder.row(
        create_styled_button(text="Profile", key="profile", callback_data="dm_profile"),
        create_styled_button(text="Pokédex", key="pokedex", callback_data="dm_dex_1")
    )
    builder.row(
        create_styled_button(text="Quests", key="quests", callback_data="refresh_quests"),
        create_styled_button(text="Guilds", key="guilds", callback_data="dm_guild_info")
    )
    builder.row(
        create_styled_button(text="Transactions", key="history", callback_data="dm_transactions"),
        create_styled_button(text="My Bag", key="bag", callback_data="dm_bag_1")
    )
    builder.row(
        create_styled_button(text="Leaderboard", key="leaderboard", callback_data="dm_leaderboard"),
        create_styled_button(text="Battle Arena", key="battle", callback_data="dm_battle_menu")
    )
    builder.row(
        create_styled_button(text="Trade", key="trade", callback_data="dm_trade_info"),
        create_styled_button(text="Redeem Code", key="redeem", callback_data="dm_redeem_info")
    )
    builder.row(
        create_styled_button(text="Shop", key="shop", callback_data="dm_shop"),
        create_styled_button(text="Games Center", key="games", callback_data="dm_games")
    )
    builder.row(
        create_styled_button(text="Streak", key="streak", callback_data="dm_streak"),
        create_styled_button(text="Chat Rankings", key="stats", callback_data="dm_rankings_info")
    )
    builder.row(
        create_styled_button(text="Help & Guide", key="help", callback_data="dm_help")
    )
    return builder.as_markup()

def get_bag_pagination_keyboard(page: int, max_page: int) -> InlineKeyboardMarkup:
    """Generates navigation buttons for browsing caught Pokémon in DM."""
    builder = InlineKeyboardBuilder()
    
    # Prev/Next row
    nav_buttons = []
    if page > 1:
        nav_buttons.append(create_styled_button(text="◀️ Prev", key="prev", callback_data=f"dm_bag_{page-1}"))
    if page < max_page:
        nav_buttons.append(create_styled_button(text="Next ➡️", key="next", callback_data=f"dm_bag_{page+1}"))
    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(create_styled_button(text="Back to Hub Menu", key="back", callback_data="dm_home"))
    return builder.as_markup()

def get_dex_pagination_keyboard(page: int, max_page: int) -> InlineKeyboardMarkup:
    """Generates navigation buttons for browsing Pokédex in DM."""
    builder = InlineKeyboardBuilder()
    
    # Prev/Next row
    nav_buttons = []
    if page > 1:
        nav_buttons.append(create_styled_button(text="◀️ Prev", key="prev", callback_data=f"dm_dex_{page-1}"))
    if page < max_page:
        nav_buttons.append(create_styled_button(text="Next ➡️", key="next", callback_data=f"dm_dex_{page+1}"))
    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(create_styled_button(text="Back to Hub Menu", key="back", callback_data="dm_home"))
    return builder.as_markup()

def get_back_to_hub_keyboard() -> InlineKeyboardMarkup:
    """Simple back navigation button."""
    builder = InlineKeyboardBuilder()
    builder.row(create_styled_button(text="Back to Hub Menu", key="back", callback_data="dm_home"))
    return builder.as_markup()

def get_admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Generates the primary Hub menu keyboard for DMs (Admin/Owner) with native custom emojis & color styles."""
    builder = InlineKeyboardBuilder()
    builder.row(
        create_styled_button(text="Profile", key="profile", callback_data="dm_profile"),
        create_styled_button(text="Pokédex", key="pokedex", callback_data="dm_dex_1")
    )
    builder.row(
        create_styled_button(text="My Bag", key="bag", callback_data="dm_bag_1"),
        create_styled_button(text="Leaderboard", key="leaderboard", callback_data="dm_leaderboard")
    )
    builder.row(
        create_styled_button(text="Battle Arena", key="battle", callback_data="dm_battle_menu"),
        create_styled_button(text="Quests", key="quests", callback_data="refresh_quests")
    )
    builder.row(
        create_styled_button(text="Trade", key="trade", callback_data="dm_trade_info"),
        create_styled_button(text="Redeem Code", key="redeem", callback_data="dm_redeem_info")
    )
    builder.row(
        create_styled_button(text="Shop", key="shop", callback_data="dm_shop"),
        create_styled_button(text="Games Center", key="games", callback_data="dm_games")
    )
    builder.row(
        create_styled_button(text="Streak", key="streak", callback_data="dm_streak"),
        create_styled_button(text="Chat Rankings", key="stats", callback_data="dm_rankings_info")
    )
    builder.row(
        create_styled_button(text="Help & Guide", key="help", callback_data="dm_help")
    )
    builder.row(
        create_styled_button(text="Executive Panel (/panel)", key="panel", callback_data="owner_panel"),
        create_styled_button(text="Owner Tools", key="tools", callback_data="owner_tools")
    )
    return builder.as_markup()

def get_uploader_menu_keyboard() -> InlineKeyboardMarkup:
    """Generates the primary Hub menu keyboard for DMs (Uploader) with native custom emojis & color styles."""
    builder = InlineKeyboardBuilder()
    builder.row(
        create_styled_button(text="Profile", key="profile", callback_data="dm_profile"),
        create_styled_button(text="Pokédex", key="pokedex", callback_data="dm_dex_1")
    )
    builder.row(
        create_styled_button(text="My Bag", key="bag", callback_data="dm_bag_1"),
        create_styled_button(text="Leaderboard", key="leaderboard", callback_data="dm_leaderboard")
    )
    builder.row(
        create_styled_button(text="Battle Arena", key="battle", callback_data="dm_battle_menu"),
        create_styled_button(text="Quests", key="quests", callback_data="refresh_quests")
    )
    builder.row(
        create_styled_button(text="Trade", key="trade", callback_data="dm_trade_info"),
        create_styled_button(text="Redeem Code", key="redeem", callback_data="dm_redeem_info")
    )
    builder.row(
        create_styled_button(text="Shop", key="shop", callback_data="dm_shop"),
        create_styled_button(text="Games Center", key="games", callback_data="dm_games")
    )
    builder.row(
        create_styled_button(text="Streak", key="streak", callback_data="dm_streak"),
        create_styled_button(text="Help & Guide", key="help", callback_data="dm_help")
    )
    builder.row(
        create_styled_button(text="View Media IDs", key="tools", callback_data="owner_medialist")
    )
    return builder.as_markup()
