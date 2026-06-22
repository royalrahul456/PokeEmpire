import random
import math
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import User
import config
from utils.formatters import escape_md

router = Router()

# In-memory store for active Mines games
# Key: user_id (int), Value: game state dict
active_mines_games = {}

def calculate_multiplier(mines_count: int, revealed_count: int) -> float:
    """Calculates the win multiplier using combinatorics with a 4% house edge."""
    if revealed_count <= 0:
        return 1.0
    
    # Calculate combination: nCr = n! / (r! * (n-r)!)
    def nCr(n, r):
        if r < 0 or r > n:
            return 0
        return math.comb(n, r)
    
    total_ways = nCr(25, revealed_count)
    safe_ways = nCr(25 - mines_count, revealed_count)
    
    if safe_ways == 0 or total_ways == 0:
        return 0.0
        
    prob = safe_ways / total_ways
    # Multiplier with a 4% house edge (96% return to player)
    mult = 0.96 / prob
    return round(mult, 2)

def get_mines_keyboard(user_id: int, game: dict) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    mines = game["mines"]
    revealed = game["revealed"]
    ended = game["ended"]
    
    for i in range(25):
        if ended:
            if i in mines:
                # Show mine
                builder.button(text="💣", callback_data="noop")
            elif i in revealed:
                # Show revealed diamond
                builder.button(text="💎", callback_data="noop")
            else:
                # Show safe unrevealed
                builder.button(text="🟢", callback_data="noop")
        else:
            if i in revealed:
                # Show revealed diamond
                builder.button(text="💎", callback_data="noop")
            else:
                # Clickable unrevealed
                builder.button(text="❓", callback_data=f"mines_rev_{user_id}_{i}")
                
    builder.adjust(5)
    
    if not ended and len(revealed) > 0:
        curr_mult = calculate_multiplier(game["mines_count"], len(revealed))
        win_amt = int(game["bet"] * curr_mult)
        builder.row(InlineKeyboardButton(
            text=f"💰 Cashout ({curr_mult}x -> {win_amt}c)",
            callback_data=f"mines_cash_{user_id}"
        ))
        
    return builder.as_markup()

@router.message(Command("mines"))
async def cmd_mines(message: Message, db: AsyncSession):
    user_id = message.from_user.id
    parts = message.text.split()
    
    if len(parts) < 2:
        await message.answer(
            "⚠️ <b>Mines Format:</b> <code>/mines &lt;bet&gt; [mines_count]</code>\n"
            "• Mines count must be between 1 and 24 (default is 3).\n"
            "• E.g. <code>/mines 100 3</code>",
            parse_mode="HTML"
        )
        return
        
    # Parse bet
    bet_str = parts[1]
    if not bet_str.isdigit():
        await message.answer("❌ Bet amount must be a valid number.")
        return
    bet = int(bet_str)
    
    if bet < 10 or bet > 100000:
        await message.answer("❌ Bet must be between 10 and 100,000 coins.")
        return
        
    # Parse mines count
    mines_count = 3
    if len(parts) >= 3:
        m_str = parts[2]
        if not m_str.isdigit():
            await message.answer("❌ Mines count must be a valid number.")
            return
        mines_count = int(m_str)
        if mines_count < 1 or mines_count > 24:
            await message.answer("❌ Mines count must be between 1 and 24.")
            return

    # Check if user already has an active game
    if user_id in active_mines_games:
        await message.answer("❌ You already have an active Mines game! Please finish it or cash out first.")
        return

    # Fetch User
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    
    if not user or user.coins < bet:
        await message.answer("❌ You don't have enough coins to place this bet!")
        return

    # Deduct bet coins immediately
    user.coins -= bet
    await db.commit()

    # Generate mines
    mines = set(random.sample(range(25), mines_count))
    
    # Save game state
    game_state = {
        "bet": bet,
        "mines_count": mines_count,
        "mines": mines,
        "revealed": set(),
        "ended": False,
        "nickname": user.nickname or message.from_user.first_name
    }
    active_mines_games[user_id] = game_state

    text = (
        f"💣 <b>MINES GAME STARTED</b> 💣\n"
        f"───────────────\n"
        f"Trainer: <b>{escape_md(game_state['nickname'])}</b>\n"
        f"Bet: <code>{bet} coins</code>\n"
        f"Mines: <code>{mines_count} 💣</code>\n"
        f"Multiplier: <code>1.0x</code>\n\n"
        f"👉 Click on the tiles below to find diamonds! Avoid the mines!"
    )
    
    await message.answer(text, reply_markup=get_mines_keyboard(user_id, game_state), parse_mode="HTML")

