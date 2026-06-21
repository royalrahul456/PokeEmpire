import os
import html
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

async def get_player_cover_media(user_id: int, db: AsyncSession) -> tuple[str, str]:
    """
    Resolves the cover media for a trainer.
    Returns (media_type, media_value)
    """
    from utils.favorite import get_favorite_id
    from utils.settings import get_custom_cover
    
    fav_val = get_favorite_id(user_id)
    media_type = None
    media_value = None
    
    if fav_val:
        pokemon_id = None
        form_index = 0
        if "." in fav_val:
            pq, fq = fav_val.split(".", 1)
            if pq.isdigit() and fq.isdigit():
                pokemon_id = int(pq)
                form_index = int(fq)
        elif fav_val.isdigit():
            pokemon_id = int(fav_val)
            
        if pokemon_id:
            # Check if they own this species
            stmt = select(UserPokemon).where(
                UserPokemon.pokemon_id == pokemon_id,
                UserPokemon.user_id == user_id
            ).limit(1)
            res = await db.execute(stmt)
            owned = res.scalar() is not None
            
            if owned:
                poke_stmt = select(Pokemon).where(Pokemon.id == pokemon_id)
                poke_res = await db.execute(poke_stmt)
                pokemon = poke_res.scalar_one_or_none()
                
                if pokemon:
                    if form_index == 0:
                        media_type = "photo"
                        media_value = pokemon.image_url
                    else:
                        from database.models import PokemonFormMedia
                        media_stmt = select(PokemonFormMedia.media_value).where(
                            PokemonFormMedia.pokemon_id == pokemon_id,
                            PokemonFormMedia.form_index == form_index
                        ).limit(1)
                        media_res = await db.execute(media_stmt)
                        media_val_db = media_res.scalar()
                        
                        if media_val_db:
                            if ":" in media_val_db:
                                mtype, mval = media_val_db.split(":", 1)
                                if mtype in ["photo", "video", "animation"]:
                                    media_type = mtype
                                    media_value = mval
                            else:
                                media_type = "video"
                                media_value = media_val_db
                                
    if not media_value:
        # Fallback 1: Random Pokémon from their bag
        rand_stmt = select(UserPokemon).options(joinedload(UserPokemon.pokemon)).where(
            UserPokemon.user_id == user_id
        ).order_by(func.random()).limit(1)
        rand_res = await db.execute(rand_stmt)
        up = rand_res.scalar_one_or_none()
        if up and up.pokemon:
            if up.form_index > 0:
                from database.models import PokemonFormMedia
                media_stmt = select(PokemonFormMedia.media_value).where(
                    PokemonFormMedia.pokemon_id == up.pokemon_id,
                    PokemonFormMedia.form_index == up.form_index
                ).limit(1)
                media_res = await db.execute(media_stmt)
                media_val_db = media_res.scalar()
                
                if media_val_db:
                    if ":" in media_val_db:
                        mtype, mval = media_val_db.split(":", 1)
                        if mtype in ["photo", "video", "animation"]:
                            media_type = mtype
                            media_value = mval
                    else:
                        media_type = "video"
                        media_value = media_val_db
            
            if not media_value:
                media_type = "photo"
                media_value = up.pokemon.image_url
                
    if not media_value:
        # Fallback 2: Default pokedex cover configured by owner
        media_type, media_value = get_custom_cover("pokedex")
        
    if not media_value:
        # Fallback 3: Hardcoded default
        media_type = "photo"
        media_value = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/890.png"
        
    return media_type, media_value

async def send_player_cover(chat_id: int, user_id: int, caption: str, reply_markup, bot, db: AsyncSession, message_to_reply=None):
    media_type, media_value = await get_player_cover_media(user_id, db)
    
    from aiogram.types import FSInputFile
    if isinstance(media_value, str) and os.path.exists(media_value):
        media_value = FSInputFile(media_value)
        
    try:
        if message_to_reply:
            if media_type == "video":
                return await message_to_reply.answer_video(video=media_value, caption=caption, reply_markup=reply_markup, parse_mode="HTML")
            elif media_type == "animation":
                return await message_to_reply.answer_animation(animation=media_value, caption=caption, reply_markup=reply_markup, parse_mode="HTML")
            else:
                return await message_to_reply.answer_photo(photo=media_value, caption=caption, reply_markup=reply_markup, parse_mode="HTML")
        else:
            if media_type == "video":
                return await bot.send_video(chat_id, video=media_value, caption=caption, reply_markup=reply_markup, parse_mode="HTML")
            elif media_type == "animation":
                return await bot.send_animation(chat_id, animation=media_value, caption=caption, reply_markup=reply_markup, parse_mode="HTML")
            else:
                return await bot.send_photo(chat_id, photo=media_value, caption=caption, reply_markup=reply_markup, parse_mode="HTML")
    except Exception as e:
        print(f"Error sending player cover media: {e}")
        # Final fallback: text only
        if message_to_reply:
            return await message_to_reply.answer(caption, reply_markup=reply_markup, parse_mode="HTML")
        else:
            return await bot.send_message(chat_id, caption, reply_markup=reply_markup, parse_mode="HTML")

