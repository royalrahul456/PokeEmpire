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
from utils.favorite import get_favorite_id, set_favorite_id
from utils.settings import send_cover_media, get_custom_cover

router = Router()

FORM_INDEX_MAP = {
    "AMV": 1,
    "Dmax": 2,
    "Gmax": 3,
    "Z-Move": 4,
    "Terastal": 5,
}

FORM_LABELS = {
    0: "Standard",
    1: "AMV",
    2: "Dmax",
    3: "Gmax",
    4: "Z-Move",
    5: "Terastal",
}

def parse_form_filter(form_str: str) -> int | None:
    form_str = form_str.strip().lower()
    if form_str.isdigit():
        return int(form_str)
    mapping = {
        "amv": 1,
        "art": 1,
        "dmax": 2,
        "gmax": 3,
        "z-move": 4,
        "zmove": 4,
        "z": 4,
        "terastal": 5,
        "tera": 5,
    }
    return mapping.get(form_str)


FORM_FILTER_LABELS = {
    "AMV": "AMV / Art",
}


def get_filter_display_label(rarity_filter: str) -> str:
    return FORM_FILTER_LABELS.get(rarity_filter, rarity_filter)


def get_media_type_from_value(media_value: str | None) -> str | None:
    if not media_value:
        return None
    if media_value.startswith("photo:"):
        return "photo"
    if media_value.startswith("video:"):
        return "video"
    if media_value.startswith("animation:"):
        return "animation"
    if media_value.startswith("http"):
        return "photo"
    return "video"


def get_form_label(form_index: int, media_value: str | None = None) -> str:
    if form_index == 1:
        return "Art" if get_media_type_from_value(media_value) == "photo" else "AMV"
    return FORM_LABELS.get(form_index, f"Form {form_index}")


def parse_stored_media_value(media_value: str | None) -> tuple[str, str | None]:
    if not media_value:
        return "photo", None
    if ":" in media_value:
        media_type, clean_value = media_value.split(":", 1)
        if media_type in {"photo", "video", "animation"}:
            return media_type, clean_value
    if media_value.startswith("http"):
        return "photo", media_value
    return "video", media_value


async def get_form_media_lookup(db: AsyncSession, pokemon_ids: list[int]) -> dict[tuple[int, int], str]:
    if not pokemon_ids:
        return {}

    from database.models import PokemonFormMedia

    stmt = select(
        PokemonFormMedia.pokemon_id,
        PokemonFormMedia.form_index,
        PokemonFormMedia.media_value,
    ).where(PokemonFormMedia.pokemon_id.in_(pokemon_ids))
    res = await db.execute(stmt)
    return {(pid, form_index): media_value for pid, form_index, media_value in res.all()}


async def get_single_form_media_value(db: AsyncSession, pokemon_id: int, form_index: int) -> str | None:
    if form_index <= 0:
        return None

    from database.models import PokemonFormMedia

    stmt = select(PokemonFormMedia.media_value).where(
        PokemonFormMedia.pokemon_id == pokemon_id,
        PokemonFormMedia.form_index == form_index,
    ).limit(1)
    res = await db.execute(stmt)
    return res.scalar_one_or_none()

