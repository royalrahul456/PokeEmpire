import random
import traceback
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
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
            await message.answer("⚠️ No wild Pokémon in your DM! Use `/hunt` to find one.", parse_mode="Markdown")
        else:
            await message.answer("⚠️ There are no active wild Pokémon here! Keep chatting to spawn one.")
        return

    # 2. Fetch Pokémon details
    poke_stmt = select(Pokemon).where(Pokemon.id == spawn.pokemon_id)
    poke_res = await db.execute(poke_stmt)
    pokemon = poke_res.scalar_one()

    # 3. Check guess correctness
    if guess != pokemon.name.lower():
        await message.answer("❌ That name is incorrect! Take another look and try again.")
        return

    # 4. Perform database transaction to catch
    # Re-check active spawn still exists (prevents double-catch)
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
        user_stmt = select(User).where(User.id == user_id)
        user_res = await db.execute(user_stmt)
        user = user_res.scalar_one_or_none()

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

        is_shiny = spawn.is_shiny
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

        # 5. Announce winner
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
            f"💰 **Reward**: `💰 +{coins_won} coins`\n"
            f"📊 **Level**: `Lvl 1`\n"
            f"🧬 **IV Quality**: `🧬 {iv_pct}%`\n"
            f"• HP IV: `[{hp_bar}]` `({iv_hp}/31)`\n"
            f"• ATK IV: `[{atk_bar}]` `({iv_atk}/31)`\n"
            f"• DEF IV: `[{def_bar}]` `({iv_def}/31)`\n"
            f"• SPD IV: `[{spd_bar}]` `({iv_spd}/31)`\n"
            f"───────────────"
        )
        await message.answer(announcement, parse_mode="Markdown")

    except Exception as e:
        # Rollback broken transaction before any further DB operations
        await db.rollback()
        # Log full error to Render logs for diagnosis
        print(f"[CATCH ERROR] user={user_id} chat={chat_id} pokemon={pokemon.name} error_type={type(e).__name__}: {e}")
        traceback.print_exc()
        await message.answer(
            f"❌ **Catch failed!** A database error occurred.\n"
            f"Please try again. If this keeps happening, contact the bot owner."
        )


