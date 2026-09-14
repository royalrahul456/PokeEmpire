from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
import config
from keyboards.inline import create_styled_button

router = Router()

def get_games_redirect_keyboard() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    games_username = getattr(config, "GAMES_BOT_USERNAME", "@PokeArenaBot").replace("@", "")
    builder.row(
        create_styled_button(
            text="🎮 Play Games on PokeArena",
            key="games",
            url=f"https://t.me/{games_username}?start=hub"
        )
    )
    return builder

@router.message(Command("games", "mines", "ttc", "xo", "slot", "spin", "rps", "scribble", "nameguess"))
async def cmd_redirect_games(message: Message):
    games_username = getattr(config, "GAMES_BOT_USERNAME", "@PokeArenaBot")
    redirect_text = (
        f"🎰 <b>Mini-Games have moved to PokeArena!</b> 🎰\n"
        f"◈ ────────────────────────── ◈\n"
        f"All mini-games (<i>Mines, Tic-Tac-Toe, Slots, Spin Wheel, RPS, Scribble, NameGuess</i>) are now played exclusively on <b>{games_username}</b>!\n\n"
        f"🏆 All coins and rewards won on PokeArena are synced directly to your account!\n\n"
        f"👇 <i>Click below to launch PokeArena:</i>"
    )
    kb = get_games_redirect_keyboard()
    await message.answer(redirect_text, reply_markup=kb.as_markup(), parse_mode="HTML")

@router.callback_query(F.data.in_({"dm_games", "btn_launch_mines", "btn_launch_xo", "btn_launch_slots", "btn_launch_spin"}))
async def cb_redirect_games(callback: CallbackQuery):
    await callback.answer()
    games_username = getattr(config, "GAMES_BOT_USERNAME", "@PokeArenaBot")
    redirect_text = (
        f"🎰 <b>Mini-Games have moved to PokeArena!</b> 🎰\n"
        f"◈ ────────────────────────── ◈\n"
        f"All mini-games are now played exclusively on <b>{games_username}</b>!\n\n"
        f"👇 <i>Click below to launch PokeArena:</i>"
    )
    kb = get_games_redirect_keyboard()
    await callback.message.answer(redirect_text, reply_markup=kb.as_markup(), parse_mode="HTML")
