from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct, desc, case
from sqlalchemy.orm import joinedload
from database.models import User, UserPokemon, Pokemon
from utils.formatters import get_hp_bar, get_progress_bar, get_rarity_emoji, escape_md

router = Router()

@router.message(Command("profile"))
async def cmd_profile(message: Message, db: AsyncSession):
    user_id = message.from_user.id

    # Check registration
    u_stmt = select(User).where(User.id == user_id)
    u_res = await db.execute(u_stmt)
    user = u_res.scalar_one_or_none()

    if not user:
        await message.answer("⚠️ You haven't caught any Pokémon yet! Join a group chat and catch a wild Pokémon using `/catch <name>` to start.")
        return

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
    user_nickname = user.nickname if (user and user.nickname) else (message.from_user.first_name or "Trainer")

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
    await message.answer(profile_card, parse_mode="Markdown")

@router.message(Command("pokemon"))
async def cmd_pokemon_list(message: Message):
    await message.answer(
        "🎒 **The Pokémon Bag is now retired!**\n"
        "All collections are managed directly via your Pokédex.\n\n"
        "👉 Use `/pokedex` to view your collection checklist and progress!\n"
        "👉 Use `/fav <pokedex_id>` to set a Pokédex cover favorite."
    )

async def get_pokedex_data(user_id: int, nickname: str, page: int, rarity_filter: str, db: AsyncSession):
    # 1. Query total species in database matching the filter
    if rarity_filter and rarity_filter != "All":
        total_stmt = select(func.count(Pokemon.id)).where(Pokemon.rarity == rarity_filter)
    else:
        total_stmt = select(func.count(Pokemon.id))
        
    total_res = await db.execute(total_stmt)
    total_species = total_res.scalar() or 1

    # 2. Query unique species caught by user matching the filter
    if rarity_filter and rarity_filter != "All":
        caught_count_stmt = (
            select(func.count(distinct(UserPokemon.pokemon_id)))
            .join(Pokemon)
            .where(UserPokemon.user_id == user_id, Pokemon.rarity == rarity_filter)
        )
    else:
        caught_count_stmt = select(func.count(distinct(UserPokemon.pokemon_id))).where(UserPokemon.user_id == user_id)
        
    caught_count_res = await db.execute(caught_count_stmt)
    caught_count = caught_count_res.scalar() or 0

    if caught_count == 0:
        filter_str = f" ({rarity_filter})" if rarity_filter and rarity_filter != "All" else ""
        text = (
            f"⭐ **{escape_md(nickname)}'s Pokédex** ⭐{filter_str}\n"
            f"───────────────\n\n"
            f"⚠️ **Your Pokédex is empty!**\n"
            f"Catch wild Pokémon in a group chat first to register them in your Pokédex."
        )
        return text, 0, 0

    per_page = 15
    max_page = (caught_count + per_page - 1) // per_page
    if page < 1: page = 1
    if page > max_page: page = max_page

    offset = (page - 1) * per_page

    # 3. Query unique caught species sorted by ID for the current page
    if rarity_filter and rarity_filter != "All":
        poke_stmt = (
            select(
                Pokemon,
                func.count(UserPokemon.id).label("total_caught"),
                func.max(case((UserPokemon.is_shiny == True, 1), else_=0)).label("has_shiny")
            )
            .join(UserPokemon)
            .where(UserPokemon.user_id == user_id, Pokemon.rarity == rarity_filter)
            .group_by(Pokemon.id)
            .order_by(Pokemon.id)
            .offset(offset)
            .limit(per_page)
        )
    else:
        poke_stmt = (
            select(
                Pokemon,
                func.count(UserPokemon.id).label("total_caught"),
                func.max(case((UserPokemon.is_shiny == True, 1), else_=0)).label("has_shiny")
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

    # 4. Query stats per generation
    if rarity_filter and rarity_filter != "All":
        gen_stats_stmt = (
            select(Pokemon.generation, func.count(distinct(UserPokemon.pokemon_id)))
            .join(UserPokemon)
            .where(UserPokemon.user_id == user_id, Pokemon.rarity == rarity_filter)
            .group_by(Pokemon.generation)
        )
        gen_totals_stmt = (
            select(Pokemon.generation, func.count(Pokemon.id))
            .where(Pokemon.rarity == rarity_filter)
            .group_by(Pokemon.generation)
        )
    else:
        gen_stats_stmt = (
            select(Pokemon.generation, func.count(distinct(UserPokemon.pokemon_id)))
            .join(UserPokemon)
            .where(UserPokemon.user_id == user_id)
            .group_by(Pokemon.generation)
        )
        gen_totals_stmt = select(Pokemon.generation, func.count(Pokemon.id)).group_by(Pokemon.generation)
        
    gen_stats_res = await db.execute(gen_stats_stmt)
    gen_stats = {gen: count for gen, count in gen_stats_res.all()}

    gen_totals_res = await db.execute(gen_totals_stmt)
    gen_totals = {gen: count for gen, count in gen_totals_res.all()}

    # Determine Pokedex Cover Image
    from utils.favorite import get_favorite_id
    fav_id = get_favorite_id(user_id)
    cover_image = None
    if fav_id:
        fav_stmt = select(Pokemon.image_url).join(UserPokemon, UserPokemon.pokemon_id == Pokemon.id).where(Pokemon.id == fav_id, UserPokemon.user_id == user_id)
        fav_res = await db.execute(fav_stmt)
        cover_image = fav_res.scalar_one_or_none()
    
    if not cover_image:
        rand_stmt = select(Pokemon.image_url).join(UserPokemon, UserPokemon.pokemon_id == Pokemon.id).where(UserPokemon.user_id == user_id).order_by(func.random()).limit(1)
        rand_res = await db.execute(rand_stmt)
        cover_image = rand_res.scalar_one_or_none()

    percent = int((caught_count / total_species) * 100)
    bar = get_progress_bar(caught_count, total_species, 10, fill_char="█", empty_char="░")

    cover_link = f"[​]({cover_image})" if cover_image else ""
    filter_label = f" ({rarity_filter})" if rarity_filter and rarity_filter != "All" else ""
    text = (
        f"{cover_link}"
        f"⭐ **{escape_md(nickname)}'s Pokédex** ⭐{filter_label} — Page {page}/{max_page}\n"
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
        text += f"◆ [ {badge} ] #{p.id:03d} {p.name.title()}{shiny_tag} x{total}\n"

    text += "\n───────────────"
    return text, page, max_page

def get_pokedex_keyboard(user_id: int, page: int, max_page: int, rarity_filter: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    # Row 1: Tab Switches
    builder.row(
        InlineKeyboardButton(text="⭐ Collection", callback_data=f"pd_tab_{user_id}_col"),
        InlineKeyboardButton(text="🖼️ Cover Info", callback_data=f"pd_tab_{user_id}_cov")
    )
    
    # Row 2: Pagination Buttons
    prev_page = page - 1 if page > 1 else max_page
    next_page = page + 1 if page < max_page else 1
    
    builder.row(
        InlineKeyboardButton(text="⬅️", callback_data=f"pd_page_{user_id}_{prev_page}_{rarity_filter}"),
        InlineKeyboardButton(text=f"{page}/{max_page}", callback_data="pd_page_info"),
        InlineKeyboardButton(text="➡️", callback_data=f"pd_page_{user_id}_{next_page}_{rarity_filter}")
    )
    
    # Row 3: Filter by Rarity Button
    builder.row(
        InlineKeyboardButton(text="🔍 Filter by Rarity", callback_data=f"pd_rarity_{user_id}_{page}_{rarity_filter}")
    )
    
    return builder.as_markup()

def get_rarity_filter_keyboard(user_id: int, current_page: int, current_filter: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    builder.row(
        InlineKeyboardButton(text="⚪ Common", callback_data=f"pd_setfilter_{user_id}_Common"),
        InlineKeyboardButton(text="🔵 Rare", callback_data=f"pd_setfilter_{user_id}_Rare")
    )
    builder.row(
        InlineKeyboardButton(text="🟣 Epic", callback_data=f"pd_setfilter_{user_id}_Epic"),
        InlineKeyboardButton(text="🟡 Legendary", callback_data=f"pd_setfilter_{user_id}_Legendary")
    )
    builder.row(
        InlineKeyboardButton(text="🌌 Mythical", callback_data=f"pd_setfilter_{user_id}_Mythical"),
        InlineKeyboardButton(text="🌍 All", callback_data=f"pd_setfilter_{user_id}_All")
    )
    builder.row(
        InlineKeyboardButton(text="🔙 Back", callback_data=f"pd_page_{user_id}_{current_page}_{current_filter}")
    )
    
    return builder.as_markup()

@router.message(Command("pokedex"))
async def cmd_pokedex(message: Message, db: AsyncSession):
    user_id = message.from_user.id

    # Parse page number
    parts = message.text.split()
    page = 1
    if len(parts) > 1 and parts[1].isdigit():
        page = int(parts[1])

    u_stmt = select(User).where(User.id == user_id)
    u_res = await db.execute(u_stmt)
    user = u_res.scalar_one_or_none()
    nickname = user.nickname if (user and user.nickname) else (message.from_user.first_name or "Trainer")

    text, final_page, max_page = await get_pokedex_data(user_id, nickname, page, "All", db)
    
    if max_page == 0:
        await message.answer(text, parse_mode="Markdown")
        return

    kb = get_pokedex_keyboard(user_id, final_page, max_page, "All")
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("pd_tab_"))
async def cb_pokedex_tab(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    user_id = int(parts[2])
    tab = parts[3]
    
    if callback.from_user.id != user_id:
        await callback.answer("❌ This is not your Pokédex! Use /pokedex to view yours.", show_alert=True)
        return
        
    if tab == "cov":
        text = (
            f"🖼️ **Pokédex Cover Favorite**\n"
            f"───────────────\n\n"
            f"Set your favorite Pokémon as the Pokédex cover illustration!\n\n"
            f"👉 **How to set**: Type `/fav <pokedex_id>` in chat.\n"
            f"*(e.g., `/fav 251` to set Celebi as cover)*"
        )
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Back to Collection", callback_data=f"pd_page_{user_id}_1_All"))
        
        try:
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        except Exception:
            pass
        await callback.answer()
    else:
        # Default/collection back trigger
        u_stmt = select(User).where(User.id == user_id)
        u_res = await db.execute(u_stmt)
        user = u_res.scalar_one_or_none()
        nickname = user.nickname if (user and user.nickname) else (callback.from_user.first_name or "Trainer")
        
        text, final_page, max_page = await get_pokedex_data(user_id, nickname, 1, "All", db)
        kb = get_pokedex_keyboard(user_id, final_page, max_page, "All")
        
        try:
            await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
        except Exception:
            pass
        await callback.answer()

@router.callback_query(F.data.startswith("pd_page_"))
async def cb_pokedex_page(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    user_id = int(parts[2])
    page = int(parts[3])
    rarity_filter = parts[4]
    
    if callback.from_user.id != user_id:
        await callback.answer("❌ This is not your Pokédex! Use /pokedex to view yours.", show_alert=True)
        return
        
    u_stmt = select(User).where(User.id == user_id)
    u_res = await db.execute(u_stmt)
    user = u_res.scalar_one_or_none()
    nickname = user.nickname if (user and user.nickname) else (callback.from_user.first_name or "Trainer")
    
    text, final_page, max_page = await get_pokedex_data(user_id, nickname, page, rarity_filter, db)
    kb = get_pokedex_keyboard(user_id, final_page, max_page, rarity_filter)
    
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass
    await callback.answer()

@router.callback_query(F.data.startswith("pd_rarity_"))
async def cb_pokedex_rarity_menu(callback: CallbackQuery):
    parts = callback.data.split("_")
    user_id = int(parts[2])
    page = int(parts[3])
    rarity_filter = parts[4]
    
    if callback.from_user.id != user_id:
        await callback.answer("❌ This is not your Pokédex! Use /pokedex to view yours.", show_alert=True)
        return
        
    text = (
        f"🔍 **Filter Pokédex by Rarity**\n"
        f"───────────────\n\n"
        f"Choose a rarity tier below to filter your species list:"
    )
    kb = get_rarity_filter_keyboard(user_id, page, rarity_filter)
    
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass
    await callback.answer()

@router.callback_query(F.data.startswith("pd_setfilter_"))
async def cb_pokedex_set_filter(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    user_id = int(parts[2])
    rarity_filter = parts[3]
    
    if callback.from_user.id != user_id:
        await callback.answer("❌ This is not your Pokédex! Use /pokedex to view yours.", show_alert=True)
        return
        
    u_stmt = select(User).where(User.id == user_id)
    u_res = await db.execute(u_stmt)
    user = u_res.scalar_one_or_none()
    nickname = user.nickname if (user and user.nickname) else (callback.from_user.first_name or "Trainer")
    
    text, final_page, max_page = await get_pokedex_data(user_id, nickname, 1, rarity_filter, db)
    kb = get_pokedex_keyboard(user_id, final_page, max_page, rarity_filter)
    
    try:
        await callback.message.edit_text(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass
    await callback.answer(f"Filtered by: {rarity_filter}")

@router.message(Command("check"))
async def cmd_check_pokemon(message: Message, db: AsyncSession):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("⚠️ Format: `/check <pokemon_name_or_id>`\n(e.g., `/check bulbasaur` or `/check 1`)")
        return

    query = " ".join(parts[1:]).strip().lower()

    # Query species
    if query.isdigit():
        poke_stmt = select(Pokemon).where(Pokemon.id == int(query))
    else:
        poke_stmt = select(Pokemon).where(Pokemon.name.ilike(query))

    poke_res = await db.execute(poke_stmt)
    pokemon = poke_res.scalar_one_or_none()

    if not pokemon:
        await message.answer(f"❌ Pokémon '{escape_md(query)}' not found in database.")
        return

    # Query owners list
    owners_stmt = (
        select(User.nickname, User.username, func.count(UserPokemon.id))
        .join(UserPokemon, UserPokemon.user_id == User.id)
        .where(UserPokemon.pokemon_id == pokemon.id)
        .group_by(User.id)
        .order_by(func.count(UserPokemon.id).desc())
    )
    owners_res = await db.execute(owners_stmt)
    owners = owners_res.all()

    # Format owner list
    if owners:
        owner_rows = []
        for idx, (nickname, username, count) in enumerate(owners):
            num = idx + 1
            username_str = f" (@{escape_md(username)})" if username else ""
            owner_rows.append(f"**{num}.** **{escape_md(nickname)}**{username_str} `x{count}`")
        owners_list = "\n".join(owner_rows)
    else:
        owners_list = "• *No trainer owns this species yet.*"

    r_emoji = get_rarity_emoji(pokemon.rarity)
    
    text = (
        f"[​]({pokemon.image_url})"
        f"🔍 **SPECIES CHECK** 🔍\n"
        f"───────────────\n"
        f"🎉 Species: {r_emoji} **{pokemon.name.title()}** {r_emoji}\n"
        f"• **National ID**: `#{pokemon.id:03d}`\n"
        f"• **Rarity**: `{pokemon.rarity}`\n"
        f"• **Generation**: `{pokemon.generation}`\n"
        f"───────────────\n"
        f"👤 **OWNERS LIST:**\n"
        f"{owners_list}\n"
        f"───────────────"
    )

    await message.answer(text, parse_mode="Markdown")

async def get_leaderboard_text(lb_type: str, db: AsyncSession) -> str:
    if lb_type == "coins":
        coins_stmt = select(User).order_by(desc(User.coins)).limit(10)
        coins_res = await db.execute(coins_stmt)
        coins_users = coins_res.scalars().all()
        
        text = "🏆 **TOP 10 — Coins**\n\n"
        if coins_users:
            for idx, u in enumerate(coins_users):
                rank = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx + 1}."
                text += f"{rank} {escape_md(u.nickname or 'Trainer')}  -> {u.coins}\n"
        else:
            text += "• *No trainers registered yet.*"
            
    elif lb_type == "catches":
        catches_stmt = (
            select(User.nickname, func.count(UserPokemon.id).label("total_catches"))
            .join(UserPokemon, UserPokemon.user_id == User.id)
            .group_by(User.id)
            .order_by(desc(func.count(UserPokemon.id)))
            .limit(10)
        )
        catches_res = await db.execute(catches_stmt)
        catches_data = catches_res.all()
        
        text = "🏆 **TOP 10 — Pokémon**\n\n"
        if catches_data:
            for idx, row in enumerate(catches_data):
                rank = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx + 1}."
                text += f"{rank} {escape_md(row.nickname or 'Trainer')}  -> {row.total_catches}\n"
        else:
            text += "• *No catches registered yet.*"
            
    elif lb_type == "streak":
        from utils.streak import get_top_streaks
        top_users = await get_top_streaks(10)
        
        text = "🏆 **TOP 10 — Streaks**\n\n"
        if top_users:
            for idx, (user_id, uinfo) in enumerate(top_users):
                rank = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx + 1}."
                
                stmt = select(User.nickname).where(User.id == user_id)
                res = await db.execute(stmt)
                nickname = res.scalar_one_or_none() or "Trainer"
                
                best_streak = uinfo.get("best_streak", 0)
                text += f"{rank} {escape_md(nickname)}  -> {best_streak} days\n"
        else:
            text += "• *No active streaks recorded yet.*"
            
    return text

def get_leaderboard_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🏆 Pokémon", callback_data="lb_type_catches"),
        InlineKeyboardButton(text="💰 Coins", callback_data="lb_type_coins"),
        InlineKeyboardButton(text="🔥 Streak", callback_data="lb_type_streak")
    )
    return builder.as_markup()

@router.message(Command("leaderboard"))
@router.message(Command("lb"))
async def cmd_leaderboard(message: Message, db: AsyncSession):
    arceus_photo = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/493.png"
    text = await get_leaderboard_text("catches", db)
    
    await message.answer_photo(
        photo=arceus_photo,
        caption=text,
        reply_markup=get_leaderboard_keyboard(),
        parse_mode="Markdown"
    )

@router.callback_query(F.data.startswith("lb_type_"))
async def cb_leaderboard_type(callback: CallbackQuery, db: AsyncSession):
    lb_type = callback.data.replace("lb_type_", "")
    text = await get_leaderboard_text(lb_type, db)
    
    try:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=get_leaderboard_keyboard(),
            parse_mode="Markdown"
        )
    except Exception:
        pass
    await callback.answer()

@router.message(Command("fav"))
async def cmd_fav(message: Message, db: AsyncSession):
    user_id = message.from_user.id
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("⚠️ Format: `/fav <pokedex_id>`\n(e.g., `/fav 251` to set Celebi as your favorite)")
        return
    
    pokedex_id = int(parts[1])
    
    # Verify user owns at least one Pokémon of this species
    stmt = select(UserPokemon).options(joinedload(UserPokemon.pokemon)).where(
        UserPokemon.pokemon_id == pokedex_id,
        UserPokemon.user_id == user_id
    ).limit(1)
    res = await db.execute(stmt)
    up = res.scalar()
    
    if not up:
        await message.answer("❌ You don't own a Pokémon with that Pokédex ID in your collection!")
        return
        
    p = up.pokemon
    from utils.favorite import set_favorite_id
    set_favorite_id(user_id, pokedex_id)
    
    # Check if they own any shiny version of this species
    shiny_stmt = select(UserPokemon.is_shiny).where(
        UserPokemon.pokemon_id == pokedex_id,
        UserPokemon.user_id == user_id,
        UserPokemon.is_shiny == True
    ).limit(1)
    shiny_res = await db.execute(shiny_stmt)
    has_shiny = shiny_res.scalar() is not None
    
    shiny_tag = "✨ Shiny " if has_shiny else ""
    await message.answer(f"⭐ **{shiny_tag}{p.name.title()}** (Pokédex ID: #{pokedex_id:03d}) has been set as your Pokédex cover favorite!")

@router.message(Command("unfav"))
async def cmd_unfav(message: Message):
    user_id = message.from_user.id
    from utils.favorite import set_favorite_id
    set_favorite_id(user_id, None)
    await message.answer("❌ Cleared your favorite cover. A random Pokémon from your bag will be shown instead.")

@router.message(Command("search"))
@router.message(Command("s"))
async def cmd_search(message: Message, db: AsyncSession):
    user_id = message.from_user.id
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("⚠️ Format: `/search <pokemon_name_or_id>`\n(e.g., `/search bulbasaur` or `/search 1`)")
        return
        
    query = " ".join(parts[1:]).strip().lower()
    
    # Query species
    if query.isdigit():
        poke_stmt = select(Pokemon).where(Pokemon.id == int(query))
    else:
        poke_stmt = select(Pokemon).where(Pokemon.name.ilike(query))
        
    poke_res = await db.execute(poke_stmt)
    pokemon = poke_res.scalar_one_or_none()
    
    if not pokemon:
        await message.answer(f"❌ Pokémon '{escape_md(query)}' not found in database.")
        return
        
    # Query player's own catches of this species
    catches_stmt = select(UserPokemon).where(
        UserPokemon.user_id == user_id,
        UserPokemon.pokemon_id == pokemon.id
    ).order_by(UserPokemon.caught_at.desc())
    catches_res = await db.execute(catches_stmt)
    user_catches = catches_res.scalars().all()
    
    r_emoji = get_rarity_emoji(pokemon.rarity)
    cover_link = f"[​]({pokemon.image_url})"
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Owners", callback_data=f"show_owners_{pokemon.id}")]
    ])
    
    if len(user_catches) > 0:
        # Find best caught (highest IV)
        best_up = None
        best_iv_pct = -1
        for up in user_catches:
            iv_total = up.iv_hp + up.iv_atk + up.iv_def + up.iv_spd
            iv_pct = int((iv_total / 124) * 100)
            if iv_pct > best_iv_pct:
                best_iv_pct = iv_pct
                best_up = up
                
        shiny_label = "✨ Yes" if best_up.is_shiny else "❌ No"
        text = (
            f"{cover_link}"
            f"🔍 **SEARCH RESULTS** 🔍\n"
            f"───────────────\n"
            f"🎉 Species: {r_emoji} **{pokemon.name.title()}** {r_emoji}\n"
            f"🆔 Pokédex ID: `#{pokemon.id:03d}`\n"
            f"⭐ Rarity: `{pokemon.rarity}`\n"
            f"🧬 Total Caught: `{len(user_catches)} caught`\n\n"
            f"🏆 **Your Best Pokémon**:\n"
            f"• Level: `Lvl {best_up.level}`\n"
            f"• IV Quality: `{best_iv_pct}%` (HP: {best_up.iv_hp}, ATK: {best_up.iv_atk}, DEF: {best_up.iv_def}, SPD: {best_up.iv_spd})\n"
            f"• Shiny: `{shiny_label}`\n"
            f"───────────────"
        )
    else:
        text = (
            f"{cover_link}"
            f"🔍 **SEARCH RESULTS** 🔍\n"
            f"───────────────\n"
            f"🎉 Species: {r_emoji} **{pokemon.name.title()}** {r_emoji}\n"
            f"🆔 Pokédex ID: `#{pokemon.id:03d}`\n"
            f"⭐ Rarity: `{pokemon.rarity}`\n"
            f"🧬 Total Caught: `0 caught` (You haven't caught this species yet!)\n"
            f"───────────────"
        )
        
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("show_owners_"))
async def cb_show_owners(callback: CallbackQuery, db: AsyncSession):
    try:
        pokemon_id = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        await callback.answer("⚠️ Invalid action.")
        return
        
    # Fetch Pokémon details
    poke_stmt = select(Pokemon).where(Pokemon.id == pokemon_id)
    poke_res = await db.execute(poke_stmt)
    pokemon = poke_res.scalar_one_or_none()
    
    if not pokemon:
        await callback.answer("⚠️ Pokémon not found.")
        return
        
    # Query owners list
    owners_stmt = (
        select(User.nickname, User.username, func.count(UserPokemon.id))
        .join(UserPokemon, UserPokemon.user_id == User.id)
        .where(UserPokemon.pokemon_id == pokemon_id)
        .group_by(User.id)
        .order_by(func.count(UserPokemon.id).desc())
    )
    owners_res = await db.execute(owners_stmt)
    owners = owners_res.all()
    
    # Format list
    if owners:
        owner_rows = []
        for idx, (nickname, username, count) in enumerate(owners):
            num = idx + 1
            username_str = f" (@{escape_md(username)})" if username else ""
            owner_rows.append(f"**{num}.** **{escape_md(nickname)}**{username_str} `x{count}`")
        owners_list = "\n".join(owner_rows)
    else:
        owners_list = "• *No trainer owns this species yet.*"
        
    text = (
        f"👥 **OWNERS OF {pokemon.name.upper()}** 👥\n"
        f"───────────────\n"
        f"{owners_list}\n"
        f"───────────────"
    )
    
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

