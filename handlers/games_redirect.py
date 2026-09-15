from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
import config
from keyboards.inline import create_styled_button

router = Router()

def get_games_redirect_keyboard() -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    games_username = getattr(config, "GAMES_BOT_USERNAME", "@PokeXArenaBot").replace("@", "")
    builder.row(
        create_styled_button(
            text="🎮 Play Games on PokeArena",
            key="games",
            url=f"https://t.me/{games_username}?start=hub"
        )
    )
    return builder

@router.message(Command(
    "games", "minigames", "mines", "endmines", "ttc", "xo", "tictactoe", 
    "slot", "slots", "casino", "spin", "wheel", "rps", "rockpaperscissors", 
    "scribble", "nameguess", "guess", "coinflip", "cf", "flip", 
    "trivia", "dice", "roll", "darts", "dart", "basketball", "basket", "bb",
    "football", "soccer", "goal", "bowling", "bowl",
    "whothat", "silhouette", "shadow", "unown", "wordguess", "cipher",
    "voltorb", "numguess", "vault"
))
async def cmd_redirect_games(message: Message):
    games_username = getattr(config, "GAMES_BOT_USERNAME", "@PokeXArenaBot").replace("@", "")
    cmd = message.text.split()[0].replace("/", "").split("@")[0].lower() if message.text else "hub"
    
    arg_map = {
        "mines": "mines", "endmines": "mines",
        "slot": "slot", "slots": "slot", "casino": "slot",
        "spin": "spin", "wheel": "spin",
        "ttc": "ttc", "xo": "ttc", "tictactoe": "ttc",
        "rps": "rps", "rockpaperscissors": "rps",
        "scribble": "scribble", "unscramble": "scribble",
        "nameguess": "nameguess", "guess": "nameguess",
        "dice": "dice", "roll": "dice",
        "darts": "darts", "dart": "darts",
        "basketball": "basket", "basket": "basket", "bb": "basket",
        "football": "football", "soccer": "football", "goal": "football",
        "bowling": "bowling", "bowl": "bowling",
        "coinflip": "coinflip", "cf": "coinflip", "flip": "coinflip",
        "whothat": "silhouette", "silhouette": "silhouette", "shadow": "silhouette",
        "unown": "unown", "wordguess": "unown", "cipher": "unown",
        "voltorb": "voltorb", "numguess": "voltorb", "vault": "voltorb"
    }
    target_arg = arg_map.get(cmd, "hub")
    
    redirect_text = (
        f"🎰 <b>Mini-Games have moved to PokeArena!</b> 🎰\n"
        f"◈ ────────────────────────── ◈\n"
        f"All mini-games (<i>Mines, Tic-Tac-Toe, Slots, Silhouette, Unown Cipher, Voltorb Lock, Dice, Darts, Spin Wheel</i>) are now played on <b>@{games_username}</b>!\n\n"
        f"🏆 All coins and rewards won on PokeArena are synced directly to your account in real-time!\n\n"
        f"👇 <i>Click below to launch:</i>"
    )
    builder = InlineKeyboardBuilder()
    builder.row(
        create_styled_button(
            text="🎮 Play on PokeArena",
            key="games",
            url=f"https://t.me/{games_username}?start={target_arg}"
        )
    )
    await message.answer(redirect_text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data.in_({
    "dm_games", "play_daily", "play_spin", "play_trivia", "play_scribble", "play_mines",
    "btn_launch_mines", "btn_launch_xo", "btn_launch_slots", "btn_launch_spin", 
    "btn_launch_rps", "btn_launch_scribble", "btn_launch_nameguess", "btn_open_games_hub",
    "btn_launch_dice", "btn_launch_darts", "btn_launch_basket", "btn_launch_football",
    "btn_launch_bowling", "btn_launch_silhouette", "btn_launch_unown", "btn_launch_voltorb",
    "play_silhouette", "play_unown", "play_voltorb"
}))
async def cb_redirect_games(callback: CallbackQuery):
    await callback.answer()
    games_username = getattr(config, "GAMES_BOT_USERNAME", "@PokeXArenaBot").replace("@", "")
    
    cb_arg_map = {
        "play_mines": "mines", "btn_launch_mines": "mines",
        "btn_launch_slots": "slot",
        "play_spin": "spin", "btn_launch_spin": "spin",
        "btn_launch_xo": "ttc",
        "btn_launch_rps": "rps",
        "play_scribble": "scribble", "btn_launch_scribble": "scribble",
        "btn_launch_nameguess": "nameguess",
        "btn_launch_dice": "dice",
        "btn_launch_darts": "darts",
        "btn_launch_basket": "basket",
        "btn_launch_football": "football",
        "btn_launch_bowling": "bowling",
        "btn_launch_silhouette": "silhouette", "play_silhouette": "silhouette",
        "btn_launch_unown": "unown", "play_unown": "unown",
        "btn_launch_voltorb": "voltorb", "play_voltorb": "voltorb",
    }
    target_arg = cb_arg_map.get(callback.data, "hub")
    
    redirect_text = (
        f"🎰 <b>Mini-Games have moved to PokeArena!</b> 🎰\n"
        f"◈ ────────────────────────── ◈\n"
        f"All mini-games are now played on <b>@{games_username}</b>!\n\n"
        f"👇 <i>Click below to launch:</i>"
    )
    builder = InlineKeyboardBuilder()
    builder.row(
        create_styled_button(
            text="🎮 Launch Game on PokeArena",
            key="games",
            url=f"https://t.me/{games_username}?start={target_arg}"
        )
    )
    await callback.message.answer(redirect_text, reply_markup=builder.as_markup(), parse_mode="HTML")
