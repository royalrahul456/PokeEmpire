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

def get_welcome_tab_keyboard(main_bot_username: str = None) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.row(
        create_styled_button(text="🎮 View All Mini-Games (Games Tab)", key="games", callback_data="btn_open_games_hub", style="primary")
    )
    builder.row(
        create_styled_button(text="💰 Balance & Wallet", key="profile", callback_data="btn_check_balance", style="success"),
        create_styled_button(text="🎡 Hourly Spin", key="games", callback_data="btn_launch_spin", style="success")
    )
    main_username = main_bot_username or getattr(config, "MAIN_BOT_USERNAME", "pokeempirebot")
    clean_username = main_username.replace("@", "")
    builder.row(
        create_styled_button(text="⚡ Back to Main Bot", key="back", url=f"https://t.me/{clean_username}", style="primary")
    )
    return builder

def get_games_hub_keyboard(main_bot_username: str = None) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    
    builder.row(
        create_styled_button(text="👤 Silhouette", key="games", callback_data="btn_launch_silhouette", style="primary"),
        create_styled_button(text="👁️ Unown Cipher", key="games", callback_data="btn_launch_unown", style="primary")
    )
    builder.row(
        create_styled_button(text="⚡ Voltorb Lock", key="games", callback_data="btn_launch_voltorb", style="danger"),
        create_styled_button(text="💣 Mines", key="games", callback_data="btn_launch_mines", style="danger")
    )
    builder.row(
        create_styled_button(text="❌ Tic-Tac-Toe", key="games", callback_data="btn_launch_xo", style="primary"),
        create_styled_button(text="🎡 Spin Wheel", key="games", callback_data="btn_launch_spin", style="success")
    )
    builder.row(
        create_styled_button(text="🎲 Dice Duel", key="games", callback_data="btn_launch_dice", style="primary"),
        create_styled_button(text="🎯 Darts", key="games", callback_data="btn_launch_darts", style="primary")
    )
    builder.row(
        create_styled_button(text="🏀 Basketball", key="games", callback_data="btn_launch_basket", style="primary"),
        create_styled_button(text="⚽ Football", key="games", callback_data="btn_launch_football", style="primary")
    )
    builder.row(
        create_styled_button(text="🎳 Bowling", key="games", callback_data="btn_launch_bowling", style="primary"),
        create_styled_button(text="✊ RPS", key="games", callback_data="btn_launch_rps", style="primary")
    )
    builder.row(
        create_styled_button(text="✏️ Scribble", key="games", callback_data="btn_launch_scribble", style="primary"),
        create_styled_button(text="💡 NameGuess", key="games", callback_data="btn_launch_nameguess", style="success")
    )
    builder.row(
        create_styled_button(text="💰 Balance", key="profile", callback_data="btn_check_balance", style="success"),
        create_styled_button(text="🔙 Welcome Menu", key="back", callback_data="btn_open_welcome_tab", style="primary")
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
    parts = message.text.split(maxsplit=1)
    arg = parts[1].strip().lower() if len(parts) > 1 else ""

    if arg == "mines":
        builder = InlineKeyboardBuilder()
        builder.row(create_styled_button(text="💣 Play Mines", key="games", callback_data="btn_launch_mines", style="danger"))
        builder.row(create_styled_button(text="🎰 Games Hub", key="games", callback_data="btn_open_games_hub", style="primary"))
        await message.answer(
            f"💣 <b>Mines Mini-Game</b>\n"
            f"◈ ────────────────────────── ◈\n"
            f"Navigate the minefield and cash out before detonating a bomb!\n\n"
            f"📌 <b>Format:</b> <code>/mines &lt;bet&gt; [mines_count]</code>\n"
            f"• Mines count: 1 to 24 (default: 3)\n"
            f"• Example: <code>/mines 500 3</code>\n\n"
            f"<i>Type the command above to start playing!</i>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        return

    if arg in ["spin", "wheel"]:
        builder = InlineKeyboardBuilder()
        builder.row(create_styled_button(text="🎡 Spin Fortune Wheel", key="games", callback_data="btn_launch_spin", style="success"))
        builder.row(create_styled_button(text="🎰 Games Hub", key="games", callback_data="btn_open_games_hub", style="primary"))
        await message.answer(
            f"🎡 <b>Hourly Fortune Wheel</b>\n"
            f"◈ ────────────────────────── ◈\n"
            f"Spin the fortune wheel once every hour for free coins!\n\n"
            f"📌 <b>Format:</b> <code>/spin</code>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        return

    if arg in ["ttc", "xo", "tictactoe"]:
        builder = InlineKeyboardBuilder()
        builder.row(create_styled_button(text="❌ Play Tic-Tac-Toe", key="games", callback_data="btn_launch_xo", style="primary"))
        builder.row(create_styled_button(text="🎰 Games Hub", key="games", callback_data="btn_open_games_hub", style="primary"))
        await message.answer(
            f"❌ <b>Tic-Tac-Toe (XO Duel)</b>\n"
            f"◈ ────────────────────────── ◈\n"
            f"Challenge an AI bot in DM or challenge players in group chats!\n\n"
            f"📌 <b>Format:</b> <code>/ttc &lt;bet&gt;</code>\n"
            f"• Example: <code>/ttc 200</code>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        return

    if arg in ["rps", "rockpaperscissors"]:
        builder = InlineKeyboardBuilder()
        builder.row(create_styled_button(text="✊ Play RPS", key="games", callback_data="btn_launch_rps", style="primary"))
        builder.row(create_styled_button(text="🎰 Games Hub", key="games", callback_data="btn_open_games_hub", style="primary"))
        await message.answer(
            f"✊ <b>Rock Paper Scissors</b>\n"
            f"◈ ────────────────────────── ◈\n"
            f"Play rock, paper, or scissors against the bot!\n\n"
            f"📌 <b>Format:</b> <code>/rps &lt;bet&gt; &lt;rock/paper/scissors&gt;</code>\n"
            f"• Example: <code>/rps 100 rock</code>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        return

    if arg in ["scribble", "unscramble"]:
        builder = InlineKeyboardBuilder()
        builder.row(create_styled_button(text="✏️ Start Scribble", key="games", callback_data="btn_launch_scribble", style="primary"))
        builder.row(create_styled_button(text="🎰 Games Hub", key="games", callback_data="btn_open_games_hub", style="primary"))
        await message.answer(
            f"✏️ <b>Scribble / Unscramble</b>\n"
            f"◈ ────────────────────────── ◈\n"
            f"Unscramble Pokémon names and guess fast for coin rewards!\n\n"
            f"📌 <b>Format:</b> <code>/scribble</code>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        return

    if arg in ["nameguess", "guess"]:
        builder = InlineKeyboardBuilder()
        builder.row(create_styled_button(text="💡 Start NameGuess", key="games", callback_data="btn_launch_nameguess", style="success"))
        builder.row(create_styled_button(text="🎰 Games Hub", key="games", callback_data="btn_open_games_hub", style="primary"))
        await message.answer(
            f"💡 <b>Pokémon NameGuess Quiz</b>\n"
            f"◈ ────────────────────────── ◈\n"
            f"Guess the hidden Pokémon name from hints!\n\n"
            f"📌 <b>Format:</b> <code>/nameguess</code>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        return

    if arg in ["dice", "roll"]:
        builder = InlineKeyboardBuilder()
        builder.row(create_styled_button(text="🎲 Roll Dice", key="games", callback_data="btn_launch_dice", style="primary"))
        builder.row(create_styled_button(text="🎰 Games Hub", key="games", callback_data="btn_open_games_hub", style="primary"))
        await message.answer(
            f"🎲 <b>Dice Duel vs AI</b>\n"
            f"◈ ────────────────────────── ◈\n"
            f"Roll a higher dice than the AI to win 2x your bet!\n\n"
            f"📌 <b>Format:</b> <code>/dice &lt;bet&gt;</code>\n"
            f"• Example: <code>/dice 500</code>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        return

    if arg in ["darts", "dart"]:
        builder = InlineKeyboardBuilder()
        builder.row(create_styled_button(text="🎯 Throw Dart", key="games", callback_data="btn_launch_darts", style="primary"))
        builder.row(create_styled_button(text="🎰 Games Hub", key="games", callback_data="btn_open_games_hub", style="primary"))
        await message.answer(
            f"🎯 <b>Darts Target Challenge</b>\n"
            f"◈ ────────────────────────── ◈\n"
            f"Hit the bullseye for 3x jackpot or inner rings for 1.5x!\n\n"
            f"📌 <b>Format:</b> <code>/darts &lt;bet&gt;</code>\n"
            f"• Example: <code>/darts 500</code>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        return

    if arg in ["basket", "basketball", "bb"]:
        builder = InlineKeyboardBuilder()
        builder.row(create_styled_button(text="🏀 Shoot Basket", key="games", callback_data="btn_launch_basket", style="primary"))
        builder.row(create_styled_button(text="🎰 Games Hub", key="games", callback_data="btn_open_games_hub", style="primary"))
        await message.answer(
            f"🏀 <b>Basketball Free Throw</b>\n"
            f"◈ ────────────────────────── ◈\n"
            f"Score a clean basket to win 2x your bet!\n\n"
            f"📌 <b>Format:</b> <code>/basketball &lt;bet&gt;</code>\n"
            f"• Example: <code>/basketball 500</code>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        return

    if arg in ["football", "soccer", "goal"]:
        builder = InlineKeyboardBuilder()
        builder.row(create_styled_button(text="⚽ Kick Penalty", key="games", callback_data="btn_launch_football", style="primary"))
        builder.row(create_styled_button(text="🎰 Games Hub", key="games", callback_data="btn_open_games_hub", style="primary"))
        await message.answer(
            f"⚽ <b>Football Penalty Shootout</b>\n"
            f"◈ ────────────────────────── ◈\n"
            f"Score a penalty goal past the keeper to win 1.8x your bet!\n\n"
            f"📌 <b>Format:</b> <code>/football &lt;bet&gt;</code>\n"
            f"• Example: <code>/football 500</code>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        return

    if arg in ["bowling", "bowl"]:
        builder = InlineKeyboardBuilder()
        builder.row(create_styled_button(text="🎳 Roll Bowling", key="games", callback_data="btn_launch_bowling", style="primary"))
        builder.row(create_styled_button(text="🎰 Games Hub", key="games", callback_data="btn_open_games_hub", style="primary"))
        await message.answer(
            f"🎳 <b>Bowling Strike Alley</b>\n"
            f"◈ ────────────────────────── ◈\n"
            f"Roll a STRIKE for 3.5x payout or SPARE for 1.5x!\n\n"
            f"📌 <b>Format:</b> <code>/bowling &lt;bet&gt;</code>\n"
            f"• Example: <code>/bowling 500</code>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        return

    if arg in ["coinflip", "cf", "flip"]:
        await message.answer(
            f"🪙 <b>Coinflip Duel</b>\n"
            f"◈ ────────────────────────── ◈\n"
            f"Pick heads or tails to double your bet!\n\n"
            f"📌 <b>Format:</b> <code>/coinflip &lt;bet&gt; &lt;heads/tails&gt;</code>\n"
            f"• Example: <code>/coinflip 500 heads</code>",
            parse_mode="HTML"
        )
        return

    if arg in ["balance", "bal", "wallet"]:
        await cmd_balance(message, db)
        return

    if arg in ["silhouette", "whothat", "shadow"]:
        builder = InlineKeyboardBuilder()
        builder.row(create_styled_button(text="👤 Start Silhouette Trial", key="games", callback_data="btn_launch_silhouette", style="primary"))
        builder.row(create_styled_button(text="🎰 Games Hub", key="games", callback_data="btn_open_games_hub", style="primary"))
        await message.answer(
            f"👤 <b>The Silhouette Trial</b>\n"
            f"◈ ────────────────────────── ◈\n"
            f"Prof. Oak & Silph Co. field simulation! Identify Pokémon by shadow outline.\n\n"
            f"📌 <b>Format:</b> <code>/whothat</code> or <code>/silhouette</code>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        return

    if arg in ["unown", "wordguess", "cipher"]:
        builder = InlineKeyboardBuilder()
        builder.row(create_styled_button(text="👁️ Start Unown Cipher", key="games", callback_data="btn_launch_unown", style="primary"))
        builder.row(create_styled_button(text="🎰 Games Hub", key="games", callback_data="btn_open_games_hub", style="primary"))
        await message.answer(
            f"👁️ <b>The Unown Cipher Matrix</b>\n"
            f"◈ ────────────────────────── ◈\n"
            f"Decipher mysterious 3, 4, or 5-letter ancient inscriptions from the Ruins of Alph!\n\n"
            f"📌 <b>Format:</b> <code>/unown</code> or <code>/cipher</code>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        return

    if arg in ["voltorb", "numguess", "vault"]:
        builder = InlineKeyboardBuilder()
        builder.row(create_styled_button(text="⚡ Start Voltorb Lock", key="games", callback_data="btn_launch_voltorb", style="danger"))
        builder.row(create_styled_button(text="🎰 Games Hub", key="games", callback_data="btn_open_games_hub", style="primary"))
        await message.answer(
            f"⚡ <b>The Voltorb Lock & Key</b>\n"
            f"◈ ────────────────────────── ◈\n"
            f"Hack the Power Plant security PIN (1–50) in 6 attempts before Voltorb self-destructs!\n\n"
            f"📌 <b>Format:</b> <code>/voltorb</code> or <code>/numguess</code>",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        return

    user_id = message.from_user.id
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    
    if not user:
        user = User(id=user_id, username=message.from_user.username, nickname=message.from_user.first_name or "Trainer", coins=1000, gems=10)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    level = getattr(user, 'trainer_level', 1) or 1
    title = get_trainer_title(level)

    welcome_text = (
        f"🎮 <b>Welcome to PokeArena!</b> 🎮\n"
        f"◈ ────────────────────────── ◈\n"
        f"👤 Trainer: <b>{user_name}</b> (<code>{user_id}</code>)\n"
        f"⭐ Level: <b>{level} ({title})</b>\n\n"
        f"💰 <b>Coins:</b> <code>{user.coins:,}</code> 🪙\n"
        f"💎 <b>Gems:</b> <code>{getattr(user, 'gems', 0):,}</code> 💎\n"
        f"◈ ────────────────────────── ◈\n"
        f"<i>All coins, gems, and rewards won here are synced to your main account in real-time.</i>\n\n"
        f"👇 <b>Select a tab below to begin:</b>"
    )
    kb = get_welcome_tab_keyboard(getattr(config, "MAIN_BOT_USERNAME", None))
    await message.answer(welcome_text, reply_markup=kb.as_markup(), parse_mode="HTML")

@router.message(Command("games"))
async def cmd_games_hub(message: Message):
    hub_text = (
        f"🎰 <b>PokeArena — Mini-Games Tab</b> 🎰\n"
        f"◈ ────────────────────────── ◈\n"
        f"Select a mini-game below to play and win coins & gems:"
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
        f"🎰 <b>PokeArena — Mini-Games Tab</b> 🎰\n"
        f"◈ ────────────────────────── ◈\n"
        f"Select a mini-game below to play:"
    )
    kb = get_games_hub_keyboard(getattr(config, "MAIN_BOT_USERNAME", None))
    try:
        await callback.message.edit_text(hub_text, reply_markup=kb.as_markup(), parse_mode="HTML")
    except Exception:
        await callback.message.answer(hub_text, reply_markup=kb.as_markup(), parse_mode="HTML")

@router.callback_query(F.data == "btn_open_welcome_tab")
async def cb_open_welcome_tab(callback: CallbackQuery, db: AsyncSession):
    await callback.answer()
    user_id = callback.from_user.id
    user_name = html.escape(callback.from_user.first_name or "Trainer")
    
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    
    if not user:
        user = User(id=user_id, username=callback.from_user.username, nickname=callback.from_user.first_name or "Trainer", coins=1000, gems=10)
        db.add(user)
        await db.commit()
        await db.refresh(user)

    level = getattr(user, 'trainer_level', 1) or 1
    title = get_trainer_title(level)

    welcome_text = (
        f"🎮 <b>Welcome to PokeArena!</b> 🎮\n"
        f"◈ ────────────────────────── ◈\n"
        f"👤 Trainer: <b>{user_name}</b> (<code>{user_id}</code>)\n"
        f"⭐ Level: <b>{level} ({title})</b>\n\n"
        f"💰 <b>Coins:</b> <code>{user.coins:,}</code> 🪙\n"
        f"💎 <b>Gems:</b> <code>{getattr(user, 'gems', 0):,}</code> 💎\n"
        f"◈ ────────────────────────── ◈\n"
        f"<i>All coins, gems, and rewards won here are synced to your main account in real-time.</i>\n\n"
        f"👇 <b>Select a tab below to begin:</b>"
    )
    kb = get_welcome_tab_keyboard(getattr(config, "MAIN_BOT_USERNAME", None))
    try:
        await callback.message.edit_text(welcome_text, reply_markup=kb.as_markup(), parse_mode="HTML")
    except Exception:
        await callback.message.answer(welcome_text, reply_markup=kb.as_markup(), parse_mode="HTML")

@router.message(Command("help"))
async def cmd_games_help(message: Message):
    help_text = (
        f"📖 <b>PokeArena Games Guide & Rules</b> 📖\n"
        f"◈ ────────────────────────── ◈\n"
        f"• 👤 <b>Silhouette:</b> <code>/whothat</code> - Identify Pokémon shadow outline.\n"
        f"• 👁️ <b>Unown Cipher:</b> <code>/unown</code> - Decrypt ancient 3/4/5-letter word cipher.\n"
        f"• ⚡ <b>Voltorb Lock:</b> <code>/voltorb</code> - Hack 1–50 security PIN in 6 attempts.\n"
        f"• 💣 <b>Mines:</b> <code>/mines &lt;bet&gt; [count]</code> - Pick safe tiles before detonating.\n"
        f"• ❌ <b>Tic-Tac-Toe:</b> <code>/ttc &lt;bet&gt;</code> - 3x3 duel against AI or players.\n"
        f"• 🎡 <b>Spin Wheel:</b> <code>/spin</code> - Hourly free spin for coins & gems.\n"
        f"• 🎲 <b>Dice Duel:</b> <code>/dice &lt;bet&gt;</code> - Roll higher than AI to win 2x.\n"
        f"• 🎯 <b>Darts:</b> <code>/darts &lt;bet&gt;</code> - Hit Bullseye for 3x or inner ring for 1.5x.\n"
        f"• 🏀 <b>Basketball:</b> <code>/basketball &lt;bet&gt;</code> - Score clean basket for 2x.\n"
        f"• ⚽ <b>Football:</b> <code>/football &lt;bet&gt;</code> - Score penalty past keeper for 1.8x.\n"
        f"• 🎳 <b>Bowling:</b> <code>/bowling &lt;bet&gt;</code> - Roll STRIKE for 3.5x or SPARE for 1.5x.\n"
        f"• 🪙 <b>Coinflip:</b> <code>/coinflip &lt;bet&gt; &lt;h/t&gt;</code> - 50/50 flip to double your bet.\n"
        f"• ✊ <b>RPS:</b> <code>/rps &lt;bet&gt; &lt;rock/paper/scissors&gt;</code> - Rock Paper Scissors.\n"
        f"• ✏️ <b>Scribble:</b> <code>/scribble</code> - Unscramble Pokémon names in groups.\n"
        f"• 💡 <b>NameGuess:</b> <code>/nameguess</code> - Identify Pokémon from anagrams.\n"
        f"• 💰 <b>Balance:</b> <code>/balance</code> - Check your synchronized wallet."
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

@router.callback_query(F.data == "btn_launch_spin")
async def cb_launch_spin(callback: CallbackQuery, db: AsyncSession):
    await callback.answer()
    from handlers.games import cmd_spin
    await cmd_spin(callback.message, db)

@router.callback_query(F.data == "btn_launch_dice")
async def cb_launch_dice(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "🎲 <b>Dice Duel:</b>\nType <code>/dice &lt;bet_amount&gt;</code> to roll vs AI!\nExample: <code>/dice 500</code>",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "btn_launch_darts")
async def cb_launch_darts(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "🎯 <b>Darts Target:</b>\nType <code>/darts &lt;bet_amount&gt;</code> to throw a dart!\nExample: <code>/darts 500</code>",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "btn_launch_basket")
async def cb_launch_basket(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "🏀 <b>Basketball Free Throw:</b>\nType <code>/basketball &lt;bet_amount&gt;</code> to shoot!\nExample: <code>/basketball 500</code>",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "btn_launch_football")
async def cb_launch_football(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "⚽ <b>Football Penalty:</b>\nType <code>/football &lt;bet_amount&gt;</code> to kick a penalty!\nExample: <code>/football 500</code>",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "btn_launch_bowling")
async def cb_launch_bowling(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "🎳 <b>Bowling Alley:</b>\nType <code>/bowling &lt;bet_amount&gt;</code> to roll for a strike!\nExample: <code>/bowling 500</code>",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "btn_launch_rps")
async def cb_launch_rps(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer(
        "✊ <b>Rock Paper Scissors:</b>\nType <code>/rps &lt;bet_amount&gt; &lt;rock/paper/scissors&gt;</code> to play!\nExample: <code>/rps 100 rock</code>",
        parse_mode="HTML"
    )

@router.callback_query(F.data == "btn_launch_scribble")
async def cb_launch_scribble(callback: CallbackQuery, db: AsyncSession):
    await callback.answer()
    from handlers.games import cmd_scribble
    await cmd_scribble(callback.message, db)

@router.callback_query(F.data == "btn_launch_nameguess")
async def cb_launch_nameguess(callback: CallbackQuery, db: AsyncSession):
    await callback.answer()
    from handlers.games import cmd_nameguess
    await cmd_nameguess(callback.message, db)

@router.callback_query(F.data == "btn_launch_silhouette")
async def cb_launch_silhouette(callback: CallbackQuery, db: AsyncSession):
    await callback.answer()
    from handlers.games import cmd_silhouette
    await cmd_silhouette(callback.message, db)

@router.callback_query(F.data == "btn_launch_unown")
async def cb_launch_unown(callback: CallbackQuery, db: AsyncSession):
    await callback.answer()
    from handlers.games import cmd_unown
    await cmd_unown(callback.message, db)

@router.callback_query(F.data == "btn_launch_voltorb")
async def cb_launch_voltorb(callback: CallbackQuery, db: AsyncSession):
    await callback.answer()
    from handlers.games import cmd_voltorb
    await cmd_voltorb(callback.message, db)