async def edit_player_cover_message(callback: CallbackQuery, user_id: int, caption: str, reply_markup, db: AsyncSession, parse_mode="HTML"):
    media_type, media_value = await get_player_cover_media(user_id, db)
    from aiogram.types import InputMediaPhoto, InputMediaVideo
    try:
        if media_type == "video":
            new_media = InputMediaVideo(media=media_value, caption=caption, parse_mode=parse_mode)
        else:
            new_media = InputMediaPhoto(media=media_value, caption=caption, parse_mode=parse_mode)
            
        await callback.message.edit_media(media=new_media, reply_markup=reply_markup)
    except Exception as e:
        print(f"Error editing player cover media: {e}")
        try:
            await callback.message.edit_caption(caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)
        except Exception:
            pass

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
        f"├─➩ 🆔 ID: <code>{user.id}</code>\n"
        f"├─➩ 💰 Balance: <code>{formatted_coins} coins</code>\n"
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
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📖 View Pokédex", callback_data=f"pd_page_{user_id}_1_All"))
    await send_player_cover(
        chat_id=message.chat.id,
        user_id=user_id,
        caption=profile_card,
        reply_markup=builder.as_markup(),
        bot=message.bot,
        db=db,
        message_to_reply=message
    )

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
            f"🌟 <b>{html.escape(nickname)}'s Pokédex</b> 🌟{filter_str}\n"
            f"───────────────\n\n"
            f"⚠️ <b>Your Pokédex is empty!</b>\n"
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

    # Query owned sub-form indexes for the current page species to avoid N+1 queries
    page_pokemon_ids = [p.id for p, _, _ in pairs]
    owned_forms_stmt = select(UserPokemon.pokemon_id, UserPokemon.form_index).where(
        UserPokemon.user_id == user_id,
        UserPokemon.pokemon_id.in_(page_pokemon_ids),
        UserPokemon.form_index > 0
    )
    res_forms = await db.execute(owned_forms_stmt)
    owned_species_forms = {}
    for pid, fidx in res_forms.all():
        if pid not in owned_species_forms:
            owned_species_forms[pid] = set()
        owned_species_forms[pid].add(fidx)

    # 5. Build header caption text (no extra stars, no progress bar, matching mockup)
    filter_label = f" ({rarity_filter})" if rarity_filter and rarity_filter != "All" else ""
    text = f"🌟 <b>{html.escape(nickname)}'s Pokédex</b> 🌟{filter_label} — Page {page}/{max_page}\n"

    current_gen = None
    rarity_badges = {
        "Common": "⚪️",
        "Rare": "🟣",
        "Epic": "🔮",
        "Legendary": "🌟",
        "Mythical": "🌌"
    }

    form_badges_map = {
        1: "🎬",
        2: "⚡",
        3: "💥",
        4: "🌀",
        5: "🔮"
    }

    first_group = True
    for p, total, has_shiny in pairs:
        if p.generation != current_gen:
            current_gen = p.generation
            if not first_group:
                text += "\n"
            first_group = False
            text += f"Generation {current_gen} {gen_stats.get(current_gen, 0)}/{gen_totals.get(current_gen, 0)}\n"
            
        badge = rarity_badges.get(p.rarity, "⚪️")
        shiny_tag = " [✨]" if has_shiny else ""
        
        forms_owned = owned_species_forms.get(p.id, set())
        form_tag = "".join([form_badges_map.get(f, "") for f in sorted(forms_owned)])
        if form_tag:
            form_tag = f" [{form_tag}]"
            
        text += f"◆ [ {badge} ] {p.id} {p.name.title()}{shiny_tag}{form_tag} ×{total}\n"

    return text, page, max_page

