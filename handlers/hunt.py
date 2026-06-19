from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import config
from database.models import User, Inventory
from services.spawn_system import SpawnSystem
from services.quest_system import QuestSystem
from keyboards.inline import get_catch_keyboard
from utils.cooldowns import cooldowns
from utils.formatters import format_card_title

router = Router()
spawn_system = SpawnSystem()
quest_system = QuestSystem()

@router.message(Command("hunt"))
@router.callback_query(F.data == "menu_hunt")
async def cmd_hunt(event: Message | CallbackQuery, db: AsyncSession):
    user_id = event.from_user.id
    
    # Check if registered
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        msg = "⚠️ You must start the bot first with /start"
        if isinstance(event, CallbackQuery):
            await event.answer(msg, show_alert=True)
        else:
            await event.answer(msg)
        return

    # Check hunt cooldown
    allowed, seconds_left = cooldowns.trigger_action(user_id, "hunt", config.HUNT_COOLDOWN)
    if not allowed:
        msg = f"⏳ Your radar is recharging! You can hunt again in **{seconds_left}s**."
        if isinstance(event, CallbackQuery):
            await event.answer(msg.replace("**", ""), show_alert=True)
        else:
            await event.answer(msg, parse_mode="Markdown")
        return

    # Generate wild encounter
    try:
        encounter = spawn_system.generate_encounter()
    except Exception as e:
        cooldowns.clear_cooldown(user_id, "hunt")
        msg = "⚠️ An error occurred while generating a wild encounter."
        if isinstance(event, CallbackQuery):
            await event.answer(msg)
        else:
            await event.answer(msg)
        return

    # Query user's current balls
    ball_types = ["ball_basic", "ball_great", "ball_ultra", "ball_master"]
    balls_owned = {}
    for ball in ball_types:
        ball_stmt = select(Inventory).where(
            Inventory.user_id == user_id,
            Inventory.item_id == ball
        )
        ball_res = await db.execute(ball_stmt)
        inv = ball_res.scalar_one_or_none()
        balls_owned[ball] = inv.quantity if inv else 0

    # Format text description
    shiny_indicator = "✨ " if encounter["is_shiny"] else ""
    boosted_indicator = "🌀 **[WEATHER BOOSTED]**" if encounter["is_boosted"] else ""
    card_title = format_card_title(encounter["name"], encounter["is_shiny"], encounter["tier"])

    text = (
        f"🌲 **A wild monster appeared!** 🌲\n\n"
        f"{card_title}\n"
        f"• Level: **Lvl {encounter['level']}**\n"
        f"• Rarity: **{encounter['tier']}**\n"
        f"• Types: **{', '.join(encounter['types'])}**\n"
        f"• Current Weather: 🌤️ **{encounter['weather']}**\n"
        f"{boosted_indicator}\n\n"
        f"Choose a capture device to throw:"
    )

    # Track Quest hunt progression
    completed_quests = await quest_system.track_progress(db, user_id, "hunt")
    if completed_quests:
        completed_alerts = "\n\n".join([f"🎉 **Quest Completed!** _{name}_" for name in completed_quests])
        if isinstance(event, Message):
            await event.answer(completed_alerts, parse_mode="Markdown")
        else:
            await event.message.answer(completed_alerts, parse_mode="Markdown")

    # Generate keyboard
    # Callback string format: catch_ball_<ball_type>_<monster_id>_<is_shiny>_<level>
    # Note: ball_type is basic, great, ultra, master
    m_id = encounter["monster_id"]
    shiny_flag = "1" if encounter["is_shiny"] else "0"
    lvl = encounter["level"]

    keyboard = get_catch_keyboard(f"{m_id}_{shiny_flag}_{lvl}", encounter["is_shiny"], balls_owned)

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        await event.answer()
    else:
        await event.answer(text, reply_markup=keyboard, parse_mode="Markdown")
