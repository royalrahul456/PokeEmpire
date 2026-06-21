import random
import traceback
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
import config
from database.models import User, Pokemon, UserPokemon, ActiveSpawn
from utils.formatters import get_progress_bar, get_rarity_emoji

router = Router()

@router.message(Command("catch"))
async def cmd_catch(message: Message, db: AsyncSession):
    chat_id = message.chat.id
    user_id = message.from_user.id
    username = message.from_user.username
    nickname = message.from_user.first_name

    # Check command parameter
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("⚠️ Format: `/catch <pokemon_name>`")
        return

    guess = parts[1].strip().lower()

    # 1. Fetch active spawn
    spawn_stmt = select(ActiveSpawn).where(ActiveSpawn.chat_id == chat_id)
    spawn_res = await db.execute(spawn_stmt)
    spawn = spawn_res.scalar_one_or_none()

    if not spawn:
        if message.chat.type == "private":
            await message.answer("⚠️ Wild Pokémon only spawn in group chats during active conversations.", parse_mode="Markdown")
        else:
            await message.answer("⚠️ There are no active wild Pokémon here! Keep chatting to spawn one.")
        return

    # 2. Fetch Pokémon details
    poke_stmt = select(Pokemon).where(Pokemon.id == spawn.pokemon_id)
    poke_res = await db.execute(poke_stmt)
    pokemon = poke_res.scalar_one()
    pokemon_name = pokemon.name  # Save as plain string before any try/rollback
    pokemon_id = pokemon.id
    pokemon_rarity = pokemon.rarity

    # 3. Check guess correctness
    actual_name = pokemon.name.lower()
    # Accept base name for form variants by stripping known suffixes from the END only
    # e.g. "basculegion-male" → "basculegion", "mr-mime-galarian" → "mr-mime"
    FORM_SUFFIXES = {"male", "female", "galarian", "alolan", "hisuian", "paldean",
                     "galar", "alola", "hisui", "paldea", "mega", "gmax", "primal",
                     "origin", "sky", "land", "incarnate", "therian", "black", "white",
                     "attack", "defense", "speed", "sunshine", "rainy", "snowy",
                     "heat", "wash", "frost", "fan", "mow", "altered", "overcast",
                     "sandy", "trash", "plant", "east", "west", "north", "south"}
    base_name = actual_name
    if "-" in actual_name:
        parts = actual_name.rsplit("-", 1)
        if parts[-1] in FORM_SUFFIXES:
            base_name = parts[0]
    if guess != actual_name and guess != base_name:
        await message.answer("❌ That name is incorrect! Take another look and try again.")
        return

    # 4. Check user registration & union membership for new players
    user_stmt = select(User).where(User.id == user_id)
    user_res = await db.execute(user_stmt)
    user = user_res.scalar_one_or_none()

    if not user:
        # Check union group membership
        try:
            member = await message.bot.get_chat_member(chat_id="@pokeempireunion", user_id=user_id)
            is_member = member.status in ["creator", "administrator", "member", "restricted"]
        except Exception:
            is_member = False

        if not is_member:
            from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
            kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🌲 Join PokéEmpire Union", url="https://t.me/pokeempireunion")]
            ])
            await message.answer(
                "❌ **Catch Denied! First-Time Player Registration Required** 🌲\n\n"
                "To start your PokéEmpire journey and catch your very first Pokémon, "
                "you must first join our official Union Group!\n\n"
                "👉 Join below, then try catching again!",
                reply_markup=kb
            )
            return

    # 5. Re-check active spawn still exists (prevents double-catch)
    rechk_stmt = select(ActiveSpawn).where(ActiveSpawn.chat_id == chat_id)
    rechk_res = await db.execute(rechk_stmt)
    active_lock = rechk_res.scalar_one_or_none()

    if not active_lock:
        await message.answer("⚠️ Too slow! Someone else caught this Pokémon already.")
        return

    try:
        # Delete active spawn using direct SQL (avoids ORM identity-map conflicts with asyncpg)
        await db.execute(delete(ActiveSpawn).where(ActiveSpawn.chat_id == chat_id))
        await db.flush()

        # Check and register user in DB if they don't exist yet
        if not user:
            user = User(
                id=user_id,
                username=username,
                nickname=nickname
            )
            db.add(user)
            await db.flush()

        # Create capture entry with random IVs
        iv_hp = random.randint(0, 31)
        iv_atk = random.randint(0, 31)
        iv_def = random.randint(0, 31)
        iv_spd = random.randint(0, 31)
        iv_total = iv_hp + iv_atk + iv_def + iv_spd
        iv_pct = int((iv_total / 124) * 100)

        # Award coins on catch
        coins_won = random.randint(30, 80)
        user.coins += coins_won

        # Shiny Charm roll (1 in 100 chance to upgrade)
        is_shiny = spawn.is_shiny
        shiny_upgraded = False
        if not is_shiny and user.has_shiny_charm:
            if random.randint(1, 100) == 1:
                is_shiny = True
                shiny_upgraded = True

        capture = UserPokemon(
            user_id=user_id,
            pokemon_id=pokemon.id,
            is_shiny=is_shiny,
            level=1,
            xp=0,
            iv_hp=iv_hp,
            iv_atk=iv_atk,
            iv_def=iv_def,
            iv_spd=iv_spd
        )
        db.add(capture)
        await db.commit()

        # Increment daily catch streak
        from utils.streak import increment_streak_catch, get_streak_data
        secured, current_count = await increment_streak_catch(user_id)
        streak_info = await get_streak_data(user_id)

        streak_days = streak_info.get("current_streak", 0)
        capped_count = min(current_count, 3)
        streak_bar_chars = "█" * (capped_count * 3) + "░" * (10 - (capped_count * 3))
        if capped_count == 3:
            streak_bar_chars = "█" * 10

        streak_msg = f"🔥 **Streak Progress**: `[{streak_bar_chars}] {capped_count}/3`"
        if secured:
            streak_msg += f"\n🎉 **Streak Secured!** (Current: `{streak_days} days`)"
        elif capped_count >= 3:
            streak_msg += f"\n✨ **Streak Secured today!** (Current: `{streak_days} days`)"

        # 6. Announce winner
        shiny_badge = "✨ Shiny " if is_shiny else ""
        poke_display = pokemon.name.title()
        r_emoji = get_rarity_emoji(pokemon.rarity)
        
        # Generate small progress bars for IVs
        hp_bar = get_progress_bar(iv_hp, 31, 5, fill_char="▰", empty_char="▱")
        atk_bar = get_progress_bar(iv_atk, 31, 5, fill_char="▰", empty_char="▱")
        def_bar = get_progress_bar(iv_def, 31, 5, fill_char="▰", empty_char="▱")
        spd_bar = get_progress_bar(iv_spd, 31, 5, fill_char="▰", empty_char="▱")

        announcement = (
            f"🎉 **SUCCESSFUL CATCH!** 🎉\n"
            f"───────────────\n"
            f"Trainer **{user.nickname}** successfully caught the wild {r_emoji} {shiny_badge}**{poke_display}**!\n\n"
        )
        if shiny_upgraded:
            announcement += "🍀 ✨ **Shiny Charm Activated!** Your catch was upgraded to a **Shiny**! ✨\n\n"
            
        announcement += (
            f"💰 **Reward**: `💰 +{coins_won} coins`\n"
            f"───────────────\n"
            f"{streak_msg}\n"
            f"───────────────"
        )
        await message.answer(announcement, parse_mode="Markdown")

    except Exception as e:
        # Rollback broken transaction before any further DB operations
        await db.rollback()
        # Log full error to Render logs for diagnosis
        # Use pre-saved pokemon_name (not pokemon.name) to avoid MissingGreenlet error after rollback
        print(f"[CATCH ERROR] user={user_id} chat={chat_id} pokemon={pokemon_name} error_type={type(e).__name__}: {e}")
        traceback.print_exc()
        await message.answer(
            f"❌ **Catch failed!** A database error occurred.\n"
            f"Please try again. If this keeps happening, contact the bot owner."
        )