def get_pokedex_keyboard(user_id: int, page: int, max_page: int, rarity_filter: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    
    # Row 1: Tab Switches (Clean, no extra stars, matching mockup)
    builder.row(
        InlineKeyboardButton(text="Collection", callback_data=f"pd_tab_{user_id}_col"),
        InlineKeyboardButton(text="💟 AMV", callback_data=f"pd_tab_{user_id}_cov")
    )
    
    # Row 2: Dynamic Pagination Buttons (no wrapping, only show arrows if next/prev page exists)
    if max_page > 1:
        nav_row = []
        if page > 1:
            nav_row.append(InlineKeyboardButton(text="⬅️", callback_data=f"pd_page_{user_id}_{page-1}_{rarity_filter}"))
        
        nav_row.append(InlineKeyboardButton(text=f"{page}/{max_page}", callback_data="pd_page_info_noop"))
        
        if page < max_page:
            nav_row.append(InlineKeyboardButton(text="➡️", callback_data=f"pd_page_{user_id}_{page+1}_{rarity_filter}"))
            
        builder.row(*nav_row)
        
    # Row 3: Filter by Rarity Button
    builder.row(
        InlineKeyboardButton(text="🔍 Filter by Rarity", callback_data=f"pd_rarity_{user_id}_{page}_{rarity_filter}")
    )
    
    # Row 4: View Profile Button
    builder.row(
        InlineKeyboardButton(text="👤 View Profile", callback_data=f"profile_view_{user_id}")
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
        await message.answer(text, parse_mode="HTML")
        return

    kb = get_pokedex_keyboard(user_id, final_page, max_page, "All")
    await send_player_cover(
        chat_id=message.chat.id,
        user_id=user_id,
        caption=text,
        reply_markup=kb,
        bot=message.bot,
        db=db,
        message_to_reply=message
    )

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
            f"🖼️ <b>Pokédex Cover Favorite</b>\n"
            f"───────────────\n\n"
            f"Set your favorite Pokémon as the Pokédex cover illustration!\n\n"
            f"👉 <b>How to set</b>: Type <code>/fav &lt;pokedex_id&gt;</code> in chat.\n"
            f"<i>(e.g., <code>/fav 251</code> to set Celebi as cover)</i>"
        )
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Back to Collection", callback_data=f"pd_page_{user_id}_1_All"))
        
        try:
            await callback.message.edit_caption(caption=text, reply_markup=builder.as_markup(), parse_mode="HTML")
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
        
        await edit_player_cover_message(callback, user_id, text, kb, db, parse_mode="HTML")
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
    
    await edit_player_cover_message(callback, user_id, text, kb, db, parse_mode="HTML")
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
        f"🔍 <b>Filter Pokédex by Rarity</b>\n"
        f"───────────────\n\n"
        f"Choose a rarity tier below to filter your species list:"
    )
    kb = get_rarity_filter_keyboard(user_id, page, rarity_filter)
    
    try:
        await callback.message.edit_caption(caption=text, reply_markup=kb, parse_mode="HTML")
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
    
    await edit_player_cover_message(callback, user_id, text, kb, db, parse_mode="HTML")
    await callback.answer(f"Filtered by: {rarity_filter}")

@router.message(Command("check"))
async def cmd_check_pokemon(message: Message, db: AsyncSession):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("⚠️ Format: `/check <pokemon_name_or_id>`\n(e.g., `/check bulbasaur` or `/check 1`)")
        return

    query = " ".join(parts[1:]).strip().lower()
    await check_pokemon_variants(message, db, query, page=1)


