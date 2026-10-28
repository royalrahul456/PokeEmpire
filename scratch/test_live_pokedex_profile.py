import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import asyncio
import html
from aiogram import Bot
from sqlalchemy import select, func, distinct
from database.database import SessionLocal
from database.models import User, UserPokemon, Pokemon
import config
from utils.formatters import get_progress_bar
from utils.favorite import get_favorite_id
from utils.settings import get_all_custom_rarities, get_custom_rarity_forms
from utils.streak import get_streak_data
from utils.trainer_level import get_trainer_title, get_xp_required_for_next_level
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from handlers.profile import send_player_cover

async def test_profile_live():
    gc_id = -1004441222762
    print(f"Testing live /profile output to official GC {gc_id}...", flush=True)

    bot = Bot(config.BOT_TOKEN)
    async with SessionLocal() as db:
        u_stmt = select(User).limit(1)
        u_res = await db.execute(u_stmt)
        user = u_res.scalar_one_or_none()

        if not user:
            print("No user found.", flush=True)
            await bot.session.close()
            return

        user_id = user.id
        count_stmt = select(func.count(UserPokemon.id)).where(UserPokemon.user_id == user_id)
        total_caught = (await db.execute(count_stmt)).scalar() or 0

        unique_stmt = select(func.count(distinct(UserPokemon.pokemon_id))).where(UserPokemon.user_id == user_id)
        unique_caught = (await db.execute(unique_stmt)).scalar() or 0

        total_species_stmt = select(func.count(Pokemon.id))
        total_species = (await db.execute(total_species_stmt)).scalar() or 1

        dex_pct = (unique_caught / total_species) * 100
        dex_bar = get_progress_bar(unique_caught, total_species, 10, fill_char="▰", empty_char="▱")

        rarity_stmt = select(Pokemon.rarity, func.count(UserPokemon.id)).join(UserPokemon).where(UserPokemon.user_id == user_id).group_by(Pokemon.rarity)
        rarity_counts = {r: count for r, count in (await db.execute(rarity_stmt)).all()}

        standard_breakdown = [("Common", "⚪️"), ("Uncommon", "🟢"), ("Medium", "🔵"), ("Rare", "🟣"), ("Epic", "🔮"), ("Legendary", "🌟"), ("Mythical", "🌌")]
        breakdown_lines = []
        for i in range(0, len(standard_breakdown), 2):
            pair = standard_breakdown[i:i+2]
            parts = [f"{r_emoji} {r_name}: <b>{rarity_counts.get(r_name, 0)}</b>" for r_name, r_emoji in pair]
            breakdown_lines.append(f"├─➩ " + " ┊ ".join(parts))
        rarity_breakdown_text = "\n".join(breakdown_lines)

        form_counts_stmt = select(UserPokemon.form_index, func.count(distinct(UserPokemon.pokemon_id))).where(UserPokemon.user_id == user_id, UserPokemon.form_index > 0).group_by(UserPokemon.form_index)
        form_counts = {fi: cnt for fi, cnt in (await db.execute(form_counts_stmt)).all()}

        forms_lines = [
            f"├─➩ 🎬 Art: <b>{form_counts.get(1, 0)}</b> ┊ ⚡ Dmax: <b>{form_counts.get(2, 0)}</b>",
            f"├─➩ 💥 Gmax: <b>{form_counts.get(3, 0)}</b> ┊ 🌀 Z-Move: <b>{form_counts.get(4, 0)}</b>",
            f"├─➩ 🔮 Terastal: <b>{form_counts.get(5, 0)}</b>"
        ]
        forms_breakdown_text = "\n".join(forms_lines)

        formatted_coins = f"{user.coins:,}"
        user_nickname = user.nickname or "Trainer"
        lvl = user.trainer_level or 1
        xp = user.trainer_xp or 0
        req_xp = get_xp_required_for_next_level(lvl)
        xp_pct = min(100, int((xp / req_xp) * 100)) if req_xp > 0 else 0
        xp_filled = xp_pct // 10
        xp_bar = "█" * xp_filled + "░" * (10 - xp_filled)
        title = get_trainer_title(lvl)

        profile_card = (
            f"╭──「 🏆 Trainer Profile 」\n"
            f"├─➩ 🏓 User: {html.escape(user_nickname)}\n"
            f"├─➩ 🆔 ID: <code>{user.id}</code>\n"
            f"├─➩ 🎖️ Level: <code>Lv. {lvl} ({title})</code>\n"
            f"├─➩ ⚡ EXP: [{xp_bar}] {xp_pct}% (<code>{xp:,}/{req_xp:,}</code>)\n"
            f"├─➩ 💰 Balance: <code>{formatted_coins} coins</code>\n"
            f"├─➩ ⚡ Pokémon: {unique_caught} (Total Catches: {total_caught})\n"
            f"├─➩ 🌍 Pokédex: {unique_caught}/{total_species} ({dex_pct:.3f}%)\n"
            f"├─➩ 🎁 Progress:\n"
            f"╰         {dex_bar}\n\n"
            f"╭─ Rarity Breakdown ─\n"
            f"{rarity_breakdown_text}\n"
            f"╰───────────────────\n\n"
            f"╭─ Forms Breakdown ─\n"
            f"{forms_breakdown_text}\n"
            f"╰───────────────────"
        )
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="📖 View Pokédex", callback_data=f"pd_page_{user_id}_1_All"))

        print("Sending /profile cover & text to official GC...", flush=True)
        msg_prof = await send_player_cover(
            chat_id=gc_id,
            user_id=user_id,
            caption=profile_card,
            reply_markup=builder.as_markup(),
            bot=bot,
            db=db
        )
        print(f"✅ /profile SENT SUCCESSFULLY! Message ID: {msg_prof.message_id}", flush=True)

    await bot.session.close()

if __name__ == '__main__':
    asyncio.run(test_profile_live())