@router.callback_query(F.data == "spawn_hint")
async def cb_spawn_hint(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id
    chat_id = callback.message.chat.id

    # 1. Fetch active spawn for this chat
    spawn_stmt = select(ActiveSpawn).where(ActiveSpawn.chat_id == chat_id)
    spawn_res = await db.execute(spawn_stmt)
    spawn = spawn_res.scalar_one_or_none()

    if not spawn:
        await callback.answer("⚠️ There is no active wild Pokémon to get a hint for!", show_alert=True)
        return

    # 2. Fetch Pokémon details
    poke_stmt = select(Pokemon).where(Pokemon.id == spawn.pokemon_id)
    poke_res = await db.execute(poke_stmt)
    pokemon = poke_res.scalar_one()
    pokemon_name = pokemon.name.title()

    # 3. Check if user is owner
    is_owner = user_id in config.ADMIN_IDS

    if is_owner:
        # Owner gets it for free!
        await callback.answer(f"💡 [ADMIN HINT] The Pokémon is: {pokemon_name}", show_alert=True)
        return

    # 4. If not owner, check user's coins balance
    user_stmt = select(User).where(User.id == user_id)
    user_res = await db.execute(user_stmt)
    user = user_res.scalar_one_or_none()

    # If user is not registered in database yet (e.g. brand new user)
    if not user:
        await callback.answer("❌ You must register first by typing /start or catching a Pokémon!", show_alert=True)
        return

    if user.coins < 2000:
        await callback.answer(f"❌ You need 2,000 coins to buy a hint! You currently have {user.coins} coins.", show_alert=True)
        return

    # 5. Deduct coins and reveal hint
    try:
        user.coins -= 2000
        await db.commit()
        await callback.answer(f"💡 Hint purchased for 2,000 coins!\nThe Pokémon is: {pokemon_name}", show_alert=True)
    except Exception as e:
        await db.rollback()
        print(f"[HINT ERROR] user={user_id} error={e}")
        await callback.answer("❌ An error occurred while purchasing the hint. Please try again.", show_alert=True)


