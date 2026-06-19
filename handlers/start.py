from aiogram import Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct
from database.models import User, Pokemon, UserPokemon
from keyboards.inline import get_dm_menu_keyboard, get_bag_pagination_keyboard, get_back_to_hub_keyboard, get_dex_pagination_keyboard
from utils.formatters import get_hp_bar, get_progress_bar, get_rarity_emoji, escape_md
import random

router = Router()

@router.message(CommandStart())
async def cmd_start(message: Message, db: AsyncSession):
    user_id = message.from_user.id
    username = message.from_user.username
    nickname = message.from_user.first_name

    # Check and register user
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user:
        user = User(
            id=user_id,
            username=username,
            nickname=nickname
        )
        db.add(user)
        await db.commit()

    if message.chat.type == "private":
        welcome_text = (
            f"🎮 **POKÉEMPIRE HUB** 🎮\n"
            f"👑 Welcome, Trainer **{escape_md(nickname)}**! 👑\n"
            f"───────────────\n\n"
            f"I spawn wild Pokémon in your active Telegram Groups based on message activity. "
            f"Be the first to guess their names and catch them!\n\n"
            f"Use the menu below to check your profile, view your caught Pokémon bag, browse the Pokédex checklist, or read the game guide.\n\n"
            f"👉 *Use the dashboard below to navigate:* "
        )
        await message.answer(welcome_text, reply_markup=get_dm_menu_keyboard(), parse_mode="Markdown")
    else:
        welcome_text = (
            f"🌲 **POKÉEMPIRE ACTIVE** 🌲\n"
            f"───────────────\n\n"
            f"Start chatting in this group, and a wild Pokémon will eventually appear!\n\n"
            f"👉 Use `/catch <name>` to catch it when it spawns.\n"
            f"👉 Message me in DMs to view your bag, profile, shop, and train!"
        )
        await message.answer(welcome_text, parse_mode="Markdown")

@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "❓ **POKÉEMPIRE GUIDE** ❓\n"
        "───────────────\n\n"
        "🌲 **Trainer Commands**:\n"
        "• `/profile` - View your Trainer level, coins, and titles.\n"
        "• `/pokemon <page>` - View your bag and paginated collection of caught Pokémon.\n"
        "• `/pokedex` - Review your caught species checklist & completion.\n"
        "• `/leaderboard` - Check the global leaderboard for coins and catches (alias `/lb`).\n"
        "• `/catch <name>` - Catch a wild Pokémon when one spawns in the group.\n"
        "• `/shop` - Purchase mystery boxes, Rare Candies, and Shiny Charms.\n"
        "• `/help` - Show this complete guide.\n\n"
        "🎮 **Earning Coins (Games)**:\n"
        "• `/daily` - Claim your daily reward (24h cooldown).\n"
        "• `/spin` - Spin the wheel of fortune (4h cooldown).\n"
        "• `/coinflip <amount> <heads/tails>` - Bet coins on a coin flip.\n"
        "• `/rps <amount> <rock/paper/scissors>` - Play rock-paper-scissors.\n"
        "• `/trivia` - Answer Pokémon questions for coins.\n"
        "• `/scribble` - Unscramble a Pokémon's name.\n\n"
        "🛡️ **Admin Group Commands**:\n"
        "• `/setspawn <threshold>` - Configure group spawn message threshold (Admins only).\n"
        "• `/toggle_spawns` - Enable or disable spawns in this group chat (Admins only)."
    )
    if message.chat.type == "private":
        await message.answer(help_text, reply_markup=get_back_to_hub_keyboard(), parse_mode="Markdown")
    else:
        await message.answer(help_text, parse_mode="Markdown")

