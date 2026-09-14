from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
import config
from utils.formatters import escape_md
from keyboards.inline import create_styled_button

router = Router()

def get_games_hub_keyboard(main_bot_username: str = None) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    
    builder.row(
        create_styled_button(text="💣 Mines Game", key="games", callback_data="btn_launch_mines"),
        create_styled_button(text="❌ Tic-Tac-Toe", key="games", callback_data="btn_launch_xo")
    )
    builder.row(
        create_styled_button(text="🎰 Slots Casino", key="games", callback_data="btn_launch_slots"),
        create_styled_button(text="🎡 Spin Wheel", key="games", callback_data="btn_launch_spin")
    )
    builder.row(
        create_styled_button(text="✊ Rock Paper Scissors", key="games", callback_data="btn_launch_rps"),
        create_styled_button(text="✏️ Scribble", key="games", callback_data="btn_launch_scribble")
    )
    builder.row(
        create_styled_button(text="💡 NameGuess", key="games", callback_data="btn_launch_nameguess")
    )

    if main_bot_username:
        clean_username = main_bot_username.replace("@", "")
        builder.row(
            create_styled_button(text="⚡ Back to Main Bot", key="back", url=f"https://t.me/{clean_username}")
        )
        
    return builder

@router.message(CommandStart())
async def cmd_games_start(message: Message, db: AsyncSession):
    user_name = escape_md(message.from_user.first_name)
    welcome_text = (
        f"🎮 <b>Welcome to PokeArena Games Center!</b> 🎮\n"
        f"◈ ────────────────────────── ◈\n"
        f"Hello <b>{user_name}</b>!\n\n"
        f"This is <b>PokeArena</b>, the dedicated Mini-Games Bot for PokeEmpire.\n"
        f"All coins, rewards, and achievements won here are directly synced to your main account!\n\n"
        f"🎲 <b>Available Games:</b>\n"
        f"• 💣 <code>/mines</code> - Test your luck avoiding mines\n"
        f"• ❌ <code>/ttc &lt;bet&gt;</code> - Tic-Tac-Toe PvP Duel\n"
        f"• 🎰 <code>/slot &lt;bet&gt;</code> - Slot Machine Casino\n"
        f"• 🎡 <code>/spin</code> - Hourly Fortune Wheel\n"
        f"• ✊ <code>/rps &lt;bet&gt;</code> - Rock Paper Scissors\n"
        f"• ✏️ <code>/scribble</code> - Drawing & Guessing\n"
        f"• 💡 <code>/nameguess</code> - Pokémon Name Quiz\n\n"
        f"👇 <i>Select a game below to begin:</i>"
    )
    kb = get_games_hub_keyboard(getattr(config, "MAIN_BOT_USERNAME", None))
    await message.answer(welcome_text, reply_markup=kb.as_markup(), parse_mode="HTML")

@router.message(Command("games"))
async def cmd_games_hub(message: Message):
    user_name = escape_md(message.from_user.first_name)
    hub_text = (
        f"🎰 <b>PokeArena Games Hub</b> 🎰\n"
        f"◈ ────────────────────────── ◈\n"
        f"Choose a mini-game to play and win coins & rewards!"
    )
    kb = get_games_hub_keyboard(getattr(config, "MAIN_BOT_USERNAME", None))
    await message.answer(hub_text, reply_markup=kb.as_markup(), parse_mode="HTML")

@router.callback_query(F.data == "btn_launch_mines")
async def cb_launch_mines(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "💣 <b>Mines Game:</b>\nType <code>/mines &lt;bet_amount&gt;</code> to start a game!\nExample: <code>/mines 1000</code>",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "btn_launch_xo")
async def cb_launch_xo(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "❌ <b>Tic-Tac-Toe (XO):</b>\nType <code>/ttc &lt;bet_amount&gt;</code> in a group or reply to an opponent!",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "btn_launch_slots")
async def cb_launch_slots(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "🎰 <b>Slots Casino:</b>\nType <code>/slot &lt;bet_amount&gt;</code> to roll the reels!\nExample: <code>/slot 500</code>",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "btn_launch_spin")
async def cb_launch_spin(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "🎡 <b>Fortune Spin:</b>\nType <code>/spin</code> to spin the hourly wheel for rewards!",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "btn_launch_rps")
async def cb_launch_rps(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "✊ <b>Rock Paper Scissors:</b>\nType <code>/rps &lt;bet_amount&gt;</code> to challenge a player!",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "btn_launch_scribble")
async def cb_launch_scribble(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "✏️ <b>Scribble:</b>\nType <code>/scribble</code> to start a drawing game in your group!",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "btn_launch_nameguess")
async def cb_launch_nameguess(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "💡 <b>NameGuess Quiz:</b>\nType <code>/nameguess</code> to start guessing Pokémon names!",
        parse_mode="HTML"
    )
