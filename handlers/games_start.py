from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import config
import html
from database.models import User
from utils.trainer_level import get_trainer_title, get_xp_required_for_next_level
from keyboards.inline import create_styled_button

router = Router()

def get_games_hub_keyboard(main_bot_username: str = None) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    
    builder.row(
        create_styled_button(text="💣 Mines Game", key="games", callback_data="btn_launch_mines", style="danger"),
        create_styled_button(text="❌ Tic-Tac-Toe", key="games", callback_data="btn_launch_xo", style="primary")
    )
    builder.row(
        create_styled_button(text="🎰 Slots Casino", key="games", callback_data="btn_launch_slots", style="primary"),
        create_styled_button(text="🎡 Spin Wheel", key="games", callback_data="btn_launch_spin", style="success")
    )
    builder.row(
        create_styled_button(text="✊ Rock Paper Scissors", key="games", callback_data="btn_launch_rps", style="primary"),
        create_styled_button(text="✏️ Scribble", key="games", callback_data="btn_launch_scribble", style="primary")
    )
    builder.row(
        create_styled_button(text="💡 NameGuess", key="games", callback_data="btn_launch_nameguess", style="success"),
        create_styled_button(text="💰 Balance", key="profile", callback_data="btn_check_balance", style="success")
    )

    main_username = main_bot_username or getattr(config, "MAIN_BOT_USERNAME", "pokeempirebot")
    clean_username = main_username.replace("@", "")
    builder.row(
        create_styled_button(text="⚡ Back to Main Bot", key="back", url=f"https://t.me/{clean_username}", style="primary")
    )
        
    return builder

@router.message(CommandStart())
async def cmd_games_start(message: Message, db: AsyncSession):
    user_name = html.escape(message.from_user.first_name or "Trainer")
    welcome_text = (
        f"🎮 <b>Welcome to PokeArena Games Center!</b> 🎮\n"
        f"◈ ────────────────────────── ◈\n"
        f"Hello <b>{user_name}</b>! 👋\n\n"
        f"This is <b>PokeArena</b>, the official dedicated Mini-Games Bot for PokeEmpire.\n"
        f"All 🪙 <b>Coins</b>, 💎 <b>Gems</b>, and 🏆 <b>Rewards</b> won here are directly synced to your main account in real-time!\n\n"
        f"🎲 <b>Featured Mini-Games:</b>\n"
        f"• 💣 <code>/mines &lt;bet&gt;</code> - Minefield Multiplier\n"
        f"• ❌ <code>/ttc &lt;bet&gt;</code> - Tic-Tac-Toe PvP Duel\n"
        f"• 🎰 <code>/slot &lt;bet&gt;</code> - Slot Machine Casino\n"
        f"• 🎡 <code>/spin</code> - Free Hourly Fortune Wheel\n"
        f"• ✊ <code>/rps &lt;bet&gt;</code> - Rock Paper Scissors\n"
        f"• ✏️ <code>/scribble</code> - Group Drawing & Guessing\n"
        f"• 💡 <code>/nameguess</code> - Pokémon Name Quiz\n\n"
        f"💰 Type <code>/balance</code> to view your balance.\n\n"
        f"👇 <i>Select a game below to begin playing:</i>"
    )
    kb = get_games_hub_keyboard(getattr(config, "MAIN_BOT_USERNAME", None))
    await message.answer(welcome_text, reply_markup=kb.as_markup(), parse_mode="HTML")

@router.message(Command("games"))
async def cmd_games_hub(message: Message):
    hub_text = (
        f"🎰 <b>PokeArena Games Hub</b> 🎰\n"
        f"◈ ────────────────────────── ◈\n"
        f"Choose a mini-game to play and win coins & gems!"
    )
    kb = get_games_hub_keyboard(getattr(config, "MAIN_BOT_USERNAME", None))
    await message.answer(hub_text, reply_markup=kb.as_markup(), parse_mode="HTML")

