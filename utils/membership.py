import time
import config
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from typing import Callable, Dict, Any, Awaitable

# In-memory cache to prevent hitting Telegram API limits on every message
# user_id -> (is_member: bool, timestamp: float)
membership_cache = {}

async def check_membership(bot, user_id: int, force_refresh: bool = False) -> bool:
    """
    Checks if a user is a member of the official group (@pokeempireunion)
    with a 5-minute in-memory cache.
    """
    if user_id in config.ADMIN_IDS:
        return True

    now = time.time()
    # Check cache if not forced to refresh
    if not force_refresh and user_id in membership_cache:
        cached_val, cached_time = membership_cache[user_id]
        # Cache True (member) for 5 minutes, False (non-member) for 15 seconds
        cache_duration = 300 if cached_val else 15
        if now - cached_time < cache_duration:
            return cached_val

    is_member = False
    # Check group chat membership
    try:
        chat_member = await bot.get_chat_member(chat_id="@pokeempireunion", user_id=user_id)
        if chat_member.status not in ["left", "kicked"]:
            is_member = True
    except Exception as e:
        print(f"Error checking group membership for {user_id}: {e}")
        is_member = False

    # Cache the result
    membership_cache[user_id] = (is_member, now)
    return is_member

def get_join_keyboard() -> InlineKeyboardMarkup:
    """
    Generates inline keyboard markup with link to the official group chat and a Verify button.
    """
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👥 Join Group Chat", url="https://t.me/pokeempireunion")
        ],
        [
            InlineKeyboardButton(text="🔄 Verify Membership", callback_data="verify_membership")
        ]
    ])
    return keyboard

class MembershipMiddleware(BaseMiddleware):
    """
    Middleware that enforces membership in the official group chat.
    """
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any]
    ) -> Any:
        bot = data.get("bot")
        user = None
        is_callback = isinstance(event, CallbackQuery)
        is_message = isinstance(event, Message)
        
        if is_message:
            user = event.from_user
            chat = event.chat
        elif is_callback:
            user = event.from_user
            chat = event.message.chat if event.message else None
            
        if not user or user.is_bot:
            return await handler(event, data)
            
        # Bypass for admin
        if user.id in config.ADMIN_IDS:
            return await handler(event, data)
            
        # Determine if we should check membership:
        # In DMs (private chats): check everything except the verification callback.
        # In Groups: only check if it is a bot command (starts with /) or callback.
        should_check = False
        if chat and chat.type == "private":
            if is_callback and event.data == "verify_membership":
                return await handler(event, data)
            # Allow /start command to go through so that it can guide them to verify
            if is_message and event.text and event.text.split()[0].lower() in ["/start"]:
                return await handler(event, data)
            should_check = True
        else:
            # In groups, check if message is a command
            if is_message and event.text and event.text.startswith("/"):
                should_check = True
            elif is_callback:
                should_check = True
                
        if should_check:
            is_member = await check_membership(bot, user.id)
            if not is_member:
                # Redirect or reply
                if is_callback:
                    await event.answer("⚠️ Access Denied! You must join our official Group Chat.", show_alert=True)
                    if chat and chat.type == "private":
                        try:
                            await event.message.edit_text(
                                "🚫 <b>ACCESS DENIED!</b> 🚫\n\n"
                                "<blockquote>You must be a member of our official Group Chat to interact with the bot.</blockquote>",
                                parse_mode="HTML",
                                reply_markup=get_join_keyboard()
                            )
                        except Exception:
                            pass
                    return
                else:
                    # Message
                    if chat and chat.type == "private":
                        await event.answer(
                            "🚫 <b>ACCESS DENIED!</b> 🚫\n\n"
                            "<blockquote>You must be a member of our official Group Chat to interact with the bot.</blockquote>",
                            parse_mode="HTML",
                            reply_markup=get_join_keyboard()
                        )
                    else:
                        # Group command
                        await event.reply(
                            "🚫 <b>ACCESS DENIED!</b> 🚫\n"
                            "<blockquote>You must join our official Group Chat (@pokeempireunion) to use bot commands!</blockquote>",
                            parse_mode="HTML"
                        )
                    return
                    
        return await handler(event, data)