@router.callback_query(F.data.startswith("mines_rev_"))
async def cb_mines_reveal(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    user_id = int(parts[2])
    cell_idx = int(parts[3])
    
    if callback.from_user.id != user_id:
        await callback.answer("❌ This is not your game! Start your own with /mines.", show_alert=True)
        return
        
    if user_id not in active_mines_games:
        await callback.answer("⚠️ Game has expired or already ended.", show_alert=True)
        return
        
    game = active_mines_games[user_id]
    if game["ended"]:
        await callback.answer()
        return
        
    if cell_idx in game["revealed"]:
        await callback.answer("⚠️ That space is already revealed!", show_alert=True)
        return
        
    # Check if user hit a mine
    if cell_idx in game["mines"]:
        # Game Over!
        game["ended"] = True
        active_mines_games.pop(user_id, None)
        
        # Query user balance to display in game over
        stmt = select(User).where(User.id == user_id)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()
        bal = user.coins if user else 0
        
        text = (
            f"💥 <b>BOOM! GAME OVER</b> 💥\n"
            f"───────────────\n"
            f"You hit a mine at tile #{cell_idx + 1}!\n"
            f"You lost your bet of <code>{game['bet']} coins</code>.\n\n"
            f"💰 New Balance: <code>{bal} coins</code>\n"
            f"───────────────"
        )
        
        await callback.message.edit_text(text, reply_markup=get_mines_keyboard(user_id, game), parse_mode="HTML")
        await callback.answer("Boom! Game Over 💀", show_alert=True)
        return
        
    # Reveal diamond
    game["revealed"].add(cell_idx)
    revealed_count = len(game["revealed"])
    mines_count = game["mines_count"]
    
    # Calculate new multiplier
    multiplier = calculate_multiplier(mines_count, revealed_count)
    
    # Check if they revealed all safe tiles
    safe_tiles_total = 25 - mines_count
    if revealed_count == safe_tiles_total:
        # User won the maximum possible!
        game["ended"] = True
        active_mines_games.pop(user_id, None)
        
        win_amt = int(game["bet"] * multiplier)
        
        # Credit user
        stmt = select(User).where(User.id == user_id)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()
        if user:
            user.coins += win_amt
            await db.commit()
            bal = user.coins
        else:
            bal = win_amt
            
        text = (
            f"🏆 <b>MAXIMUM WIN!</b> 🏆\n"
            f"───────────────\n"
            f"Amazing! You cleared all safe tiles!\n"
            f"Multiplier: <code>{multiplier}x</code>\n"
            f"Earnings: <code>+{win_amt} coins</code>\n\n"
            f"💰 New Balance: <code>{bal} coins</code>\n"
            f"───────────────"
        )
        
        await callback.message.edit_text(text, reply_markup=get_mines_keyboard(user_id, game), parse_mode="HTML")
        await callback.answer("🏆 Maximum Win! Outstanding!", show_alert=True)
        return

    # Continue game
    win_amt = int(game["bet"] * multiplier)
    text = (
        f"💣 <b>MINES GAME</b> 💣\n"
        f"───────────────\n"
        f"Trainer: <b>{escape_md(game['nickname'])}</b>\n"
        f"Bet: <code>{game['bet']} coins</code>\n"
        f"Mines: <code>{mines_count} 💣</code>\n"
        f"Diamonds: <code>{revealed_count} 💎</code>\n"
        f"Multiplier: <code>{multiplier}x</code>\n"
        f"Potential Win: <code>{win_amt} coins</code>\n\n"
        f"👉 Keep clicking or cash out!"
    )
    
    await callback.message.edit_text(text, reply_markup=get_mines_keyboard(user_id, game), parse_mode="HTML")
    await callback.answer("Found a diamond! 💎")

@router.callback_query(F.data.startswith("mines_cash_"))
async def cb_mines_cashout(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    user_id = int(parts[2])
    
    if callback.from_user.id != user_id:
        await callback.answer("❌ This is not your game!", show_alert=True)
        return
        
    if user_id not in active_mines_games:
        await callback.answer("⚠️ Game has expired or already ended.", show_alert=True)
        return
        
    game = active_mines_games.pop(user_id, None)
    if not game or game["ended"]:
        await callback.answer()
        return
        
    game["ended"] = True
    revealed_count = len(game["revealed"])
    
    # Calculate final winnings
    multiplier = calculate_multiplier(game["mines_count"], revealed_count)
    win_amt = int(game["bet"] * multiplier)
    
    # Credit user
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if user:
        user.coins += win_amt
        await db.commit()
        bal = user.coins
    else:
        bal = win_amt
        
    text = (
        f"💰 <b>CASHOUT SUCCESSFUL!</b> 💰\n"
        f"───────────────\n"
        f"You cashed out successfully!\n"
        f"Multiplier: <code>{multiplier}x</code>\n"
        f"Earnings: <code>+{win_amt} coins</code> (Profit: <code>+{win_amt - game['bet']} coins</code>)\n\n"
        f"💰 New Balance: <code>{bal} coins</code>\n"
        f"───────────────"
    )
    
    await callback.message.edit_text(text, reply_markup=get_mines_keyboard(user_id, game), parse_mode="HTML")
    await callback.answer(f"Cashed out +{win_amt} coins! 💰", show_alert=True)

@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    await callback.answer()