@router.message(Command("balance", "bal"))
async def cmd_balance(message: Message, db: AsyncSession):
    user_id = message.from_user.id
    user_name = html.escape(message.from_user.first_name or "Trainer")
    
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    
    if not user:
        user = User(id=user_id, username=message.from_user.username, coins=1000, gems=10)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    level = user.trainer_level or 1
    title = get_trainer_title(level)

    bal_text = (
        f"💳 <b>Trainer Balance & Wallet</b> 💳\n"
        f"◈ ────────────────────────── ◈\n"
        f"👤 Trainer: <b>{user_name}</b> (<code>{user_id}</code>)\n"
        f"⭐ Level: <b>{level} ({title})</b>\n\n"
        f"💰 <b>Coins:</b> <code>{user.coins:,}</code> 🪙\n"
        f"💎 <b>Gems:</b> <code>{user.gems:,}</code> 💎\n"
        f"◈ ────────────────────────── ◈\n"
        f"<i>All earnings are instantly usable across PokeEmpire & PokeArena!</i>"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(
        create_styled_button(text="🎰 Games Hub", key="games", callback_data="btn_open_games_hub", style="primary"),
        create_styled_button(text="🎡 Hourly Spin", key="games", callback_data="btn_launch_spin", style="success")
    )
    await message.answer(bal_text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data == "btn_check_balance")
async def cb_check_balance(callback: CallbackQuery, db: AsyncSession):
    await callback.answer()
    user_id = callback.from_user.id
    user_name = html.escape(callback.from_user.first_name or "Trainer")
    
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    
    if not user:
        user = User(id=user_id, username=callback.from_user.username, coins=1000, gems=10)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    level = user.trainer_level or 1
    title = get_trainer_title(level)

    bal_text = (
        f"💳 <b>Trainer Balance & Wallet</b> 💳\n"
        f"◈ ────────────────────────── ◈\n"
        f"👤 Trainer: <b>{user_name}</b>\n"
        f"⭐ Level: <b>{level} ({title})</b>\n\n"
        f"💰 <b>Coins:</b> <code>{user.coins:,}</code> 🪙\n"
        f"💎 <b>Gems:</b> <code>{user.gems:,}</code> 💎\n"
        f"◈ ────────────────────────── ◈\n"
        f"<i>All earnings are instantly usable across PokeEmpire & PokeArena!</i>"
    )
    builder = InlineKeyboardBuilder()
    builder.row(
        create_styled_button(text="🎰 Games Hub", key="games", callback_data="btn_open_games_hub", style="primary")
    )
    await callback.message.answer(bal_text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data == "btn_open_games_hub")
async def cb_open_games_hub(callback: CallbackQuery):
    await callback.answer()
    hub_text = (
        f"🎰 <b>PokeArena Games Hub</b> 🎰\n"
        f"◈ ────────────────────────── ◈\n"
        f"Choose a mini-game to play and win coins & gems!"
    )
    kb = get_games_hub_keyboard(getattr(config, "MAIN_BOT_USERNAME", None))
    await callback.message.answer(hub_text, reply_markup=kb.as_markup(), parse_mode="HTML")

@router.message(Command("help"))
async def cmd_games_help(message: Message):
    help_text = (
        f"📖 <b>PokeArena Games Guide & Rules</b> 📖\n"
        f"◈ ────────────────────────── ◈\n"
        f"• 💣 <b>Mines:</b> <code>/mines &lt;bet&gt;</code> - Pick safe tiles to increase multiplier. Cash out before hitting a mine!\n"
        f"• ❌ <b>Tic-Tac-Toe:</b> <code>/ttc &lt;bet&gt;</code> - Challenge another player to a 3x3 duel.\n"
        f"• 🎰 <b>Slots:</b> <code>/slot &lt;bet&gt;</code> - Match 3 icons for jackpot multipliers up to 10x.\n"
        f"• 🎡 <b>Spin Wheel:</b> <code>/spin</code> - Free spin every hour for coins & gems.\n"
        f"• ✊ <b>RPS:</b> <code>/rps &lt;bet&gt;</code> - Classic Rock Paper Scissors vs players.\n"
        f"• ✏️ <b>Scribble:</b> <code>/scribble</code> - Group drawing game. Guess drawn words for coins!\n"
        f"• 💡 <b>NameGuess:</b> <code>/nameguess</code> - Identify Pokémon names from anagrams."
    )
    kb = get_games_hub_keyboard(getattr(config, "MAIN_BOT_USERNAME", None))
    await message.answer(help_text, reply_markup=kb.as_markup(), parse_mode="HTML")

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
