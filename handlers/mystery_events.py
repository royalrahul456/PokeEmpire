import random
import time
import html
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import config
from database.models import Pokemon, User, GlobalSetting
from services.spawn_service import SpawnService
from utils.trainer_level import log_transaction, add_trainer_xp

router = Router()

active_grass_events = {}  # chat_id -> dict
active_daily_mystery_event = {
    "active": False,
    "mutator": None,
    "expires_at": 0
}

EVENT_MUTATORS = [
    {
        "key": "shiny_surge",
        "title": "🌟 2x Shiny & Legendary Spawn Frenzy!",
        "desc": "Shiny & Legendary Pokémon rates are DOUBLED for 10 minutes!"
    },
    {
        "key": "coin_surge",
        "title": "🪙 Golden Coin Surge!",
        "desc": "Earn DOUBLE coins from all minigames, trivia, and catches!"
    },
    {
        "key": "form_outbreak",
        "title": "🎨 Custom Form Outbreak!",
        "desc": "Rare Custom Form & AMV Pokémon are active in the wild!"
    },
    {
        "key": "gift_crate",
        "title": "🎁 Mystery Gift Crate Drop!",
        "desc": "Claim free bonus Coin Crates for all investigators!"
    }
]

@router.message(Command("spawnmystery", "mysteryspawn"))
async def cmd_spawn_mystery(message: Message, db: AsyncSession):
    if message.chat.type not in ["group", "supergroup"]:
        await message.answer("⚠️ Mystery Grass events can only be triggered in group chats!")
        return

    user_id = message.from_user.id if message.from_user else 0
    if user_id not in config.ADMIN_IDS:
        await message.answer("❌ Denied. Only Bot Admins & Owner can manually trigger mystery grass events.")
        return

    chat_id = message.chat.id
    await trigger_tall_grass_event(chat_id, message.bot, db)

async def trigger_tall_grass_event(chat_id: int, bot, db: AsyncSession):
    """Posts mystery grass event in group chat."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔎 Investigate", callback_data=f"grass_investigate_{chat_id}"),
        InlineKeyboardButton(text="🚶 Ignore", callback_data="grass_ignore")
    )

    text = (
        f"🌿 <b>SOMETHING IS MOVING IN THE TALL GRASS...</b> 🌿\n"
        f"◈ ────────────────── ◈\n"
        f"<i>Rustle... Rustle... A mysterious creature is lurking nearby! Will you check it out?</i>"
    )

    msg = await bot.send_message(chat_id, text, reply_markup=builder.as_markup(), parse_mode="HTML")
    active_grass_events[chat_id] = {
        "message_id": msg.message_id,
        "investigated": False
    }

@router.callback_query(F.data.startswith("grass_investigate_"))
async def cb_grass_investigate(callback: CallbackQuery, db: AsyncSession):
    chat_id = callback.message.chat.id
    event_data = active_grass_events.get(chat_id)

    if not event_data or event_data.get("investigated"):
        await callback.answer("⚠️ This mystery grass event has already been investigated or expired!", show_alert=True)
        return

    event_data["investigated"] = True
    user = callback.from_user
    user_name = html.escape(user.first_name or user.username or f"Trainer {user.id}")

    # Boosted rarity spawn (pick Epic/Legendary/Mythical/Rare)
    rarities = ["Rare", "Epic", "Legendary", "Mythical"]
    weights = [40, 35, 20, 5]
    chosen_rarity = random.choices(rarities, weights=weights, k=1)[0]

    # Trigger wild spawn with boosted rarity
    success = await SpawnService.trigger_spawn(db, chat_id, callback.bot, rarity=chosen_rarity)

    # Award investigator 150 EXP
    u_stmt = select(User).where(User.id == user.id)
    u_res = await db.execute(u_stmt)
    u_rec = u_res.scalar_one_or_none()
    if u_rec:
        await add_trainer_xp(u_rec, 150, db, callback.bot, chat_id)

    await callback.answer(f"🔎 You investigated the grass and found a {chosen_rarity} Pokémon! +150 EXP", show_alert=True)

    text = (
        f"🔎 <b>TRAINER {user_name.upper()} INVESTIGATED THE GRASS!</b> 🔎\n"
        f"◈ ────────────────── ◈\n"
        f"💥 <i>A wild <b>{chosen_rarity} Pokémon</b> jumped out of the bushes!</i>"
    )
    try:
        await callback.message.edit_text(text, parse_mode="HTML")
    except Exception:
        pass

@router.callback_query(F.data == "grass_ignore")
async def cb_grass_ignore(callback: CallbackQuery):
    await callback.answer("🚶 You quietly backed away from the rustling grass...", show_alert=True)

@router.message(Command("trigger_mystery_event"))
async def cmd_trigger_daily_mystery(message: Message, db: AsyncSession):
    if not message.from_user or message.from_user.id not in config.ADMIN_IDS:
        await message.answer("❌ Denied. Only Bot Owner can trigger global Daily Mystery Events.")
        return

    mutator = random.choice(EVENT_MUTATORS)
    active_daily_mystery_event["active"] = True
    active_daily_mystery_event["mutator"] = mutator
    active_daily_mystery_event["expires_at"] = time.time() + 600  # 10 minutes

    text = (
        f"🚨 <b>MYSTERY EVENT ACTIVATED!</b> 🚨\n"
        f"◈ ────────────────── ◈\n"
        f"⏳ <b>Duration:</b> <i>Next 10 Minutes Only!</i>\n\n"
        f"💥 <b>Active Event:</b> {mutator['title']}\n"
        f"ℹ️ {mutator['desc']}\n"
        f"◈ ────────────────── ◈\n"
        f"👀 <i>Enjoy the special mystery bonus across PokeEmpire for 10 minutes!</i>"
    )

    if message.chat.type in ["group", "supergroup"]:
        await message.answer(text, parse_mode="HTML")
    else:
        await message.answer("🚨 Global 10-Minute Mystery Event Triggered!", parse_mode="HTML")
