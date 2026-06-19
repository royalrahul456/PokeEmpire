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

@router.message(Command("pokedex"))
async def cmd_pokedex(message: Message, db: AsyncSession):
    user_id = message.from_user.id

    # Parse page number
    parts = message.text.split()
    page = 1
    if len(parts) > 1 and parts[1].isdigit():
        page = int(parts[1])

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
    nickname = user.nickname if (user and user.nickname) else (message.from_user.first_name or "Trainer")

    if caught_count == 0:
        await message.answer(
            f"👑 **{escape_md(nickname)}'s Pokédex** 👑\n"
            f"───────────────\n\n"
            f"⚠️ **Your Pokédex is empty!**\n"
            f"Catch wild Pokémon in a group chat first to register them in your Pokédex."
        )
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
    if max_page > 1:
        text += f"\n👉 Use `/pokedex <page>` to view other pages."

    await message.answer(text, parse_mode="Markdown")

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

@router.message(Command("leaderboard"))
@router.message(Command("lb"))
async def cmd_leaderboard(message: Message, db: AsyncSession):
    # Query top 10 users by coins
    coins_stmt = select(User).order_by(desc(User.coins)).limit(10)
    coins_res = await db.execute(coins_stmt)
    coins_users = coins_res.scalars().all()

    # Query top 10 users by catches
    catches_stmt = (
        select(User.nickname, User.username, func.count(UserPokemon.id).label("total_catches"))
        .join(UserPokemon, UserPokemon.user_id == User.id)
        .group_by(User.id)
        .order_by(desc(func.count(UserPokemon.id)))
        .limit(10)
    )
    catches_res = await db.execute(catches_stmt)
    catches_data = catches_res.all()

    # Format coins leaderboard
    coins_rows = []
    if coins_users:
        for idx, u in enumerate(coins_users):
            rank_prefix = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx + 1}."
            username_str = f" (@{escape_md(u.username)})" if u.username else ""
            coins_rows.append(f"{rank_prefix} **{escape_md(u.nickname)}**{username_str} • `💰 {u.coins}c`")
        coins_list = "\n".join(coins_rows)
    else:
        coins_list = "• *No trainers registered yet.*"

    # Format catches leaderboard
    catches_rows = []
    if catches_data:
        for idx, row in enumerate(catches_data):
            rank_prefix = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx + 1}."
            username_str = f" (@{escape_md(row.username)})" if row.username else ""
            catches_rows.append(f"{rank_prefix} **{escape_md(row.nickname)}**{username_str} • `🧬 {row.total_catches} caught`")
        catches_list = "\n".join(catches_rows)
    else:
        catches_list = "• *No trainers have caught Pokémon yet.*"

    leaderboard_card = (
        f"🏆 **GLOBAL LEADERBOARD** 🏆\n"
        f"───────────────\n\n"
        f"💰 **TOP 10 COINS**\n"
        f"{coins_list}\n\n"
        f"───────────────\n\n"
        f"🎒 **TOP 10 CATCHES**\n"
        f"{catches_list}\n\n"
        f"───────────────"
    )

    await message.answer(leaderboard_card, parse_mode="Markdown")

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

