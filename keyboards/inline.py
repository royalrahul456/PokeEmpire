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
    """Helper to construct 100% standard-compliant InlineKeyboardButton."""
    kwargs = {"text": text}
    if url:
        kwargs["url"] = url
    if callback_data:
        kwargs["callback_data"] = callback_data
    if web_app:
        kwargs["web_app"] = web_app

    return InlineKeyboardButton(**kwargs)

def get_start_welcome_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    """Generates primary start welcome keyboard."""
    builder = InlineKeyboardBuilder()
    
    # Row 1 (Full Width): Add to Group
    builder.row(
        create_styled_button(
            text="➕ Add to Group",
            key="add_to_group",
            url=f"https://t.me/{bot_username}?startgroup=true"
        )
    )
    # Row 2: Updates & Support
    updates_username = getattr(config, "UPDATES_CHANNEL", "@pokeempireupdates").replace("@", "")
    builder.row(
        create_styled_button(
            text="📢 Updates",
            key="updates",
            url=f"https://t.me/{updates_username}"
        ),
        create_styled_button(
            text="🌲 Official Group",
            key="support",
            url=getattr(config, "SUPPORT_GROUP_URL", "https://t.me/PokeEmpire")
        )
    )
    # Row 3: Help & Stats
    builder.row(
        create_styled_button(
            text="ℹ️ Help & Guide",
            key="help",
            callback_data="dm_help"
        ),
        create_styled_button(
            text="📊 Chat Rankings",
            key="stats",
            callback_data="dm_rankings_info"
        )
    )
    return builder.as_markup()

def get_dm_menu_keyboard() -> InlineKeyboardMarkup:
    """Generates the primary Hub menu keyboard for DMs."""
    builder = InlineKeyboardBuilder()
    builder.row(
        create_styled_button(text="👤 Profile", key="profile", callback_data="dm_profile"),
        create_styled_button(text="📖 Pokédex", key="pokedex", callback_data="dm_dex_1")
    )
    builder.row(
        create_styled_button(text="⚔️ Quests", key="quests", callback_data="refresh_quests"),
        create_styled_button(text="🏰 Guilds", key="guilds", callback_data="dm_guild_info")
    )
    builder.row(
        create_styled_button(text="💳 Transactions", key="history", callback_data="dm_transactions"),
        create_styled_button(text="🎒 My Bag", key="bag", callback_data="dm_bag_1")
    )
    builder.row(
        create_styled_button(text="🏆 Leaderboard", key="leaderboard", callback_data="dm_leaderboard"),
        create_styled_button(text="🛡️ Battle Arena", key="battle", callback_data="dm_battle_menu")
    )
    builder.row(
        create_styled_button(text="🔄 Trade", key="trade", callback_data="dm_trade_info"),
        create_styled_button(text="🎟️ Redeem Code", key="redeem", callback_data="dm_redeem_info")
    )
    games_bot_user = getattr(config, "GAMES_BOT_USERNAME", "@PokeArenaBot").replace("@", "")
    builder.row(
        create_styled_button(text="🛒 Shop", key="shop", callback_data="dm_shop"),
        create_styled_button(text="🎮 Games Center", key="games", url=f"https://t.me/{games_bot_user}?start=hub")
    )
    builder.row(
        create_styled_button(text="🔥 Streak", key="streak", callback_data="dm_streak"),
        create_styled_button(text="📊 Chat Rankings", key="stats", callback_data="dm_rankings_info")
    )
    builder.row(
        create_styled_button(text="ℹ️ Help & Guide", key="help", callback_data="dm_help")
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

def get_tx_pagination_keyboard(user_id: int, page: int, max_page: int, is_dm: bool = False) -> InlineKeyboardMarkup:
    """Generates navigation buttons for browsing Transaction History."""
    builder = InlineKeyboardBuilder()
    nav_buttons = []
    if page > 1:
        nav_buttons.append(create_styled_button(text="◀️ Prev", key="prev", callback_data=f"tx_page_{user_id}_{page-1}"))
    else:
        nav_buttons.append(create_styled_button(text="⏹️", callback_data="tx_noop"))
    nav_buttons.append(create_styled_button(text=f"📄 {page}/{max_page}", callback_data="tx_noop"))
    if page < max_page:
        nav_buttons.append(create_styled_button(text="Next ➡️", key="next", callback_data=f"tx_page_{user_id}_{page+1}"))
    else:
        nav_buttons.append(create_styled_button(text="⏹️", callback_data="tx_noop"))
    if max_page > 1:
        builder.row(*nav_buttons)
    if is_dm:
        builder.row(create_styled_button(text="Back to Hub Menu", key="back", callback_data="dm_home"))
    else:
        builder.row(create_styled_button(text="👤 My Profile", key="profile", callback_data="dm_profile"))
    return builder.as_markup()

def get_pay_confirm_keyboard(sender_id: int, target_id: int, amount: int) -> InlineKeyboardMarkup:
    """Generates Green Accept and Red Decline buttons for coin transfer confirmation."""
    builder = InlineKeyboardBuilder()
    builder.row(
        create_styled_button(
            text="✔️ Accept",
            key="confirm",
            style="success",
            icon_custom_emoji_id="6255796213686208481",
            callback_data=f"pay_cnf_{sender_id}_{target_id}_{amount}"
        ),
        create_styled_button(
            text="❌ Decline",
            key="cancel",
            style="danger",
            icon_custom_emoji_id="5210952531676504517",
            callback_data=f"pay_dec_{sender_id}_{target_id}_{amount}"
        )
    )
    return builder.as_markup()

def get_gift_confirm_keyboard(sender_id: int, target_id: int, user_pokemon_id: int) -> InlineKeyboardMarkup:
    """Generates Green Accept and Red Decline buttons for Pokémon gift confirmation."""
    builder = InlineKeyboardBuilder()
    builder.row(
        create_styled_button(
            text="✔️ Accept",
            key="confirm",
            style="success",
            icon_custom_emoji_id="6255796213686208481",
            callback_data=f"gift_cnf_{sender_id}_{target_id}_{user_pokemon_id}"
        ),
        create_styled_button(
            text="❌ Decline",
            key="cancel",
            style="danger",
            icon_custom_emoji_id="5210952531676504517",
            callback_data=f"gift_dec_{sender_id}_{target_id}_{user_pokemon_id}"
        )
    )
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

GROUP_ONLY_GAMES_NOTICE = (
    "⚠️ <b>Games are only available in our official group!</b>\n\n"
    "To play mini-games, compete in PvP duels, and win Coins & Gems, please join our official group chat below:"
)

def get_official_group_keyboard() -> InlineKeyboardMarkup:
    """Returns an inline keyboard with a direct button to join the official group."""
    builder = InlineKeyboardBuilder()
    group_url = getattr(config, "SUPPORT_GROUP_URL", "https://t.me/PokeEmpire")
    builder.row(
        create_styled_button(text="👥 Join Official GC", key="support", url=group_url, style="primary")
    )
    return builder.as_markup()

