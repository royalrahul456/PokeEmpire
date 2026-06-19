from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from services.spawn_service import SpawnService
from utils.cooldowns import cooldowns

router = Router()

@router.message(Command("hunt"))
async def cmd_hunt(message: Message, db: AsyncSession):
    # Hunt is only allowed in DMs (private chats)
    if message.chat.type != "private":
        await message.answer("⚠️ The `/hunt` command can only be used in private DMs with the bot.", parse_mode="Markdown")
        return

    user_id = message.from_user.id
    
    # Enforce 30-second cooldown
    allowed, seconds_left = cooldowns.trigger_action(user_id, "hunt", 30)
    if not allowed:
        await message.answer(f"⏳ **Your radar is recharging!** You can hunt again in **{seconds_left}s**.", parse_mode="Markdown")
        return

    # Trigger wild spawn in DM (chat_id = user_id)
    success = await SpawnService.trigger_spawn(db, user_id, message.bot)
    if not success:
        # Clear cooldown so they don't get penalized on failure
        cooldowns.clear_cooldown(user_id, "hunt")
        await message.answer("❌ **Error:** Failed to start a wild encounter. Please try again later.", parse_mode="Markdown")
