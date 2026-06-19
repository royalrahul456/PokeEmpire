from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct, desc
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
        f"├─➩ 🏓 User: {escape_md(user.nickname)}\n"
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
async def cmd_pokemon_list(message: Message, db: AsyncSession):
    user_id = message.from_user.id

    # Parse page number
    parts = message.text.split()
    page = 1
    if len(parts) > 1 and parts[1].isdigit():
        page = int(parts[1])

    # Check registration
    u_stmt = select(User).where(User.id == user_id)
    u_res = await db.execute(u_stmt)
    user = u_res.scalar_one_or_none()
    if not user:
        await message.answer("⚠️ You haven't caught any Pokémon yet.")
        return

    # Count total caught
    count_stmt = select(func.count(UserPokemon.id)).where(UserPokemon.user_id == user_id)
    count_res = await db.execute(count_stmt)
    total = count_res.scalar() or 0

    if total == 0:
        await message.answer("⚠️ Your bag is empty! Catch some Pokémon first.")
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
        num = offset + idx + 1
        shiny_tag = "✨ " if up.is_shiny else ""
        r_emoji = get_rarity_emoji(p.rarity)
        name_display = f"\"{up.nickname}\"" if up.nickname else p.name.title()
        text += f"**{num}.** {r_emoji} {shiny_tag}**{escape_md(name_display)}** `(Lvl {up.level}, ID: {up.id})`\n"

    text += "\n───────────────"
    if max_page > 1:
        text += f"\n👉 Use `/pokemon <page>` to view other pages."

    await message.answer(text, parse_mode="Markdown")

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

    if caught_count == 0:
        await message.answer(
            "🏆 **POKÉDEX** 🏆\n"
            "───────────────\n\n"
            "⚠️ **Your Pokédex is empty!**\n"
            "Catch wild Pokémon in a group chat first to register them in your Pokédex."
        )
        return

    per_page = 30
    max_page = (caught_count + per_page - 1) // per_page
    if page < 1: page = 1
    if page > max_page: page = max_page

    offset = (page - 1) * per_page

    # Query unique caught species sorted by ID for the current page
    poke_stmt = select(Pokemon).join(UserPokemon).where(
        UserPokemon.user_id == user_id
    ).group_by(Pokemon.id).order_by(Pokemon.id).offset(offset).limit(per_page)
    poke_res = await db.execute(poke_stmt)
    all_pokemon = poke_res.scalars().all()

    percent = int((caught_count / total_species) * 100)

    # Progress bar
    bar = get_progress_bar(caught_count, total_species, 10, fill_char="█", empty_char="░")

    text = (
        f"🏆 **POKÉDEX** 🏆\n"
        f"Page {page} of {max_page}\n"
        f"Completion: **{caught_count}/{total_species}** species (**{percent}%**)\n"
        f"`[{bar}]` 🔴\n"
        f"───────────────\n\n"
    )

    for p in all_pokemon:
        r_emoji = get_rarity_emoji(p.rarity)
        text += f"{r_emoji} **#{p.id:03d}** {p.name.title()} `({p.rarity})`\n"

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