@router.callback_query(F.data == "dm_home")
async def cb_dm_home(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id
    nickname = callback.from_user.first_name

    welcome_text = (
        f"🎮 **POKÉEMPIRE HUB** 🎮\n"
        f"👑 Welcome, Trainer **{escape_md(nickname)}**! 👑\n"
        f"───────────────\n\n"
        f"I spawn wild Pokémon in your active Telegram Groups based on message activity. "
        f"Be the first to guess their names and catch them!\n\n"
        f"Use the menu below to check your profile, view your caught Pokémon bag, browse the Pokédex checklist, or read the game guide.\n\n"
        f"👉 *Use the dashboard below to navigate:* "
    )
    # Check registration
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        user = User(
            id=user_id,
            username=callback.from_user.username,
            nickname=nickname
        )
        db.add(user)
        await db.commit()

    await callback.message.edit_text(welcome_text, reply_markup=get_dm_menu_keyboard(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "dm_profile")
async def cb_dm_profile(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id

    # Check registration
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        user = User(
            id=user_id,
            username=callback.from_user.username,
            nickname=callback.from_user.first_name
        )
        db.add(user)
        await db.commit()

    # Count total caught Pokémon
    count_stmt = select(func.count(UserPokemon.id)).where(UserPokemon.user_id == user_id)
    count_res = await db.execute(count_stmt)
    total_caught = count_res.scalar() or 0

    # Count unique caught Pokémon
    unique_stmt = select(func.count(distinct(UserPokemon.pokemon_id))).where(UserPokemon.user_id == user_id)
    unique_res = await db.execute(unique_stmt)
    unique_caught = unique_res.scalar() or 0

    # Count shiny Pokémon
    shiny_stmt = select(func.count(UserPokemon.id)).where(UserPokemon.user_id == user_id, UserPokemon.is_shiny == True)
    shiny_res = await db.execute(shiny_stmt)
    total_shiny = shiny_res.scalar() or 0

    # Count total species in database
    total_species_stmt = select(func.count(Pokemon.id))
    total_species_res = await db.execute(total_species_stmt)
    total_species = total_species_res.scalar() or 1

    # Calculate percentage
    dex_pct = (unique_caught / total_species) * 100
    dex_bar = get_progress_bar(unique_caught, total_species, 10, fill_char="▰", empty_char="▱")

    # Count caught by rarity
    rarity_stmt = select(Pokemon.rarity, func.count(UserPokemon.id)).join(UserPokemon).where(UserPokemon.user_id == user_id).group_by(Pokemon.rarity)
    rarity_res = await db.execute(rarity_stmt)
    rarity_counts = {r: count for r, count in rarity_res.all()}

    commons = rarity_counts.get("Common", 0)
    rares = rarity_counts.get("Rare", 0)
    epics = rarity_counts.get("Epic", 0)
    legendaries = rarity_counts.get("Legendary", 0)
    mythicals = rarity_counts.get("Mythical", 0)

    # Formatted coins
    formatted_coins = f"{user.coins:,}"
    user_nickname = user.nickname if (user and user.nickname) else (callback.from_user.first_name or "Trainer")

    # Calculate global rank position based on catches
    rank_stmt = (
        select(func.count())
        .select_from(
            select(User.id)
            .join(UserPokemon, UserPokemon.user_id == User.id)
            .group_by(User.id)
            .having(func.count(UserPokemon.id) > total_caught)
            .subquery()
        )
    )
    rank_res = await db.execute(rank_stmt)
    rank_position = (rank_res.scalar() or 0) + 1

    profile_card = (
        f"╭──「 🏆 Trainer Profile 」\n"
        f"├─➩ 🏓 User: {escape_md(user_nickname)}\n"
        f"├─➩ 🆔 ID: `{user.id}`\n"
        f"├─➩ 💰 Balance: `{formatted_coins} coins`\n"
        f"├─➩ ⚡ Pokémon: {unique_caught} (Total Catches: {total_caught})\n"
        f"├─➩ 🌍 Pokédex: {unique_caught}/{total_species} ({dex_pct:.3f}%)\n"
        f"├─➩ 🎁 Progress:\n"
        f"╰         {dex_bar}\n\n"
        f"╭─ Rarity Breakdown ─\n"
        f"├─➩ ⚪️ Common: {commons}\n"
        f"├─➩ 🔵 Rare: {rares}\n"
        f"├─➩ 🟣 Epic: {epics}\n"
        f"├─➩ 🟡 Legendary: {legendaries}\n"
        f"├─➩ 🌌 Mythical: {mythicals}\n"
        f"├─➩ ✨ Shiny: {total_shiny}\n"
        f"╰───────────────────\n\n"
        f"╭─ Global Rank ─\n"
        f"├─➩ 🏆 Position: #{rank_position}\n"
        f"╰───────────────────"
    )

    await callback.message.edit_text(profile_card, reply_markup=get_back_to_hub_keyboard(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "dm_help")
async def cb_dm_help(callback: CallbackQuery):
    help_text = (
        "❓ **POKÉEMPIRE GUIDE** ❓\n"
        "───────────────\n\n"
        "🌲 **Trainer Commands**:\n"
        "• `/profile` - View your Trainer level, coins, and titles.\n"
        "• `/pokemon <page>` - View your bag and paginated collection of caught Pokémon.\n"
        "• `/pokedex` - Review your caught species checklist & completion.\n"
        "• `/leaderboard` - Check the global leaderboard for coins and catches (alias `/lb`).\n"
        "• `/catch <name>` - Catch a wild Pokémon when one spawns in the group.\n"
        "• `/shop` - Purchase mystery boxes, Rare Candies, and Shiny Charms.\n"
        "• `/help` - Show this complete guide.\n\n"
        "🎮 **Earning Coins (Games)**:\n"
        "• `/daily` - Claim your daily reward (24h cooldown).\n"
        "• `/spin` - Spin the wheel of fortune (4h cooldown).\n"
        "• `/coinflip <amount> <heads/tails>` - Bet coins on a coin flip.\n"
        "• `/rps <amount> <rock/paper/scissors>` - Play rock-paper-scissors.\n"
        "• `/trivia` - Answer Pokémon questions for coins.\n"
        "• `/scribble` - Unscramble a Pokémon's name.\n\n"
        "🛡️ **Admin Group Commands**:\n"
        "• `/setspawn <threshold>` - Configure group spawn message threshold (Admins only).\n"
        "• `/toggle_spawns` - Enable or disable spawns in this group chat (Admins only).\n\n"
        "🎮 **Interactive Hub**: Use the buttons here to explore your trainer collection instantly!"
    )
    await callback.message.edit_text(help_text, reply_markup=get_back_to_hub_keyboard(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("dm_dex_"))
async def cb_dm_dex(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id
    
    # Parse page number
    try:
        page = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        page = 1

    # Count total species in database
    total_stmt = select(func.count(Pokemon.id))
    total_res = await db.execute(total_stmt)
    total_species = total_res.scalar() or 1

    # Count unique species caught by user
    caught_count_stmt = select(func.count(distinct(UserPokemon.pokemon_id))).where(UserPokemon.user_id == user_id)
    caught_count_res = await db.execute(caught_count_stmt)
    caught_count = caught_count_res.scalar() or 0

    # Get nickname
    u_stmt = select(User).where(User.id == user_id)
    u_res = await db.execute(u_stmt)
    user = u_res.scalar_one_or_none()
    nickname = user.nickname if user else callback.from_user.first_name

    if caught_count == 0:
        text = (
            f"👑 **{escape_md(nickname)}'s Pokédex** 👑\n"
            f"───────────────\n\n"
            f"⚠️ **Your Pokédex is empty!**\n"
            f"Catch wild Pokémon in a group chat first to register them in your Pokédex."
        )
        await callback.message.edit_text(text, reply_markup=get_back_to_hub_keyboard(), parse_mode="Markdown")
        await callback.answer()
        return

    per_page = 15
    max_page = (caught_count + per_page - 1) // per_page
    if page < 1: page = 1
    if page > max_page: page = max_page

    offset = (page - 1) * per_page

    # Query unique caught species sorted by ID for the current page
    poke_stmt = (
        select(
            Pokemon,
            func.count(UserPokemon.id).label("total_caught"),
            func.max(UserPokemon.is_shiny).label("has_shiny")
        )
        .join(UserPokemon)
        .where(UserPokemon.user_id == user_id)
        .group_by(Pokemon.id)
        .order_by(Pokemon.id)
        .offset(offset)
        .limit(per_page)
    )
    poke_res = await db.execute(poke_stmt)
    pairs = poke_res.all()

    # Query stats per generation
    gen_stats_stmt = (
        select(Pokemon.generation, func.count(distinct(UserPokemon.pokemon_id)))
        .join(UserPokemon)
        .where(UserPokemon.user_id == user_id)
        .group_by(Pokemon.generation)
    )
    gen_stats_res = await db.execute(gen_stats_stmt)
    gen_stats = {gen: count for gen, count in gen_stats_res.all()}

    gen_totals_stmt = select(Pokemon.generation, func.count(Pokemon.id)).group_by(Pokemon.generation)
    gen_totals_res = await db.execute(gen_totals_stmt)
    gen_totals = {gen: count for gen, count in gen_totals_res.all()}

    # Determine Pokedex Cover Image
    from utils.favorite import get_favorite_id
    fav_id = get_favorite_id(user_id)
    cover_image = None
    if fav_id:
        fav_stmt = select(Pokemon.image_url).join(UserPokemon, UserPokemon.pokemon_id == Pokemon.id).where(UserPokemon.id == fav_id, UserPokemon.user_id == user_id)
        fav_res = await db.execute(fav_stmt)
        cover_image = fav_res.scalar_one_or_none()
    
    if not cover_image:
        rand_stmt = select(Pokemon.image_url).join(UserPokemon, UserPokemon.pokemon_id == Pokemon.id).where(UserPokemon.user_id == user_id).order_by(func.random()).limit(1)
        rand_res = await db.execute(rand_stmt)
        cover_image = rand_res.scalar_one_or_none()

    percent = int((caught_count / total_species) * 100)
    bar = get_progress_bar(caught_count, total_species, 10, fill_char="█", empty_char="░")

    cover_link = f"[​]({cover_image})" if cover_image else ""
    text = (
        f"{cover_link}"
        f"👑 **{escape_md(nickname)}'s Pokédex** 👑 — Page {page}/{max_page}\n"
        f"Completion: **{caught_count}/{total_species}** species (**{percent}%**)\n"
        f"`[{bar}]` 🔴\n"
        f"───────────────\n"
    )

    current_gen = None
    rarity_badges = {
        "Common": "⚪️",
        "Rare": "🔵",
        "Epic": "🟣",
        "Legendary": "🟡",
        "Mythical": "🌌"
    }

    for p, total, has_shiny in pairs:
        if p.generation != current_gen:
            current_gen = p.generation
            text += f"\n**Generation {current_gen}** {gen_stats.get(current_gen, 0)}/{gen_totals.get(current_gen, 0)}\n"
            
        badge = rarity_badges.get(p.rarity, "⚪️")
        shiny_tag = " [✨]" if has_shiny else ""
        text += f"◈⌠{badge}⌡ #{p.id:03d} {p.name.title()}{shiny_tag} ×{total}\n"

    text += "\n───────────────"

    await callback.message.edit_text(text, reply_markup=get_dex_pagination_keyboard(page, max_page), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("dm_bag_"))
async def cb_dm_bag(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id
    
    # Parse page number
    try:
        page = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        page = 1

    # Count total caught
    count_stmt = select(func.count(UserPokemon.id)).where(UserPokemon.user_id == user_id)
    count_res = await db.execute(count_stmt)
    total = count_res.scalar() or 0

    if total == 0:
        text = (
            "🎒 **POKÉMON BAG** 🎒\n"
            "───────────────\n\n"
            "⚠️ Your bag is empty! Catch some Pokémon in a group chat first."
        )
        await callback.message.edit_text(text, reply_markup=get_back_to_hub_keyboard(), parse_mode="Markdown")
        await callback.answer()
        return

    per_page = 10
    max_page = (total + per_page - 1) // per_page
    if page < 1: page = 1
    if page > max_page: page = max_page

    offset = (page - 1) * per_page

    # Query owned Pokémon
    stmt = select(UserPokemon, Pokemon).join(Pokemon).where(
        UserPokemon.user_id == user_id
    ).order_by(UserPokemon.caught_at.desc()).offset(offset).limit(per_page)
    res = await db.execute(stmt)
    pairs = res.all()

    text = (
        f"🎒 **POKÉMON BAG** 🎒\n"
        f"Page {page} of {max_page} | Total: **{total} caught**\n"
        f"───────────────\n\n"
    )

    for idx, (up, p) in enumerate(pairs):
        num = idx + 1  # numbering local to page
        shiny_tag = "✨ " if up.is_shiny else ""
        r_emoji = get_rarity_emoji(p.rarity)
        name_display = f"\"{escape_md(up.nickname)}\"" if up.nickname else escape_md(p.name.title())
        text += f"**{num}.** {r_emoji} {shiny_tag}**{name_display}** `(Lvl {up.level}, ID: {up.id})`\n"

    text += "\n───────────────\n*Select a number below to inspect details:* "

    builder = InlineKeyboardBuilder()
    
    # Navigation row
    nav_buttons = []
    if page > 1:
        nav_buttons.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"dm_bag_{page-1}"))
    if page < max_page:
        nav_buttons.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"dm_bag_{page+1}"))
    if nav_buttons:
        builder.row(*nav_buttons)

    # Detail selection buttons row(s)
    detail_row = []
    for idx, (up, p) in enumerate(pairs):
        num = idx + 1
        detail_row.append(InlineKeyboardButton(text=str(num), callback_data=f"dm_detail_{up.id}_{page}"))
    
    for i in range(0, len(detail_row), 5):
        builder.row(*detail_row[i:i+5])

    builder.row(InlineKeyboardButton(text="🔙 Back to Hub Menu", callback_data="dm_home"))

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

def get_base_stats(rarity: str) -> dict:
    if rarity == "Common":
        return {"hp": 45, "atk": 49, "def": 49, "spd": 45}
    elif rarity == "Rare":
        return {"hp": 60, "atk": 65, "def": 65, "spd": 60}
    elif rarity == "Epic":
        return {"hp": 80, "atk": 85, "def": 80, "spd": 80}
    elif rarity == "Legendary":
        return {"hp": 100, "atk": 110, "def": 100, "spd": 100}
    elif rarity == "Mythical":
        return {"hp": 100, "atk": 100, "def": 100, "spd": 100}
    return {"hp": 50, "atk": 50, "def": 50, "spd": 50}

@router.callback_query(F.data.startswith("dm_detail_"))
async def cb_dm_detail(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    up_id = int(parts[2])
    page = int(parts[3])

    # Fetch UserPokemon
    stmt = select(UserPokemon, Pokemon).join(Pokemon).where(UserPokemon.id == up_id)
    res = await db.execute(stmt)
    pair = res.first()

    if not pair:
        await callback.answer("❌ Pokémon not found.", show_alert=True)
        return

    up, p = pair
    base = get_base_stats(p.rarity)
    
    # Calculate stats at level
    level = up.level
    hp_max = ((2 * base["hp"] + up.iv_hp) * level) // 100 + level + 10
    atk = ((2 * base["atk"] + up.iv_atk) * level) // 100 + 5
    def_stat = ((2 * base["def"] + up.iv_def) * level) // 100 + 5
    spd = ((2 * base["spd"] + up.iv_spd) * level) // 100 + 5

    iv_total = up.iv_hp + up.iv_atk + up.iv_def + up.iv_spd
    iv_pct = int((iv_total / 124) * 100)

    xp_needed = level * 100
    xp_bar = get_progress_bar(up.xp, xp_needed, 10, fill_char="█", empty_char="░")

    # Generate small progress bars for IVs
    iv_hp_bar = get_progress_bar(up.iv_hp, 31, 5, fill_char="▰", empty_char="▱")
    iv_atk_bar = get_progress_bar(up.iv_atk, 31, 5, fill_char="▰", empty_char="▱")
    iv_def_bar = get_progress_bar(up.iv_def, 31, 5, fill_char="▰", empty_char="▱")
    iv_spd_bar = get_progress_bar(up.iv_spd, 31, 5, fill_char="▰", empty_char="▱")

    shiny_tag = "✨ Shiny " if up.is_shiny else ""
    name_display = escape_md(up.nickname) if up.nickname else escape_md(p.name.title())
    orig_name_display = f" ({escape_md(p.name.title())})" if up.nickname else ""
    r_emoji = get_rarity_emoji(p.rarity)

    text = (
        f"[​]({p.image_url})"
        f"⭐ **POKÉMON DETAILS** ⭐\n"
        f"───────────────\n\n"
        f"• ID: `{up.id}`\n"
        f"• Name: {r_emoji} {shiny_tag}**{name_display}**{orig_name_display}\n"
        f"• Level: `Lvl {level}`\n"
        f"• Rarity: `{p.rarity}`\n"
        f"• IV Quality: **{iv_pct}%**\n\n"
        f"📈 **Experience**:\n"
        f"`[{xp_bar}]` **{up.xp}/{xp_needed} XP**\n\n"
        f"📊 **Combat Stats & IVs**:\n"
        f"• ❤️ HP: **{hp_max}** `({iv_hp_bar} +{up.iv_hp})`\n"
        f"• ⚔️ ATK: **{atk}** `({iv_atk_bar} +{up.iv_atk})`\n"
        f"• 🛡️ DEF: **{def_stat}** `({iv_def_bar} +{up.iv_def})`\n"
        f"• ⚡ SPD: **{spd}** `({iv_spd_bar} +{up.iv_spd})`\n"
        f"───────────────"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🏷️ Rename", callback_data=f"dm_rename_{up_id}_{page}"),
        InlineKeyboardButton(text="💸 Release", callback_data=f"dm_release_{up_id}_{page}")
    )
    builder.row(
        InlineKeyboardButton(text="⚔️ Train (Battle)", callback_data=f"dm_train_{up_id}_{page}")
    )
    builder.row(
        InlineKeyboardButton(text="🎒 Back to Bag", callback_data=f"dm_bag_{page}")
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

active_renames = {}

@router.callback_query(F.data.startswith("dm_rename_"))
async def cb_dm_rename(callback: CallbackQuery):
    parts = callback.data.split("_")
    up_id = int(parts[2])
    page = int(parts[3])
    user_id = callback.from_user.id

    active_renames[user_id] = {"up_id": up_id, "page": page}

    text = (
        f"🏷️ **RENAME POKÉMON** 🏷️\n"
        f"───────────────\n\n"
        f"Please enter the new nickname in your next message (maximum 15 characters)."
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="❌ Cancel", callback_data=f"dm_detail_{up_id}_{page}"))
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("dm_release_"))
async def cb_dm_release(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    up_id = int(parts[2])
    page = int(parts[3])
    user_id = callback.from_user.id

    # Fetch UserPokemon
    stmt = select(UserPokemon, Pokemon).join(Pokemon).where(UserPokemon.id == up_id)
    res = await db.execute(stmt)
    pair = res.first()

    if not pair:
        await callback.answer("❌ Pokémon already released.", show_alert=True)
        return

    up, p = pair

    # Calculate release coins
    base_release = {
        "Common": 100,
        "Rare": 200,
        "Epic": 500,
        "Legendary": 1500,
        "Mythical": 1500
    }
    base = base_release.get(p.rarity, 100)
    coins_earned = base + (up.level * 10)

    # Delete UserPokemon
    await db.delete(up)

    # Award coins to user
    user_stmt = select(User).where(User.id == user_id)
    user_res = await db.execute(user_stmt)
    user = user_res.scalar_one()
    user.coins += coins_earned
    await db.commit()

    text = (
        f"💸 **POKÉMON RELEASED** 💸\n"
        f"───────────────\n\n"
        f"You successfully released **{p.name.title()}** and received `💰 {coins_earned} coins`!\n\n"
        f"💰 **New Balance**: `💰 {user.coins} coins`\n"
        f"───────────────"
    )

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🎒 Back to Bag", callback_data=f"dm_bag_{page}"))

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer(f"Earned {coins_earned} coins!")

active_battles = {}

@router.callback_query(F.data.startswith("dm_train_"))
async def cb_dm_train(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    up_id = int(parts[2])
    page = int(parts[3])
    user_id = callback.from_user.id

    # Fetch User's Pokémon
    stmt = select(UserPokemon, Pokemon).join(Pokemon).where(UserPokemon.id == up_id)
    res = await db.execute(stmt)
    pair = res.first()

    if not pair:
        await callback.answer("❌ Pokémon not found.", show_alert=True)
        return

    up, p = pair
    base = get_base_stats(p.rarity)
    
    # User Pokémon stats
    level = up.level
    hp_max = ((2 * base["hp"] + up.iv_hp) * level) // 100 + level + 10
    atk = ((2 * base["atk"] + up.iv_atk) * level) // 100 + 5
    def_stat = ((2 * base["def"] + up.iv_def) * level) // 100 + 5
    spd = ((2 * base["spd"] + up.iv_spd) * level) // 100 + 5
    user_mon_name = escape_md(up.nickname) if up.nickname else escape_md(p.name.title())

    # Generate random wild Pokémon of equal level
    random_wild_id = random.randint(1, 1025)
    wild_stmt = select(Pokemon).where(Pokemon.id == random_wild_id)
    wild_res = await db.execute(wild_stmt)
    wild_p = wild_res.scalar_one()

    wild_base = get_base_stats(wild_p.rarity)
    wild_iv = random.randint(0, 31)
    
    wild_hp_max = ((2 * wild_base["hp"] + wild_iv) * level) // 100 + level + 10
    wild_atk = ((2 * wild_base["atk"] + wild_iv) * level) // 100 + 5
    wild_def = ((2 * wild_base["def"] + wild_iv) * level) // 100 + 5
    wild_spd = ((2 * wild_base["spd"] + wild_iv) * level) // 100 + 5

    wild_name_escaped = escape_md(wild_p.name.title())

    # Store battle session
    active_battles[user_id] = {
        "user_mon_id": up_id,
        "user_mon_name": user_mon_name,
        "user_mon_hp": hp_max,
        "user_mon_hp_max": hp_max,
        "user_mon_atk": atk,
        "user_mon_def": def_stat,
        "user_mon_spd": spd,
        "wild_name": wild_name_escaped,
        "wild_hp": wild_hp_max,
        "wild_hp_max": wild_hp_max,
        "wild_atk": wild_atk,
        "wild_def": wild_def,
        "wild_spd": wild_spd,
        "page": page,
        "turn": 1,
        "log": f"⚔️ Battle started! Lvl {level} {user_mon_name} encountered wild Lvl {level} {wild_name_escaped}!"
    }

    text = (
        f"⚔️ **BATTLE ENCOUNTER** ⚔️\n"
        f"───────────────\n\n"
        f"Trainer's **{user_mon_name}** `(Lvl {level})`\n"
        f"{get_hp_bar(hp_max, hp_max)}\n\n"
        f"Wild **{wild_p.name.title()}** `(Lvl {level})`\n"
        f"{get_hp_bar(wild_hp_max, wild_hp_max)}\n\n"
        f"───────────────\n"
        f"💬 {active_battles[user_id]['log']}"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⚔️ Attack", callback_data=f"bat_atk_{up_id}_{page}"),
        InlineKeyboardButton(text="🛡️ Defend", callback_data=f"bat_def_{up_id}_{page}")
    )
    builder.row(
        InlineKeyboardButton(text="🏃 Run", callback_data=f"bat_run_{up_id}_{page}")
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("bat_"))
async def cb_battle_action(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id
    if user_id not in active_battles:
        await callback.answer("❌ No active battle session.", show_alert=True)
        return

    parts = callback.data.split("_")
    action = parts[1]  # atk, def, run
    up_id = int(parts[2])
    page = int(parts[3])

    battle = active_battles[user_id]
    
    if action == "run":
        del active_battles[user_id]
        text = (
            f"🏃 **SURRENDERED** 🏃\n"
            f"───────────────\n\n"
            f"You surrendered and fled safely from wild **{battle['wild_name']}**.\n"
            f"───────────────"
        )
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Back to Pokémon Detail", callback_data=f"dm_detail_{up_id}_{page}"))
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        await callback.answer("Escaped!")
        return

    # Fetch User & Pokémon
    stmt = select(UserPokemon, Pokemon).join(Pokemon).where(UserPokemon.id == up_id)
    res = await db.execute(stmt)
    pair = res.first()

    if not pair:
        del active_battles[user_id]
        await callback.answer("❌ Pokémon not found.", show_alert=True)
        return

    up, p = pair
    level = up.level

    user_defending = action == "def"
    wild_defending = random.choice([True, False]) if battle["turn"] > 1 else False # wild has a chance to defend

    # Calculate damage formula helper
    def deal_dmg(atk_val, def_val, is_defending):
        base_dmg = (((2 * level // 5 + 2) * atk_val * 40 // def_val) // 50) + random.randint(2, 5)
        if is_defending:
            base_dmg = base_dmg // 2
        return max(1, base_dmg)

    logs = []
    
    # Order turns based on speed
    if battle["user_mon_spd"] >= battle["wild_spd"]:
        # User goes first
        if not user_defending:
            dmg = deal_dmg(battle["user_mon_atk"], battle["wild_def"], wild_defending)
            battle["wild_hp"] = max(0, battle["wild_hp"] - dmg)
            logs.append(f"💥 {battle['user_mon_name']} attacked wild {battle['wild_name']} for {dmg} damage!")
        else:
            logs.append(f"🛡️ {battle['user_mon_name']} braced for impact (defending)!")

        # Wild responds if alive
        if battle["wild_hp"] > 0:
            if not wild_defending:
                dmg = deal_dmg(battle["wild_atk"], battle["user_mon_def"], user_defending)
                battle["user_mon_hp"] = max(0, battle["user_mon_hp"] - dmg)
                logs.append(f"💥 Wild {battle['wild_name']} hit {battle['user_mon_name']} for {dmg} damage!")
            else:
                logs.append(f"🛡️ Wild {battle['wild_name']} is defending!")
    else:
        # Wild goes first
        if not wild_defending:
            dmg = deal_dmg(battle["wild_atk"], battle["user_mon_def"], user_defending)
            battle["user_mon_hp"] = max(0, battle["user_mon_hp"] - dmg)
            logs.append(f"💥 Wild {battle['wild_name']} hit {battle['user_mon_name']} for {dmg} damage!")
        else:
            logs.append(f"🛡️ Wild {battle['wild_name']} is defending!")

        # User responds if alive
        if battle["user_mon_hp"] > 0:
            if not user_defending:
                dmg = deal_dmg(battle["user_mon_atk"], battle["wild_def"], wild_defending)
                battle["wild_hp"] = max(0, battle["wild_hp"] - dmg)
                logs.append(f"💥 {battle['user_mon_name']} attacked wild {battle['wild_name']} for {dmg} damage!")
            else:
                logs.append(f"🛡️ {battle['user_mon_name']} braced for impact (defending)!")

    battle["turn"] += 1
    battle["log"] = "\n".join(logs)

    # Check outcomes
    if battle["wild_hp"] <= 0:
        # Victory!
        del active_battles[user_id]
        
        # Award XP & Coins
        xp_gain = random.randint(30, 60) * level
        coins_gain = random.randint(20, 50)
        
        up.xp += xp_gain
        xp_needed = level * 100
        
        # Fetch user from DB
        user_stmt = select(User).where(User.id == user_id)
        user_res = await db.execute(user_stmt)
        user = user_res.scalar_one()
        user.coins += coins_gain
        
        lvl_up_text = ""
        if up.xp >= xp_needed:
            up.level += 1
            up.xp = 0
            lvl_up_text = f"🌟 **LEVEL UP!** 🌟\n**{battle['user_mon_name']}** reached **Lvl {up.level}**!\n"
            
        await db.commit()

        victory_text = (
            f"🏆 **BATTLE VICTORY** 🏆\n"
            f"───────────────\n\n"
            f"🎉 **{battle['user_mon_name']}** defeated wild **{battle['wild_name']}**!\n\n"
            f"📈 **Rewards**:\n"
            f"• Experience: **+{xp_gain} XP**\n"
            f"• Coins earned: `💰 +{coins_gain} coins`\n"
            f"• New Balance: `💰 {user.coins} coins`\n\n"
            f"{lvl_up_text}"
            f"───────────────"
        )

        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Return to Pokémon Detail", callback_data=f"dm_detail_{up_id}_{page}"))
        await callback.message.edit_text(victory_text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        await callback.answer("Victory!")
        return

    elif battle["user_mon_hp"] <= 0:
        # Defeat!
        del active_battles[user_id]
        defeat_text = (
            f"💀 **BATTLE DEFEAT** 💀\n"
            f"───────────────\n\n"
            f"💀 **{battle['user_mon_name']}** fainted in battle against wild **{battle['wild_name']}**.\n\n"
            f"Train your Pokémon more or feed them Rare Candy to grow stronger!\n"
            f"───────────────"
        )
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Return to Pokémon Detail", callback_data=f"dm_detail_{up_id}_{page}"))
        await callback.message.edit_text(defeat_text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        await callback.answer("Defeated!")
        return

    # Update turn details
    hp_bar_user = get_hp_bar(battle['user_mon_hp'], battle['user_mon_hp_max'])
    hp_bar_wild = get_hp_bar(battle['wild_hp'], battle['wild_hp_max'])
    text = (
        f"⚔️ **BATTLE: TURN {battle['turn']}** ⚔️\n"
        f"───────────────\n\n"
        f"Trainer's **{battle['user_mon_name']}** `(Lvl {level})`\n"
        f"{hp_bar_user}\n\n"
        f"Wild **{battle['wild_name']}** `(Lvl {level})`\n"
        f"{hp_bar_wild}\n\n"
        f"───────────────\n"
        f"💬 **Log**:\n{battle['log']}\n"
        f"───────────────"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⚔️ Attack", callback_data=f"bat_atk_{up_id}_{page}"),
        InlineKeyboardButton(text="🛡️ Defend", callback_data=f"bat_def_{up_id}_{page}")
    )
    builder.row(
        InlineKeyboardButton(text="🏃 Run", callback_data=f"bat_run_{up_id}_{page}")
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

def is_renaming(message: Message) -> bool:
    return message.from_user.id in active_renames

@router.message(F.chat.type == "private", F.text, ~F.text.startswith("/"), is_renaming)
async def check_dm_text_messages(message: Message, db: AsyncSession):
    user_id = message.from_user.id
    session_data = active_renames[user_id]
    new_name = message.text.strip()
    
    if len(new_name) > 15:
        await message.answer("⚠️ Nickname must be 15 characters or less. Try again:")
        return
        
    up_id = session_data["up_id"]
    page = session_data["page"]
    
    # Update nickname in DB
    stmt = select(UserPokemon).where(UserPokemon.id == up_id)
    res = await db.execute(stmt)
    up = res.scalar_one_or_none()
    
    if up:
        up.nickname = new_name
        await db.commit()
        
        # Remove from active rename session
        del active_renames[user_id]
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Back to Pokémon Detail", callback_data=f"dm_detail_{up_id}_{page}"))
        await message.answer(f"✅ Nickname updated to **{escape_md(new_name)}** successfully!", reply_markup=builder.as_markup(), parse_mode="Markdown")
    else:
        del active_renames[user_id]
        await message.answer("❌ Error: Pokémon not found.")
    return

@router.message(Command("ping"))
async def cmd_ping(message: Message):
    import time
    from datetime import datetime, timezone
    
    start_time = time.time()
    sent_message = await message.answer("🏓 **Pinging...**", parse_mode="Markdown")
    latency_ms = int((time.time() - start_time) * 1000)
    
    transit_latency = int((datetime.now(timezone.utc) - message.date).total_seconds() * 1000)
    
    text = (
        f"🏓 **PONG!** 🏓\n"
        f"───────────────\n"
        f"📡 **API Latency**: `{latency_ms}ms`\n"
        f"⚡ **Transit Latency**: `{max(0, transit_latency)}ms`\n"
        f"───────────────"
    )
    await sent_message.edit_text(text, parse_mode="Markdown")

@router.message(F.new_chat_members)
async def on_new_chat_members(message: Message):
    # Check if the bot itself is in the new chat members list
    bot_user = await message.bot.get_me()
    if any(member.id == bot_user.id for member in message.new_chat_members):
        welcome_text = (
            f"🎮 **POKÉEMPIRE ACTIVATED** 🎮\n"
            f"───────────────\n\n"
            f"Hello everyone! I am **PokéEmpire Bot**, and I have just joined this group. 🌲\n\n"
            f"I spawn wild Pokémon in this chat based on message activity. "
            f"The first player to guess their name and use `/catch <name>` catches them!\n\n"
            f"⚙️ **Default Settings**:\n"
            f"• Spawns are **Enabled**.\n"
            f"• Spawn interval is initialized randomly (every 50-100 messages).\n\n"
            f"🛡️ **Admin Group Commands**:\n"
            f"• `/setspawn <threshold>` - Configure group spawn message threshold.\n"
            f"• `/toggle_spawns` - Enable/Disable spawns in this group.\n"
            f"• `/spawnsetting` - Check current spawn status and progress.\n\n"
            f"👤 **Player Commands**:\n"
            f"• `/help` - Show the complete game guide.\n"
            f"• `/leaderboard` (or `/lb`) - Check global rankings.\n\n"
            f"👉 Chat here to start triggering spawns, or message me in private DMs to check your profile, bag, and shop!"
        )
        await message.answer(welcome_text, parse_mode="Markdown")