@router.callback_query(F.data.startswith("check_page_"))
async def cb_check_page(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    try:
        pokemon_id = int(parts[2])
        page = int(parts[3])
    except (IndexError, ValueError):
        await callback.answer("⚠️ Invalid page.")
        return

    poke_stmt = select(Pokemon).where(Pokemon.id == pokemon_id)
    poke_res = await db.execute(poke_stmt)
    pokemon = poke_res.scalar_one_or_none()
    if not pokemon:
        await callback.answer("⚠️ Pokémon not found.")
        return

    await check_pokemon_variants(callback.message, db, str(pokemon_id), page=page, edit=True)
    await callback.answer()


async def check_pokemon_variants(message: Message, db: AsyncSession, query: str, page: int = 1, edit: bool = False):
    pokemon_id = None
    if "." in query:
        pq, fq = query.split(".", 1)
        if pq.isdigit():
            pokemon_id = int(pq)
    elif query.isdigit():
        pokemon_id = int(query)
        
    if pokemon_id is not None:
        poke_stmt = select(Pokemon).where(Pokemon.id == pokemon_id)
    else:
        poke_stmt = select(Pokemon).where(Pokemon.name.ilike(query))

    poke_res = await db.execute(poke_stmt)
    pokemon = poke_res.scalar_one_or_none()

    if not pokemon:
        text = f"❌ Pokémon '{escape_md(query)}' not found in database."
        if edit:
            await message.edit_text(text)
        else:
            await message.answer(text)
        return

    from database.models import PokemonFormMedia
    media_stmt = select(PokemonFormMedia.form_index).where(PokemonFormMedia.pokemon_id == pokemon.id).order_by(PokemonFormMedia.form_index)
    media_res = await db.execute(media_stmt)
    db_forms = media_res.scalars().all()

    all_forms = [0] + list(db_forms)
    all_forms = sorted(list(set(all_forms)))

    total_variants = len(all_forms)
    page_size = 8
    total_pages = max(1, (total_variants + page_size - 1) // page_size)

    if page < 1:
        page = 1
    if page > total_pages:
        page = total_pages

    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_forms = all_forms[start_idx:end_idx]

    cover_link = f"[​]({pokemon.image_url})"
    text_lines = [
        f"{cover_link}📛 **{pokemon.name.title()}**",
        f"┣━ 📺 Gen {pokemon.generation}",
        f"┣━ 📊 Total variants: {total_variants} — Page {page}/{total_pages}",
        ""
    ]

    form_names = {
        0: pokemon.rarity,
        1: "AMV",
        2: "Dmax",
        3: "Gmax",
        4: "Z-Move",
        5: "Terastal"
    }

    form_emojis = {
        0: get_rarity_emoji(pokemon.rarity),
        1: "🎬",
        2: "⚡",
        3: "💥",
        4: "🌀",
        5: "🔮"
    }

    for f in page_forms:
        f_name = form_names.get(f, f"Form {f}")
        f_emoji = form_emojis.get(f, "🟢")
        text_lines.append(f"┣━ {f_emoji} {f_name} | ID: `{pokemon.id}.{f}`")

    text = "\n".join(text_lines)

    kb_rows = []
    if total_pages > 1:
        prev_page = page - 1 if page > 1 else total_pages
        next_page = page + 1 if page < total_pages else 1
        kb_rows.append([
            InlineKeyboardButton(text="⬅️ Prev", callback_data=f"check_page_{pokemon.id}_{prev_page}"),
            InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="check_page_info_noop"),
            InlineKeyboardButton(text="Next ➡️", callback_data=f"check_page_{pokemon.id}_{next_page}")
        ])

    kb_rows.append([
        InlineKeyboardButton(text="👥 View Owners", callback_data=f"show_owners_{pokemon.id}")
    ])

    reply_markup = InlineKeyboardMarkup(inline_keyboard=kb_rows)

    if edit:
        await message.edit_text(text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await message.answer(text, reply_markup=reply_markup, parse_mode="Markdown")

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
    if len(parts) < 2:
        await message.answer("⚠️ Format: `/fav <pokedex_id>[.form_index]`\n(e.g., `/fav 251` or `/fav 6.1` to set Charizard AMV as your favorite cover)")
        return
        
    fav_str = parts[1].strip()
    pokemon_id = None
    form_index = 0
    if "." in fav_str:
        pq, fq = fav_str.split(".", 1)
        if pq.isdigit() and fq.isdigit():
            pokemon_id = int(pq)
            form_index = int(fq)
    elif fav_str.isdigit():
        pokemon_id = int(fav_str)
        
    if pokemon_id is None:
        await message.answer("⚠️ Format: `/fav <pokedex_id>[.form_index]`\n(e.g., `/fav 251` or `/fav 6.1` to set Charizard AMV as your favorite cover)")
        return
    
    # Verify user owns at least one Pokémon of this species/form
    if form_index > 0:
        stmt = select(UserPokemon).options(joinedload(UserPokemon.pokemon)).where(
            UserPokemon.pokemon_id == pokemon_id,
            UserPokemon.user_id == user_id,
            UserPokemon.form_index == form_index
        ).limit(1)
    else:
        stmt = select(UserPokemon).options(joinedload(UserPokemon.pokemon)).where(
            UserPokemon.pokemon_id == pokemon_id,
            UserPokemon.user_id == user_id
        ).limit(1)
        
    res = await db.execute(stmt)
    up = res.scalar()
    
    if not up:
        form_suffix = f" (Form {form_index})" if form_index > 0 else ""
        await message.answer(f"❌ You don't own a Pokémon with that Pokédex ID{form_suffix} in your collection!")
        return
        
    p = up.pokemon
    from utils.favorite import set_favorite_id
    set_favorite_id(user_id, fav_str)
    
    # Check if they own any shiny version of this species
    shiny_stmt = select(UserPokemon.is_shiny).where(
        UserPokemon.pokemon_id == pokemon_id,
        UserPokemon.user_id == user_id,
        UserPokemon.is_shiny == True
    ).limit(1)
    shiny_res = await db.execute(shiny_stmt)
    has_shiny = shiny_res.scalar() is not None
    
    shiny_tag = "✨ Shiny " if has_shiny else ""
    form_suffix = f" (Form {form_index})" if form_index > 0 else ""
    await message.answer(f"🌟 <b>{shiny_tag}{p.name.title()}</b>{form_suffix} (Pokédex ID: {fav_str}) has been set as your Pokédex cover favorite!", parse_mode="HTML")

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
        await message.answer("⚠️ Format: `/search <pokemon_name_or_id>[.form_index]`\n(e.g., `/search bulbasaur` or `/search 6.1`)")
        return
        
    query = " ".join(parts[1:]).strip().lower()
    
    pokemon_id = None
    form_filter = None
    if "." in query:
        pq, fq = query.split(".", 1)
        if pq.isdigit() and fq.isdigit():
            pokemon_id = int(pq)
            form_filter = int(fq)
    elif query.isdigit():
        pokemon_id = int(query)
        
    # Query species
    if pokemon_id is not None:
        poke_stmt = select(Pokemon).where(Pokemon.id == pokemon_id)
    else:
        poke_stmt = select(Pokemon).where(Pokemon.name.ilike(query))
        
    poke_res = await db.execute(poke_stmt)
    pokemon = poke_res.scalar_one_or_none()
    
    if not pokemon:
        await message.answer(f"❌ Pokémon '{escape_md(query)}' not found in database.")
        return
        
    # Query player's own catches of this species (applying form filter if provided)
    if form_filter is not None:
        catches_stmt = select(UserPokemon).where(
            UserPokemon.user_id == user_id,
            UserPokemon.pokemon_id == pokemon.id,
            UserPokemon.form_index == form_filter
        ).order_by(UserPokemon.caught_at.desc())
    else:
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
                
        form_names_search = {
            0: "Standard",
            1: "AMV",
            2: "Dmax",
            3: "Gmax",
            4: "Z-Move",
            5: "Terastal"
        }
        best_form_name = form_names_search.get(best_up.form_index, f"Form {best_up.form_index}")
        shiny_label = "✨ Yes" if best_up.is_shiny else "❌ No"
        
        form_suffix = f" (Form {form_filter})" if form_filter is not None else ""
        text = (
            f"{cover_link}"
            f"🔍 **SEARCH RESULTS** 🔍\n"
            f"───────────────\n"
            f"🎉 Species: {r_emoji} **{pokemon.name.title()}** {r_emoji}\n"
            f"🆔 Pokédex ID: `#{pokemon.id:03d}`\n"
            f"⭐ Rarity: `{pokemon.rarity}`\n"
            f"🧬 Total Caught{form_suffix}: `{len(user_catches)} caught`\n\n"
            f"🏆 **Your Best Pokémon**:\n"
            f"• Form: `{best_form_name} | ID: {pokemon.id}.{best_up.form_index}`\n"
            f"• Shiny: `{shiny_label}`\n"
            f"───────────────"
        )
    else:
        form_suffix = f" of Form {form_filter}" if form_filter is not None else ""
        text = (
            f"{cover_link}"
            f"🔍 **SEARCH RESULTS** 🔍\n"
            f"───────────────\n"
            f"🎉 Species: {r_emoji} **{pokemon.name.title()}** {r_emoji}\n"
            f"🆔 Pokédex ID: `#{pokemon.id:03d}`\n"
            f"⭐ Rarity: `{pokemon.rarity}`\n"
            f"🧬 Total Caught: `0 caught` (You haven't caught this species{form_suffix} yet!)\n"
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


@router.callback_query(F.data.startswith("profile_view_"))
async def cb_profile_view(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    user_id = int(parts[2])

    if callback.from_user.id != user_id:
        await callback.answer("❌ This is not your profile!", show_alert=True)
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

    # Fetch User
    u_stmt = select(User).where(User.id == user_id)
    u_res = await db.execute(u_stmt)
    user = u_res.scalar_one_or_none()
    
    formatted_coins = f"{user.coins:,}" if user else "0"
    user_nickname = user.nickname if (user and user.nickname) else (callback.from_user.first_name or "Trainer")

    # Calculate global rank position
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
        f"├─➩ 🆔 ID: `{user_id}`\n"
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
    
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="📖 View Pokédex", callback_data=f"pd_page_{user_id}_1_All"))
    
    await edit_player_cover_message(callback, user_id, profile_card, builder.as_markup(), db, parse_mode="HTML")
    await callback.answer()


@router.message(Command("dex"))
async def cmd_dex(message: Message, db: AsyncSession):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("⚠️ Format: `/dex <pokemon_name_or_id>`")
        return
        
    query = " ".join(parts[1:]).strip().lower()
    user_id = message.from_user.id
    
    # 1. Resolve Pokemon
    if query.isdigit():
        poke_stmt = select(Pokemon).where(Pokemon.id == int(query))
    else:
        poke_stmt = select(Pokemon).where(Pokemon.name.ilike(query))
        
    poke_res = await db.execute(poke_stmt)
    pokemon = poke_res.scalar_one_or_none()
    
    if not pokemon:
        await message.answer(f"❌ Pokémon '{escape_md(query)}' not found.")
        return
        
    # 2. Get owned form indexes for this user and species
    owned_stmt = select(UserPokemon.form_index).where(
        UserPokemon.user_id == user_id,
        UserPokemon.pokemon_id == pokemon.id
    )
    owned_res = await db.execute(owned_stmt)
    owned_forms = set(owned_res.scalars().all())
    
    # 3. Check if they own any shiny version
    shiny_stmt = select(UserPokemon.id).where(
        UserPokemon.user_id == user_id,
        UserPokemon.pokemon_id == pokemon.id,
        UserPokemon.is_shiny == True
    ).limit(1)
    shiny_res = await db.execute(shiny_stmt)
    has_shiny = shiny_res.scalar() is not None
    
    # 4. Get configured form media
    from database.models import PokemonFormMedia
    media_stmt = select(PokemonFormMedia.form_index, PokemonFormMedia.media_value).where(
        PokemonFormMedia.pokemon_id == pokemon.id
    )
    media_res = await db.execute(media_stmt)
    configured_media = {row[0]: row[1] for row in media_res.all()}
    
    # 5. Build Subtype Status list
    form_names = {
        0: "Standard",
        1: "AMV/Art",
        2: "Dmax",
        3: "Gmax",
        4: "Z-Move",
        5: "Terastal"
    }
    form_badges = {
        0: "📸",
        1: "🎬",
        2: "⚡",
        3: "💥",
        4: "🌀",
        5: "🔮"
    }
    
    subtypes_text = ""
    # We will list Form 0, and any other forms that are configured.
    available_forms = [0] + sorted([f for f in configured_media.keys() if f > 0])
    
    builder = InlineKeyboardBuilder()
    
    for f in available_forms:
        f_name = form_names.get(f, f"Form {f}")
        f_badge = form_badges.get(f, "🌀")
        is_owned = f in owned_forms
        owned_status = "✅ Owned" if is_owned else "❌ Locked"
        
        # Rarity for subtypes
        if f == 0:
            rarity_lbl = pokemon.rarity
        elif f == 1:
            val = configured_media.get(1, "")
            rarity_lbl = "Art" if val.startswith("photo:") else "AMV"
        else:
            rarity_lbl = f_name
            
        subtypes_text += f"• {f_badge} <b>{f_name}</b> (<code>{rarity_lbl}</code>): {owned_status}\n"
        
        if is_owned:
            builder.button(text=f"▶️ View {f_name}", callback_data=f"dex_play_{user_id}_{pokemon.id}_{f}")
            
    builder.adjust(2)
    
    r_emoji = get_rarity_emoji(pokemon.rarity)
    shiny_tag = " ✨" if has_shiny else ""
    
    caption = (
        f"📖 <b>DEX ENTRY: #{pokemon.id:03d} {pokemon.name.title()}</b>{shiny_tag}\n"
        f"───────────────\n"
        f"Rarity: {r_emoji} <b>{pokemon.rarity}</b>\n"
        f"Generation: <b>Gen {pokemon.generation}</b>\n\n"
        f"🧬 <b>Subtype Collection</b>:\n"
        f"{subtypes_text}"
        f"───────────────"
    )
    
    try:
        await message.answer_photo(
            photo=pokemon.image_url,
            caption=caption,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    except Exception as e:
        print(f"Error sending dex entry: {e}")
        await message.answer(caption, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data.startswith("dex_play_"))
async def cb_dex_play(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    user_id = int(parts[2])
    pokemon_id = int(parts[3])
    form_index = int(parts[4])
    
    if callback.from_user.id != user_id:
        await callback.answer("❌ This is not your menu!", show_alert=True)
        return
        
    stmt = select(Pokemon).where(Pokemon.id == pokemon_id)
    res = await db.execute(stmt)
    pokemon = res.scalar_one_or_none()
    if not pokemon:
        await callback.answer("❌ Pokémon not found.", show_alert=True)
        return
        
    from database.models import PokemonFormMedia
    media_value = None
    media_type = "photo"
    
    if form_index == 0:
        media_value = pokemon.image_url
        media_type = "photo"
    else:
        media_stmt = select(PokemonFormMedia).where(
            PokemonFormMedia.pokemon_id == pokemon_id,
            PokemonFormMedia.form_index == form_index
        )
        media_res = await db.execute(media_stmt)
        form_media = media_res.scalar_one_or_none()
        if form_media:
            media_value = form_media.media_value
            if media_value.startswith("video:"):
                media_type = "video"
                media_value = media_value.replace("video:", "")
            elif media_value.startswith("photo:"):
                media_type = "photo"
                media_value = media_value.replace("photo:", "")
            elif media_value.startswith("animation:"):
                media_type = "animation"
                media_value = media_value.replace("animation:", "")
            else:
                if media_value.startswith("http"):
                    media_type = "photo"
                else:
                    media_type = "video"
                    
    if not media_value:
        await callback.answer("❌ Media not configured for this form.", show_alert=True)
        return
        
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Back to Dex Info", callback_data=f"dex_back_{user_id}_{pokemon_id}")
    
    from aiogram.types import InputMediaPhoto, InputMediaVideo
    try:
        if media_type in ["video", "animation"]:
            new_media = InputMediaVideo(media=media_value, caption=f"🎥 Playing <b>{pokemon.name.title()} Form {form_index}</b>", parse_mode="HTML")
        else:
            new_media = InputMediaPhoto(media=media_value, caption=f"📸 Showing <b>{pokemon.name.title()} Form {form_index}</b>", parse_mode="HTML")
            
        await callback.message.edit_media(media=new_media, reply_markup=builder.as_markup())
    except Exception as e:
        print(f"Error playing form media: {e}")
        await callback.answer("❌ Could not display media on this message.", show_alert=True)
        
    await callback.answer()

@router.callback_query(F.data.startswith("dex_back_"))
async def cb_dex_back(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    user_id = int(parts[2])
    pokemon_id = int(parts[3])
    
    if callback.from_user.id != user_id:
        await callback.answer("❌ This is not your menu!", show_alert=True)
        return
        
    stmt = select(Pokemon).where(Pokemon.id == pokemon_id)
    res = await db.execute(stmt)
    pokemon = res.scalar_one_or_none()
    if not pokemon:
        await callback.answer("❌ Pokémon not found.", show_alert=True)
        return
        
    owned_stmt = select(UserPokemon.form_index).where(
        UserPokemon.user_id == user_id,
        UserPokemon.pokemon_id == pokemon.id
    )
    owned_res = await db.execute(owned_stmt)
    owned_forms = set(owned_res.scalars().all())
    
    shiny_stmt = select(UserPokemon.id).where(
        UserPokemon.user_id == user_id,
        UserPokemon.pokemon_id == pokemon.id,
        UserPokemon.is_shiny == True
    ).limit(1)
    shiny_res = await db.execute(shiny_stmt)
    has_shiny = shiny_res.scalar() is not None
    
    from database.models import PokemonFormMedia
    media_stmt = select(PokemonFormMedia.form_index, PokemonFormMedia.media_value).where(
        PokemonFormMedia.pokemon_id == pokemon.id
    )
    media_res = await db.execute(media_stmt)
    configured_media = {row[0]: row[1] for row in media_res.all()}
    
    form_names = {
        0: "Standard",
        1: "AMV/Art",
        2: "Dmax",
        3: "Gmax",
        4: "Z-Move",
        5: "Terastal"
    }
    form_badges = {
        0: "📸",
        1: "🎬",
        2: "⚡",
        3: "💥",
        4: "🌀",
        5: "🔮"
    }
    
    subtypes_text = ""
    available_forms = [0] + sorted([f for f in configured_media.keys() if f > 0])
    builder = InlineKeyboardBuilder()
    
    for f in available_forms:
        f_name = form_names.get(f, f"Form {f}")
        f_badge = form_badges.get(f, "🌀")
        is_owned = f in owned_forms
        owned_status = "✅ Owned" if is_owned else "❌ Locked"
        
        if f == 0:
            rarity_lbl = pokemon.rarity
        elif f == 1:
            val = configured_media.get(1, "")
            rarity_lbl = "Art" if val.startswith("photo:") else "AMV"
        else:
            rarity_lbl = f_name
            
        subtypes_text += f"• {f_badge} <b>{f_name}</b> (<code>{rarity_lbl}</code>): {owned_status}\n"
        
        if is_owned:
            builder.button(text=f"▶️ View {f_name}", callback_data=f"dex_play_{user_id}_{pokemon.id}_{f}")
            
    builder.adjust(2)
    
    r_emoji = get_rarity_emoji(pokemon.rarity)
    shiny_tag = " ✨" if has_shiny else ""
    
    caption = (
        f"📖 <b>DEX ENTRY: #{pokemon.id:03d} {pokemon.name.title()}</b>{shiny_tag}\n"
        f"───────────────\n"
        f"Rarity: {r_emoji} <b>{pokemon.rarity}</b>\n"
        f"Generation: <b>Gen {pokemon.generation}</b>\n\n"
        f"🧬 <b>Subtype Collection</b>:\n"
        f"{subtypes_text}"
        f"───────────────"
    )
    
    from aiogram.types import InputMediaPhoto
    try:
        await callback.message.edit_media(
            media=InputMediaPhoto(media=pokemon.image_url, caption=caption, parse_mode="HTML"),
            reply_markup=builder.as_markup()
        )
    except Exception as e:
        print(f"Error resetting media: {e}")
        try:
            await callback.message.edit_caption(caption=caption, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception:
            pass
            
    await callback.answer()

@router.message(Command("gift"))
async def cmd_gift(message: Message, db: AsyncSession):
    parts = message.text.split()
    target_user = None
    gift_str = None
    
    # 1. Parse target and pokemon query
    if message.reply_to_message:
        if len(parts) < 2:
            await message.answer("⚠️ Format (replying): `/gift <pokedex_id>[.form_index]`")
            return
        rep_user = message.reply_to_message.from_user
        if rep_user.is_bot:
            await message.answer("❌ You cannot gift Pokémon to a bot!")
            return
            
        stmt = select(User).where(User.id == rep_user.id)
        res = await db.execute(stmt)
        target_user = res.scalar_one_or_none()
        gift_str = parts[1]
    else:
        if len(parts) < 3:
            await message.answer("⚠️ Format: `/gift <@username or user_id> <pokedex_id>[.form_index]`\n(or reply to their message with `/gift <pokedex_id>[.form_index]`)")
            return
            
        target_str = parts[1]
        gift_str = parts[2]
        
        if target_str.isdigit():
            stmt = select(User).where(User.id == int(target_str))
            res = await db.execute(stmt)
            target_user = res.scalar_one_or_none()
        elif target_str.startswith("@"):
            uname = target_str.replace("@", "").strip()
            stmt = select(User).where(User.username.ilike(uname))
            res = await db.execute(stmt)
            target_user = res.scalar_one_or_none()
            
    if not target_user:
        await message.answer("❌ Target trainer not found. They must have started the bot first.")
        return
        
    if target_user.id == message.from_user.id:
        await message.answer("❌ You cannot gift Pokémon to yourself!")
        return

    # 2. Parse pokedex_id and form_index
    form_index = 0
    pokedex_str = gift_str
    if "." in gift_str:
        pq, fq = gift_str.split(".", 1)
        if fq.isdigit():
            form_index = int(fq)
        pokedex_str = pq
        
    if not pokedex_str.isdigit():
        await message.answer("❌ Invalid Pokédex ID. Must be a number.")
        return
    pokedex_id = int(pokedex_str)
    
    # 3. Find if user owns this species and form (prefer non-shiny first)
    stmt = select(UserPokemon).options(joinedload(UserPokemon.pokemon)).where(
        UserPokemon.user_id == message.from_user.id,
        UserPokemon.pokemon_id == pokedex_id,
        UserPokemon.form_index == form_index
    ).order_by(UserPokemon.is_shiny.asc())
    res = await db.execute(stmt)
    up = res.scalars().first()
    
    if not up:
        form_names = {
            0: "Standard",
            1: "AMV/Art",
            2: "Dmax",
            3: "Gmax",
            4: "Z-Move",
            5: "Terastal"
        }
        f_name = form_names.get(form_index, f"Form {form_index}")
        await message.answer(f"❌ You do not own a <b>{f_name}</b> form of Pokédex #{pokedex_id:03d}!", parse_mode="HTML")
        return
        
    # 4. Transfer ownership
    old_user_id = up.user_id
    up.user_id = target_user.id
    
    # Clear cover favorite if they gifted their last copy of this species
    remain_stmt = select(UserPokemon.id).where(
        UserPokemon.user_id == old_user_id,
        UserPokemon.pokemon_id == pokedex_id
    ).limit(1)
    remain_res = await db.execute(remain_stmt)
    if remain_res.scalar() is None:
        from utils.favorite import get_favorite_id, set_favorite_id
        fav_val = get_favorite_id(old_user_id)
        if fav_val and (fav_val == str(pokedex_id) or fav_val.startswith(f"{pokedex_id}.")):
            set_favorite_id(old_user_id, None)
            
    await db.commit()
    
    # Success message
    shiny_badge = "✨ Shiny " if up.is_shiny else ""
    form_names = {
        0: "",
        1: "AMV ",
        2: "Dmax ",
        3: "Gmax ",
        4: "Z-Move ",
        5: "Terastal "
    }
    form_badge = form_names.get(form_index, f"Form {form_index} ")
    r_emoji = get_rarity_emoji(up.pokemon.rarity)
    
    sender_name = message.from_user.first_name
    receiver_name = target_user.nickname or "Trainer"
    
    text = (
        f"🎁 <b>POKÉMON GIFTED!</b> 🎁\n"
        f"───────────────\n"
        f"Trainer <b>{escape_md(sender_name)}</b> gifted a Pokémon to <b>{escape_md(receiver_name)}</b>!\n\n"
        f"💝 Pokémon: {r_emoji} {shiny_badge}{form_badge}<b>{up.pokemon.name.title()}</b>\n"
        f"───────────────"
    )
    await message.answer(text, parse_mode="HTML")

