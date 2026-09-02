import re

file_path = r"c:\Users\Rahul Pachute\Downloads\coding\PokeEmpire\handlers\profile.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# Let's define the new check blocks
check_block_replacement = """@router.message(Command("check"))
@router.message(Command("c"))
async def cmd_check_pokemon(message: Message, db: AsyncSession):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("⚠️ Format: `/check <pokemon_name_or_id>`\\n(e.g., `/check bulbasaur` or `/check 1`)")
        return

    query = " ".join(parts[1:]).strip().lower()
    
    pokemon_id = None
    form_index = 0
    pokemon_name_query = None
    
    if "." in query:
        pq, fq = query.split(".", 1)
        pq = pq.strip()
        fq = fq.strip()
        if pq.isdigit():
            pokemon_id = int(pq)
        else:
            pokemon_name_query = pq
        if fq.isdigit():
            form_index = int(fq)
    else:
        if query.isdigit():
            pokemon_id = int(query)
        else:
            pokemon_name_query = query
            
    if pokemon_id is not None:
        stmt = select(Pokemon).where(Pokemon.id == pokemon_id)
    else:
        stmt = select(Pokemon).where(Pokemon.name.ilike(pokemon_name_query))
        
    res = await db.execute(stmt)
    pokemon = res.scalar_one_or_none()
    
    if not pokemon:
        searched_term = pokemon_name_query if pokemon_name_query else str(pokemon_id)
        await message.answer(f"Pokemon '{escape_md(searched_term)}' not found in database.", parse_mode="HTML")
        return
        
    caption, reply_markup, media_type, media_value = await build_check_pokemon_payload(pokemon.id, form_index, db)
    
    from aiogram.types import FSInputFile
    if isinstance(media_value, str) and os.path.exists(media_value):
        media_value = FSInputFile(media_value)
        
    try:
        if media_type == "video":
            await message.answer_video(video=media_value, caption=caption, reply_markup=reply_markup, parse_mode="HTML")
        elif media_type == "animation":
            await message.answer_animation(animation=media_value, caption=caption, reply_markup=reply_markup, parse_mode="HTML")
        else:
            await message.answer_photo(photo=media_value, caption=caption, reply_markup=reply_markup, parse_mode="HTML")
    except Exception as e:
        print(f"Error sending check media: {e}")
        await message.answer(caption, reply_markup=reply_markup, parse_mode="HTML")


async def build_check_pokemon_payload(pokemon_id: int, form_index: int, db: AsyncSession):
    # Fetch pokemon
    stmt = select(Pokemon).where(Pokemon.id == pokemon_id)
    res = await db.execute(stmt)
    pokemon = res.scalar_one_or_none()
    if not pokemon:
        return None, None, None, None
        
    # Resolve media
    media_type = "photo"
    media_value = pokemon.image_url
    if form_index > 0:
        form_media = await get_single_form_media_value(db, pokemon.id, form_index)
        if form_media:
            media_type, media_value = parse_stored_media_value(form_media)
    else:
        if pokemon.video_url:
            media_type = "video"
            media_value = pokemon.video_url
            
    # Resolve form label
    if form_index > 0:
        form_media_db = await get_single_form_media_value(db, pokemon.id, form_index)
        form_label = get_form_label(form_index, form_media_db)
        r_emoji = "📺" if form_index == 1 else "🔮"
        rarity_str = f"{r_emoji} {form_label}"
        name_str = f"{pokemon.name.title()} ({form_label})"
        id_str = f"{pokemon.id}.{form_index}"
    else:
        r_emoji = get_rarity_emoji(pokemon.rarity)
        rarity_str = f"{r_emoji} {pokemon.rarity}"
        name_str = pokemon.name.title()
        id_str = f"{pokemon.id}"
        
    caption = (
        f"<b>🌟 Pokemon Info</b>\\n"
        f"🆔 <b>ID</b>: <code>{id_str}</code>\\n"
        f"⛔ <b>Name</b>: {escape_md(name_str)}\\n"
        f"🎦 <b>Generation</b>: Gen {pokemon.generation}\\n"
        f"🎬 <b>Rarity</b>: {rarity_str}"
    )
    
    # Keyboard has a single button: Owners
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👥 Owners", callback_data=f"show_check_owners_{pokemon.id}_{form_index}")
    )
    return caption, builder.as_markup(), media_type, media_value


@router.callback_query(F.data.startswith("show_check_owners_"))
async def cb_show_check_owners(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    pokemon_id = int(parts[3])
    form_index = int(parts[4])
    
    # Query owners
    owners_stmt = (
        select(User.id, User.nickname, func.count(UserPokemon.id))
        .join(UserPokemon, UserPokemon.user_id == User.id)
        .where(UserPokemon.pokemon_id == pokemon_id)
        .where(UserPokemon.form_index == form_index)
        .group_by(User.id)
        .order_by(func.count(UserPokemon.id).desc())
    )
    owners_res = await db.execute(owners_stmt)
    owners = owners_res.all()
    
    caption = f"🎦 <b>Who has this pokemon:</b>\\n"
    if owners:
        owner_rows = []
        for idx, (uid, nick, count) in enumerate(owners, start=1):
            display_name = escape_md(nick or "Trainer")
            owner_rows.append(f"{idx}. <a href=\\"tg://user?id={uid}\\">{display_name}</a> ×{count}")
        caption += "\\n".join(owner_rows)
    else:
        caption += "No trainer owns this species yet."
        
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔙 Back", callback_data=f"check_back_{pokemon_id}_{form_index}")
    )
    
    try:
        await callback.message.edit_caption(caption=caption, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        try:
            await callback.message.edit_text(caption, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception:
            pass
            
    await callback.answer()


@router.callback_query(F.data.startswith("check_back_"))
async def cb_check_back(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    pokemon_id = int(parts[2])
    form_index = int(parts[3])
    
    caption, reply_markup, _, _ = await build_check_pokemon_payload(pokemon_id, form_index, db)
    
    try:
        await callback.message.edit_caption(caption=caption, reply_markup=reply_markup, parse_mode="HTML")
    except Exception:
        try:
            await callback.message.edit_text(caption, reply_markup=reply_markup, parse_mode="HTML")
        except Exception:
            pass
            
    await callback.answer()
"""