async def get_player_cover_media(user_id: int, db: AsyncSession) -> tuple[str, str]:
    """
    Resolves the cover media for a trainer.
    Returns (media_type, media_value)
    """
    fav_val = await get_favorite_id(user_id, db)
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
    uncommons = rarity_counts.get("Uncommon", 0)
    mediums = rarity_counts.get("Medium", 0)
    rares = rarity_counts.get("Rare", 0)
    epics = rarity_counts.get("Epic", 0)
    legendaries = rarity_counts.get("Legendary", 0)
    mythicals = rarity_counts.get("Mythical", 0)

    # Count form-based (AMV/Art=1, Dmax=2, Gmax=3, Z-Move=4, Terastal=5)
    from database.models import PokemonFormMedia
    form_counts_stmt = select(UserPokemon.form_index, func.count(distinct(UserPokemon.pokemon_id))).where(
        UserPokemon.user_id == user_id, UserPokemon.form_index > 0
    ).group_by(UserPokemon.form_index)
    form_counts_res = await db.execute(form_counts_stmt)
    form_counts = {fi: cnt for fi, cnt in form_counts_res.all()}
    amv_count = form_counts.get(1, 0)
    dmax_count = form_counts.get(2, 0)
    gmax_count = form_counts.get(3, 0)
    zmove_count = form_counts.get(4, 0)
    terastal_count = form_counts.get(5, 0)

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
        f"├─➩ 🟢 Uncommon: {uncommons}\n"
        f"├─➩ 🔵 Medium: {mediums}\n"
        f"├─➩ 🟣 Rare: {rares}\n"
        f"├─➩ 🔮 Epic: {epics}\n"
        f"├─➩ 🌟 Legendary: {legendaries}\n"
        f"├─➩ 🌌 Mythical: {mythicals}\n"
        f"├─➩ ✨ Shiny: {total_shiny}\n"
        f"╰───────────────────\n\n"
        f"╭─ Forms Breakdown ─\n"
        f"├─➩ 🎬 AMV / Art: {amv_count}\n"
        f"├─➩ ⚡ Dmax: {dmax_count}\n"
        f"├─➩ 💥 Gmax: {gmax_count}\n"
        f"├─➩ 🌀 Z-Move: {zmove_count}\n"
        f"├─➩ 🔮 Terastal: {terastal_count}\n"
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
    from database.models import PokemonFormMedia

    form_idx = FORM_INDEX_MAP.get(rarity_filter)
    filter_label = get_filter_display_label(rarity_filter)

    if form_idx is not None:
        view_mode = "form"
    elif rarity_filter and rarity_filter != "All":
        view_mode = "rarity"
    else:
        view_mode = "all"

    if view_mode == "all":
        total_species_res = await db.execute(select(func.count(Pokemon.id)))
        total_species = total_species_res.scalar() or 0
        total_forms_res = await db.execute(select(func.count(PokemonFormMedia.form_index)))
        total_forms = total_forms_res.scalar() or 0
        total_entries = total_species + total_forms

        caught_entries_subq = (
            select(UserPokemon.pokemon_id, UserPokemon.form_index)
            .where(UserPokemon.user_id == user_id)
            .group_by(UserPokemon.pokemon_id, UserPokemon.form_index)
            .subquery()
        )
        caught_count_res = await db.execute(select(func.count()).select_from(caught_entries_subq))
        caught_count = caught_count_res.scalar() or 0
    elif view_mode == "form":
        total_res = await db.execute(
            select(func.count(distinct(PokemonFormMedia.pokemon_id))).where(PokemonFormMedia.form_index == form_idx)
        )
        total_entries = total_res.scalar() or 0

        caught_entries_subq = (
            select(UserPokemon.pokemon_id)
            .where(UserPokemon.user_id == user_id, UserPokemon.form_index == form_idx)
            .group_by(UserPokemon.pokemon_id)
            .subquery()
        )
        caught_count_res = await db.execute(select(func.count()).select_from(caught_entries_subq))
        caught_count = caught_count_res.scalar() or 0
    else:
        total_res = await db.execute(select(func.count(Pokemon.id)).where(Pokemon.rarity == rarity_filter))
        total_entries = total_res.scalar() or 0

        caught_entries_subq = (
            select(UserPokemon.pokemon_id)
            .join(Pokemon, UserPokemon.pokemon_id == Pokemon.id)
            .where(UserPokemon.user_id == user_id, Pokemon.rarity == rarity_filter)
            .group_by(UserPokemon.pokemon_id)
            .subquery()
        )
        caught_count_res = await db.execute(select(func.count()).select_from(caught_entries_subq))
        caught_count = caught_count_res.scalar() or 0

    if caught_count == 0:
        filter_str = f" ({html.escape(filter_label)})" if rarity_filter and rarity_filter != "All" else ""
        text = (
            f"<b>{html.escape(nickname)}'s Pokedex</b>{filter_str}\n\n"
            f"<b>Your Pokedex is empty.</b>\n"
            f"Catch Pokemon in a group chat first to register them here."
        )
        return text, 0, 0

    per_page = 15
    max_page = max(1, (caught_count + per_page - 1) // per_page)
    if page < 1:
        page = 1
    if page > max_page:
        page = max_page

    offset = (page - 1) * per_page

    if view_mode == "all":
        poke_stmt = (
            select(
                Pokemon,
                UserPokemon.form_index.label("entry_form_index"),
                func.count(UserPokemon.id).label("total_caught"),
                func.max(case((UserPokemon.is_shiny == True, 1), else_=0)).label("has_shiny"),
            )
            .join(UserPokemon, UserPokemon.pokemon_id == Pokemon.id)
            .where(UserPokemon.user_id == user_id)
            .group_by(Pokemon.id, UserPokemon.form_index)
            .order_by(Pokemon.id, UserPokemon.form_index)
            .offset(offset)
            .limit(per_page)
        )
        poke_res = await db.execute(poke_stmt)
        page_entries = [
            {
                "pokemon": pokemon,
                "form_index": form_index,
                "total_caught": total_caught,
                "has_shiny": bool(has_shiny),
            }
            for pokemon, form_index, total_caught, has_shiny in poke_res.all()
        ]
    elif view_mode == "form":
        poke_stmt = (
            select(
                Pokemon,
                UserPokemon.form_index.label("entry_form_index"),
                func.count(UserPokemon.id).label("total_caught"),
                func.max(case((UserPokemon.is_shiny == True, 1), else_=0)).label("has_shiny"),
            )
            .join(UserPokemon, UserPokemon.pokemon_id == Pokemon.id)
            .where(UserPokemon.user_id == user_id, UserPokemon.form_index == form_idx)
            .group_by(Pokemon.id, UserPokemon.form_index)
            .order_by(Pokemon.id, UserPokemon.form_index)
            .offset(offset)
            .limit(per_page)
        )
        poke_res = await db.execute(poke_stmt)
        page_entries = [
            {
                "pokemon": pokemon,
                "form_index": entry_form_index,
                "total_caught": total_caught,
                "has_shiny": bool(has_shiny),
            }
            for pokemon, entry_form_index, total_caught, has_shiny in poke_res.all()
        ]
    else:
        poke_stmt = (
            select(
                Pokemon,
                func.count(UserPokemon.id).label("total_caught"),
                func.max(case((UserPokemon.is_shiny == True, 1), else_=0)).label("has_shiny"),
            )
            .join(UserPokemon, UserPokemon.pokemon_id == Pokemon.id)
            .where(UserPokemon.user_id == user_id, Pokemon.rarity == rarity_filter)
            .group_by(Pokemon.id)
            .order_by(Pokemon.id)
            .offset(offset)
            .limit(per_page)
        )
        poke_res = await db.execute(poke_stmt)
        page_entries = [
            {
                "pokemon": pokemon,
                "form_index": 0,
                "total_caught": total_caught,
                "has_shiny": bool(has_shiny),
            }
            for pokemon, total_caught, has_shiny in poke_res.all()
        ]

    if view_mode == "all":
        gen_stats_subq = (
            select(Pokemon.generation.label("generation"), UserPokemon.pokemon_id, UserPokemon.form_index)
            .join(UserPokemon, UserPokemon.pokemon_id == Pokemon.id)
            .where(UserPokemon.user_id == user_id)
            .group_by(Pokemon.generation, UserPokemon.pokemon_id, UserPokemon.form_index)
            .subquery()
        )
        gen_stats_res = await db.execute(
            select(gen_stats_subq.c.generation, func.count()).group_by(gen_stats_subq.c.generation)
        )
        gen_stats = {gen: count for gen, count in gen_stats_res.all()}

        gen_species_res = await db.execute(
            select(Pokemon.generation, func.count(Pokemon.id)).group_by(Pokemon.generation)
        )
        gen_totals = {gen: count for gen, count in gen_species_res.all()}

        gen_form_res = await db.execute(
            select(Pokemon.generation, func.count(PokemonFormMedia.form_index))
            .join(PokemonFormMedia, PokemonFormMedia.pokemon_id == Pokemon.id)
            .group_by(Pokemon.generation)
        )
        for gen, count in gen_form_res.all():
            gen_totals[gen] = gen_totals.get(gen, 0) + count
    elif view_mode == "form":
        gen_stats_res = await db.execute(
            select(Pokemon.generation, func.count(distinct(UserPokemon.pokemon_id)))
            .join(UserPokemon, UserPokemon.pokemon_id == Pokemon.id)
            .where(UserPokemon.user_id == user_id, UserPokemon.form_index == form_idx)
            .group_by(Pokemon.generation)
        )
        gen_stats = {gen: count for gen, count in gen_stats_res.all()}

        gen_totals_res = await db.execute(
            select(Pokemon.generation, func.count(distinct(PokemonFormMedia.pokemon_id)))
            .join(PokemonFormMedia, PokemonFormMedia.pokemon_id == Pokemon.id)
            .where(PokemonFormMedia.form_index == form_idx)
            .group_by(Pokemon.generation)
        )
        gen_totals = {gen: count for gen, count in gen_totals_res.all()}
    else:
        gen_stats_res = await db.execute(
            select(Pokemon.generation, func.count(distinct(UserPokemon.pokemon_id)))
            .join(UserPokemon, UserPokemon.pokemon_id == Pokemon.id)
            .where(UserPokemon.user_id == user_id, Pokemon.rarity == rarity_filter)
            .group_by(Pokemon.generation)
        )
        gen_stats = {gen: count for gen, count in gen_stats_res.all()}

        gen_totals_res = await db.execute(
            select(Pokemon.generation, func.count(Pokemon.id))
            .where(Pokemon.rarity == rarity_filter)
            .group_by(Pokemon.generation)
        )
        gen_totals = {gen: count for gen, count in gen_totals_res.all()}

    page_pokemon_ids = list({entry["pokemon"].id for entry in page_entries})
    form_media_lookup = await get_form_media_lookup(db, page_pokemon_ids)

    owned_species_forms = {}
    if view_mode == "rarity" and page_pokemon_ids:
        owned_forms_stmt = select(UserPokemon.pokemon_id, UserPokemon.form_index).where(
            UserPokemon.user_id == user_id,
            UserPokemon.pokemon_id.in_(page_pokemon_ids),
            UserPokemon.form_index > 0,
        )
        owned_forms_res = await db.execute(owned_forms_stmt)
        for pokemon_id, owned_form_index in owned_forms_res.all():
            owned_species_forms.setdefault(pokemon_id, set()).add(owned_form_index)

    filter_str = f" ({html.escape(filter_label)})" if rarity_filter and rarity_filter != "All" else ""
    text = f"🌟 <b>{html.escape(nickname)}'s Pokédex</b> 🌟{filter_str} — Page {page}/{max_page}\n"

    rarity_badges = {
        "Common": "⚪️",
        "Uncommon": "🟢",
        "Medium": "🔵",
        "Rare": "🟣",
        "Epic": "🔮",
        "Legendary": "🌟",
        "Mythical": "🌌",
    }

    current_gen = None
    first_group = True
    for entry in page_entries:
        pokemon = entry["pokemon"]
        if pokemon.generation != current_gen:
            current_gen = pokemon.generation
            if not first_group:
                text += "\n"
            first_group = False
            text += f"Generation {current_gen} {gen_stats.get(current_gen, 0)}/{gen_totals.get(current_gen, 0)}\n"

        shiny_tag = " [✨]" if entry["has_shiny"] else ""
        total_caught = entry["total_caught"]
        pokemon_name = html.escape(pokemon.name.title())

        if view_mode == "rarity":
            base_badge = rarity_badges.get(pokemon.rarity, "⚪️")
            forms_owned = sorted(owned_species_forms.get(pokemon.id, set()))
            form_suffix = ""
            if forms_owned:
                form_icons = []
                for owned_form_index in forms_owned:
                    media_value = form_media_lookup.get((pokemon.id, owned_form_index))
                    form_label = get_form_label(owned_form_index, media_value)
                    form_icons.append(get_rarity_emoji(form_label))
                form_suffix = f" [{' '.join(form_icons)}]"
            text += f"◆ [ {base_badge} ] {pokemon.id} {pokemon_name}{shiny_tag}{form_suffix} ×{total_caught}\n"
            continue

        form_index = entry["form_index"]
        if form_index == 0:
            entry_badge = rarity_badges.get(pokemon.rarity, "⚪️")
            entry_id = str(pokemon.id)
            entry_name = pokemon_name
        else:
            media_value = form_media_lookup.get((pokemon.id, form_index))
            form_label = get_form_label(form_index, media_value)
            entry_badge = get_rarity_emoji(form_label)
            entry_id = f"{pokemon.id}.{form_index}"
            entry_name = f"{html.escape(form_label)} {pokemon_name}"

        text += f"◆ [ {entry_badge} ] {entry_id} {entry_name}{shiny_tag} ×{total_caught}\n"

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
        InlineKeyboardButton(text="🟢 Uncommon", callback_data=f"pd_setfilter_{user_id}_Uncommon")
    )
    builder.row(
        InlineKeyboardButton(text="🔵 Medium", callback_data=f"pd_setfilter_{user_id}_Medium"),
        InlineKeyboardButton(text="🟣 Rare", callback_data=f"pd_setfilter_{user_id}_Rare")
    )
    builder.row(
        InlineKeyboardButton(text="🔮 Epic", callback_data=f"pd_setfilter_{user_id}_Epic"),
        InlineKeyboardButton(text="🌟 Legendary", callback_data=f"pd_setfilter_{user_id}_Legendary")
    )
    builder.row(
        InlineKeyboardButton(text="🌌 Mythical", callback_data=f"pd_setfilter_{user_id}_Mythical"),
        InlineKeyboardButton(text="🎬 AMV / Art", callback_data=f"pd_setfilter_{user_id}_AMV")
    )
    builder.row(
        InlineKeyboardButton(text="⚡ Dmax", callback_data=f"pd_setfilter_{user_id}_Dmax"),
        InlineKeyboardButton(text="💥 Gmax", callback_data=f"pd_setfilter_{user_id}_Gmax")
    )
    builder.row(
        InlineKeyboardButton(text="🌀 Z-Move", callback_data=f"pd_setfilter_{user_id}_Z-Move"),
        InlineKeyboardButton(text="🔮 Terastal", callback_data=f"pd_setfilter_{user_id}_Terastal")
    )
    builder.row(
        InlineKeyboardButton(text="🌍 All", callback_data=f"pd_setfilter_{user_id}_All"),
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
            f"💟 <b>AMV Cover Favorite</b>\n"
            f"───────────────\n\n"
            f"Set your favorite Pokémon AMV / Art as the Pokédex cover illustration!\n\n"
            f"👉 <b>How to set</b>: Type <code>/fav &lt;pokedex_id&gt;.&lt;form_index&gt;</code> in chat.\n"
            f"<i>(e.g., <code>/fav 6.1</code> to set Charizard AMV as cover)</i>"
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
@router.message(Command("c"))
async def cmd_check_pokemon(message: Message, db: AsyncSession):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("⚠️ Format: `/check <pokemon_name_or_id>`\n(e.g., `/check bulbasaur` or `/check 1`)")
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
        f"<b>🌟 Pokemon Info</b>\n"
        f"🆔 <b>ID</b>: <code>{id_str}</code>\n"
        f"⛔ <b>Name</b>: {escape_md(name_str)}\n"
        f"🎦 <b>Generation</b>: Gen {pokemon.generation}\n"
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
    
    caption = f"🎦 <b>Who has this pokemon:</b>\n"
    if owners:
        owner_rows = []
        for idx, (uid, nick, count) in enumerate(owners, start=1):
            display_name = escape_md(nick or "Trainer")
            owner_rows.append(f"{idx}. <a href=\"tg://user?id={uid}\">{display_name}</a> ×{count}")
        caption += "\n".join(owner_rows)
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
    text = await get_leaderboard_text("catches", db)
    
    await send_cover_media(
        chat_id=message.chat.id,
        key="leaderboard",
        caption=text,
        reply_markup=get_leaderboard_keyboard(),
        bot=message.bot,
        default_url="https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/493.png",
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
    await set_favorite_id(user_id, fav_str, db)
    
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
async def cmd_unfav(message: Message, db: AsyncSession):
    user_id = message.from_user.id
    await set_favorite_id(user_id, None, db)
    await message.answer("❌ Cleared your favorite cover. A random Pokémon from your bag will be shown instead.")

@router.message(Command("search"))
@router.message(Command("s"))
@router.message(Command("cid"))
async def cmd_search(message: Message, db: AsyncSession):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("Format: `/search <pokemon_name_or_id>`\nExample: `/search bulbasaur` or `/search 6`", parse_mode="Markdown")
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
        f"🦧 <b>{escape_md(pokemon.name.title())}</b>\n"
        f"┣━ 🎦 {escape_md(series_str)}\n"
        f"┣━ 📊 Total variants: <b>{total_variants}</b> — Page <b>{page}/{total_pages}</b>\n\n"
    )
    
    for form_index, label, emoji, entry_id in page_variants:
        caption += f"┣━ {emoji} {label} | ID: <code>{entry_id}</code>\n"
        
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
    uncommons = rarity_counts.get("Uncommon", 0)
    mediums = rarity_counts.get("Medium", 0)
    rares = rarity_counts.get("Rare", 0)
    epics = rarity_counts.get("Epic", 0)
    legendaries = rarity_counts.get("Legendary", 0)
    mythicals = rarity_counts.get("Mythical", 0)

    # Count form-based (AMV/Art=1, Dmax=2, Gmax=3, Z-Move=4, Terastal=5)
    from database.models import PokemonFormMedia
    form_counts_stmt = select(UserPokemon.form_index, func.count(distinct(UserPokemon.pokemon_id))).where(
        UserPokemon.user_id == user_id, UserPokemon.form_index > 0
    ).group_by(UserPokemon.form_index)
    form_counts_res = await db.execute(form_counts_stmt)
    form_counts = {fi: cnt for fi, cnt in form_counts_res.all()}
    amv_count = form_counts.get(1, 0)
    dmax_count = form_counts.get(2, 0)
    gmax_count = form_counts.get(3, 0)
    zmove_count = form_counts.get(4, 0)
    terastal_count = form_counts.get(5, 0)

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
        f"├─➩ 🟢 Uncommon: {uncommons}\n"
        f"├─➩ 🔵 Medium: {mediums}\n"
        f"├─➩ 🟣 Rare: {rares}\n"
        f"├─➩ 🔮 Epic: {epics}\n"
        f"├─➩ 🌟 Legendary: {legendaries}\n"
        f"├─➩ 🌌 Mythical: {mythicals}\n"
        f"├─➩ ✨ Shiny: {total_shiny}\n"
        f"╰───────────────────\n\n"
        f"╭─ Forms Breakdown ─\n"
        f"├─➩ 🎬 AMV / Art: {amv_count}\n"
        f"├─➩ ⚡ Dmax: {dmax_count}\n"
        f"├─➩ 💥 Gmax: {gmax_count}\n"
        f"├─➩ 🌀 Z-Move: {zmove_count}\n"
        f"├─➩ 🔮 Terastal: {terastal_count}\n"
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
        fav_val = await get_favorite_id(old_user_id, db)
        if fav_val and (fav_val == str(pokedex_id) or fav_val.startswith(f"{pokedex_id}.")):
            await set_favorite_id(old_user_id, None, db)
            
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
    
    # Resolve media of the gifted Pokémon
    media_value = up.pokemon.image_url
    media_type = "photo"
    if up.form_index > 0:
        form_media = await get_single_form_media_value(db, up.pokemon_id, up.form_index)
        if form_media:
            media_type, media_value = parse_stored_media_value(form_media)
    else:
        if up.pokemon.video_url:
            media_type = "video"
            media_value = up.pokemon.video_url

    pokemon_display = f"{r_emoji} {shiny_badge}{form_badge}<b>{up.pokemon.name.title()}</b>"

    caption = (
        f"🎁 <b>POKÉMON GIFTED!</b> 🎁\n"
        f"<blockquote>👤 Sender: <b>{escape_md(sender_name)}</b>\n"
        f"👤 Recipient: <b>{escape_md(receiver_name)}</b>\n"
        f"💝 Pokémon: {pokemon_display}</blockquote>"
    )

    from aiogram.types import FSInputFile
    if isinstance(media_value, str) and os.path.exists(media_value):
        media_value = FSInputFile(media_value)

    try:
        if media_type == "video":
            await message.answer_video(video=media_value, caption=caption, parse_mode="HTML")
        elif media_type == "animation":
            await message.answer_animation(animation=media_value, caption=caption, parse_mode="HTML")
        else:
            await message.answer_photo(photo=media_value, caption=caption, parse_mode="HTML")
    except Exception as e:
        print(f"Error sending player gifted pokemon media: {e}")
        await message.answer(caption, parse_mode="HTML")

    # Send private DM to recipient
    dm_text = (
        f"📣 <b>You received a Gift!</b>\n"
        f"<blockquote>👤 Sender: <b>{escape_md(sender_name)}</b>\n"
        f"💝 Pokémon: {pokemon_display}</blockquote>"
    )
    try:
        await message.bot.send_message(chat_id=target_user.id, text=dm_text, parse_mode="HTML")
    except Exception:
        pass