# First, let's find get_leaderboard_text start
leaderboard_idx = content.find("async def get_leaderboard_text")
# Let's find cmd_check_pokemon start (represented by F.Command("check") or @router.message(Command("check")))
check_start_idx = content.find('@router.message(Command("check"))')

# Replace the check block
if check_start_idx != -1 and leaderboard_idx != -1:
    print("Found boundaries for check command block!")
    content = content[:check_start_idx] + check_block_replacement + "\n\n" + content[leaderboard_idx:]
else:
    print("Error: Could not find check command boundaries.")

# Now, let's find F.data.startswith("profile_view_") to locate the end of the search/owners callbacks
profile_view_idx = content.find('@router.callback_query(F.data.startswith("profile_view_"))')
# And let's find the start of the search block: build_search_result_payload
search_start_idx = content.find('async def build_search_result_payload')

search_block_replacement = """@router.message(Command("search"))
@router.message(Command("s"))
@router.message(Command("cid"))
async def cmd_search(message: Message, db: AsyncSession):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Format: `/search <pokemon_name_or_id>`\\nExample: `/search bulbasaur` or `/search 6`", parse_mode="Markdown")
        return

    query = " ".join(parts[1:]).strip().lower()

    pokemon_id = None
    pokemon_name_query = None

    if "." in query:
        pq, fq = query.split(".", 1)
        pq = pq.strip()
        if pq.isdigit():
            pokemon_id = int(pq)
        else:
            pokemon_name_query = pq
    else:
        if query.isdigit():
            pokemon_id = int(query)
        else:
            pokemon_name_query = query

    if pokemon_id is not None:
        poke_stmt = select(Pokemon).where(Pokemon.id == pokemon_id)
    else:
        poke_stmt = select(Pokemon).where(Pokemon.name.ilike(f"%{pokemon_name_query}%"))

    poke_res = await db.execute(poke_stmt)
    pokemons = poke_res.scalars().all()

    if not pokemons:
        searched_term = pokemon_name_query if pokemon_name_query else str(pokemon_id)
        await message.answer(f"Pokemon '{escape_md(searched_term)}' not found in database.", parse_mode="HTML")
        return

    # Sort results so the closest match (shortest name or exact name) is selected as the primary_pokemon
    if pokemon_name_query:
        pokemons.sort(key=lambda p: (abs(len(p.name) - len(pokemon_name_query)), p.name.lower() != pokemon_name_query.lower()))
    pokemon = pokemons[0]

    await send_search_result_message(message, pokemon, 1, db)


async def build_variants_search_payload(pokemon_id: int, page: int, db: AsyncSession):
    # Fetch primary pokemon
    stmt = select(Pokemon).where(Pokemon.id == pokemon_id)
    res = await db.execute(stmt)
    pokemon = res.scalar_one_or_none()
    if not pokemon:
        return "Character not found.", None
        
    # Fetch all forms from PokemonFormMedia
    from database.models import PokemonFormMedia
    stmt = select(PokemonFormMedia.form_index, PokemonFormMedia.media_value).where(
        PokemonFormMedia.pokemon_id == pokemon_id
    ).order_by(PokemonFormMedia.form_index)
    res = await db.execute(stmt)
    form_entries = res.all()
    
    # Build list of variants: (form_index, label, rarity_emoji, entry_id)
    base_emoji = get_rarity_emoji(pokemon.rarity)
    variants = [(0, pokemon.rarity, base_emoji, f"{pokemon.id}")]
    
    for form_index, media_value in form_entries:
        form_label = get_form_label(form_index, media_value)
        if form_index == 1:
            form_emoji = "📺" # AMV
        elif form_index == 2:
            form_emoji = "⚡" # Dmax
        elif form_index == 3:
            form_emoji = "💥" # Gmax
        elif form_index == 4:
            form_emoji = "🌀" # Z-Move
        elif form_index == 5:
            form_emoji = "🔮" # Terastal
        else:
            form_emoji = "🔮"
        variants.append((form_index, form_label, form_emoji, f"{pokemon.id}.{form_index}"))
        
    total_variants = len(variants)
    page_size = 5
    total_pages = max(1, (total_variants + page_size - 1) // page_size)
    
    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages
        
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_variants = variants[start_idx:end_idx]
    
    gen_str = str(pokemon.generation)
    if gen_str.isdigit():
        series_str = f"Gen {gen_str}"
    else:
        series_str = gen_str
        
    caption = (
        f"🦧 <b>{escape_md(pokemon.name.title())}</b>\\n"
        f"┣━ 🎦 {escape_md(series_str)}\\n"
        f"┣━ 📊 Total variants: <b>{total_variants}</b> — Page <b>{page}/{total_pages}</b>\\n\\n"
    )
    
    for form_index, label, emoji, entry_id in page_variants:
        caption += f"┣━ {emoji} {label} | ID: <code>{entry_id}</code>\\n"
        
    # Build keyboard
    builder = InlineKeyboardBuilder()
    if total_pages > 1:
        if page == 1:
            builder.row(
                InlineKeyboardButton(text=f"1/{total_pages}", callback_data="search_noop"),
                InlineKeyboardButton(text="Next ➡️", callback_data=f"search_page_{pokemon.id}_{page + 1}")
            )
        elif page == total_pages:
            builder.row(
                InlineKeyboardButton(text="⬅️ Prev", callback_data=f"search_page_{pokemon.id}_{page - 1}"),
                InlineKeyboardButton(text=f"{total_pages}/{total_pages}", callback_data="search_noop")
            )
        else:
            builder.row(
                InlineKeyboardButton(text="⬅️ Prev", callback_data=f"search_page_{pokemon.id}_{page - 1}"),
                InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="search_noop"),
                InlineKeyboardButton(text="Next ➡️", callback_data=f"search_page_{pokemon.id}_{page + 1}")
            )
            
    return caption, builder.as_markup()


async def send_search_result_message(message: Message, pokemon: Pokemon, page: int, db: AsyncSession):
    caption, reply_markup = await build_variants_search_payload(pokemon.id, page, db)
    
    media_value = pokemon.image_url
    media_type = "photo"
    
    if pokemon.video_url:
        media_type = "video"
        media_value = pokemon.video_url
        
    from aiogram.types import FSInputFile
    if isinstance(media_value, str) and os.path.exists(media_value):
        media_value = FSInputFile(media_value)
        
    try:
        if media_type == "video":
            await message.answer_video(video=media_value, caption=caption, reply_markup=reply_markup, parse_mode="HTML")
        else:
            await message.answer_photo(photo=media_value, caption=caption, reply_markup=reply_markup, parse_mode="HTML")
    except Exception as e:
        print(f"Error sending variants media: {e}")
        await message.answer(caption, reply_markup=reply_markup, parse_mode="HTML")


@router.callback_query(F.data.startswith("search_page_"))
async def cb_search_page(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    pokemon_id = int(parts[2])
    page = int(parts[3])
    
    caption, reply_markup = await build_variants_search_payload(pokemon_id, page, db)
    
    try:
        await callback.message.edit_caption(caption=caption, reply_markup=reply_markup, parse_mode="HTML")
    except Exception:
        try:
            await callback.message.edit_text(caption, reply_markup=reply_markup, parse_mode="HTML")
        except Exception:
            pass
            
    await callback.answer()


@router.callback_query(F.data == "search_noop")
async def cb_search_noop(callback: CallbackQuery):
    await callback.answer()
"""

# Replace the search block
if search_start_idx != -1 and profile_view_idx != -1:
    print("Found boundaries for search block!")
    content = content[:search_start_idx] + search_block_replacement + "\n\n" + content[profile_view_idx:]
else:
    print("Error: Could not find search block boundaries.")

# Write changes back
with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated profile handlers successfully!")
