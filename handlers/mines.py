import random
import math
import html
import json
import asyncio
from collections import defaultdict
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from database.models import User, ActiveMinesGame
from utils.trainer_level import log_transaction
import config

from keyboards.inline import create_styled_button, get_official_group_keyboard, GROUP_ONLY_GAMES_NOTICE

router = Router()

# In-memory store for active Mines games (backed by database for persistent cashout resilience)
# Key: user_id (int), Value: game state dict
active_mines_games = {}
user_locks = defaultdict(asyncio.Lock)

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
        builder.row(create_styled_button(
            text=f"🎁 Cashout ({curr_mult}x -> {win_amt:,}c)",
            key="claim",
            style="success",
            callback_data=f"mines_cash_{user_id}"
        ))
        
    return builder.as_markup()

async def get_or_load_game(user_id: int, db: AsyncSession) -> dict | None:
    """Gets game state from memory or recovers from persistent database."""
    if user_id in active_mines_games:
        return active_mines_games[user_id]
    
    stmt = select(ActiveMinesGame).where(ActiveMinesGame.user_id == user_id)
    res = await db.execute(stmt)
    db_game = res.scalar_one_or_none()
    
    if db_game and not db_game.ended:
        try:
            mines_set = set(json.loads(db_game.mines_json))
        except Exception:
            mines_set = set()
            
        try:
            revealed_set = set(json.loads(db_game.revealed_json))
        except Exception:
            revealed_set = set()
            
        game_state = {
            "bet": db_game.bet,
            "mines_count": db_game.mines_count,
            "mines": mines_set,
            "revealed": revealed_set,
            "ended": db_game.ended,
            "nickname": db_game.nickname or "Trainer",
            "chat_id": db_game.chat_id,
            "message_id": db_game.message_id
        }
        active_mines_games[user_id] = game_state
        return game_state
    return None

async def save_game_state(user_id: int, game_state: dict, db: AsyncSession, chat_id: int = None, message_id: int = None):
    """Saves game state to in-memory dictionary and database."""
    active_mines_games[user_id] = game_state
    
    mines_json = json.dumps(list(game_state["mines"]))
    revealed_json = json.dumps(list(game_state["revealed"]))
    
    stmt = select(ActiveMinesGame).where(ActiveMinesGame.user_id == user_id)
    res = await db.execute(stmt)
    db_game = res.scalar_one_or_none()
    
    if db_game:
        db_game.bet = game_state["bet"]
        db_game.mines_count = game_state["mines_count"]
        db_game.mines_json = mines_json
        db_game.revealed_json = revealed_json
        db_game.ended = game_state.get("ended", False)
        db_game.nickname = game_state.get("nickname", "Trainer")
        if chat_id:
            db_game.chat_id = chat_id
        if message_id:
            db_game.message_id = message_id
    else:
        db_game = ActiveMinesGame(
            user_id=user_id,
            chat_id=chat_id,
            message_id=message_id,
            bet=game_state["bet"],
            mines_count=game_state["mines_count"],
            mines_json=mines_json,
            revealed_json=revealed_json,
            ended=game_state.get("ended", False),
            nickname=game_state.get("nickname", "Trainer")
        )
        db.add(db_game)
    await db.commit()

async def delete_game_state(user_id: int, db: AsyncSession):
    """Deletes game state from in-memory dictionary and database."""
    active_mines_games.pop(user_id, None)
    stmt = delete(ActiveMinesGame).where(ActiveMinesGame.user_id == user_id)
    await db.execute(stmt)
    await db.commit()

@router.message(Command("mines", ignore_mention=True))
async def cmd_mines(message: Message, db: AsyncSession):
    if message.chat.type == "private":
        await message.answer(GROUP_ONLY_GAMES_NOTICE, reply_markup=get_official_group_keyboard(), parse_mode="HTML")
        return

    user_id = message.from_user.id
    async with user_locks[user_id]:
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
        existing_game = await get_or_load_game(user_id, db)
        if existing_game and not existing_game.get("ended", False):
            await message.answer("❌ You already have an active Mines game! Please finish it, cash out, or type /endmines first.")
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
        try:
            await log_transaction(user_id, -bet, "MINES_BET", f"Placed Mines bet ({mines_count} mines)", db)
        except Exception:
            pass
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
            "nickname": user.nickname or message.from_user.first_name or "Trainer"
        }
        
        text = (
            f"💣 <b>MINES GAME STARTED</b> 💣\n"
            f"<blockquote>👤 Trainer: <b>{html.escape(game_state['nickname'])}</b>\n"
            f"💰 Bet: <b>{bet:,} coins</b>\n"
            f"💣 Mines: <b>{mines_count} 💣</b>\n"
            f"📈 Multiplier: <b>1.0x</b></blockquote>\n"
            f"👉 Click on the tiles below to find diamonds! Avoid the mines!"
        )
        
        sent_msg = await message.answer(text, reply_markup=get_mines_keyboard(user_id, game_state), parse_mode="HTML")
        await save_game_state(user_id, game_state, db, chat_id=message.chat.id, message_id=sent_msg.message_id)

@router.callback_query(F.data.startswith("mines_rev_"))
async def cb_mines_reveal(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    user_id = int(parts[2])
    cell_idx = int(parts[3])
    
    if callback.from_user.id != user_id:
        await callback.answer("❌ This is not your game! Start your own with /mines.", show_alert=True)
        return

    async with user_locks[user_id]:
        game = await get_or_load_game(user_id, db)
        if not game or game.get("ended", False):
            await callback.answer("⚠️ Game has expired or already ended.", show_alert=True)
            return
            
        if cell_idx in game["revealed"]:
            await callback.answer("⚠️ That space is already revealed!", show_alert=True)
            return
            
        # Check if user hit a mine
        if cell_idx in game["mines"]:
            # Game Over!
            game["ended"] = True
            await delete_game_state(user_id, db)
            
            # Query user balance to display in game over
            stmt = select(User).where(User.id == user_id)
            res = await db.execute(stmt)
            user = res.scalar_one_or_none()
            bal = user.coins if user else 0
            
            text = (
                f"💥 <b>BOOM! GAME OVER</b> 💥\n"
                f"<blockquote>👤 Trainer: <b>{html.escape(game['nickname'])}</b>\n"
                f"💣 Hit Tile: <b>#{cell_idx + 1}</b>\n"
                f"💸 Lost Bet: <b>-{game['bet']:,} coins</b>\n"
                f"💰 New Balance: <b>💰 {bal:,} coins</b></blockquote>"
            )
            
            try:
                await callback.message.edit_text(text, reply_markup=get_mines_keyboard(user_id, game), parse_mode="HTML")
            except Exception:
                pass
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
        if revealed_count >= safe_tiles_total:
            # User won the maximum possible!
            game["ended"] = True
            win_amt = int(game["bet"] * multiplier)
            
            await delete_game_state(user_id, db)
            
            # Credit user
            stmt = select(User).where(User.id == user_id)
            res = await db.execute(stmt)
            user = res.scalar_one_or_none()
            if user:
                user.coins += win_amt
                try:
                    await log_transaction(user_id, win_amt, "MINES_WIN", f"Mines Max Win at {multiplier}x", db)
                except Exception:
                    pass
                await db.commit()
                bal = user.coins
            else:
                bal = win_amt
                
            text = (
                f"🏆 <b>MAXIMUM WIN!</b> 🏆\n"
                f"<blockquote>👤 Trainer: <b>{html.escape(game['nickname'])}</b>\n"
                f"🌟 Result: <b>Cleared all safe tiles!</b>\n"
                f"📈 Multiplier: <b>{multiplier}x</b>\n"
                f"💰 Earnings: <b>+{win_amt:,} coins</b>\n"
                f"💰 New Balance: <b>💰 {bal:,} coins</b></blockquote>"
            )
            
            try:
                await callback.message.edit_text(text, reply_markup=get_mines_keyboard(user_id, game), parse_mode="HTML")
            except Exception:
                pass
            await callback.answer("🏆 Maximum Win! Outstanding!", show_alert=True)
            return
     
        # Continue game
        await save_game_state(user_id, game, db)
        win_amt = int(game["bet"] * multiplier)
        text = (
            f"💣 <b>MINES GAME</b> 💣\n"
            f"<blockquote>👤 Trainer: <b>{html.escape(game['nickname'])}</b>\n"
            f"💰 Bet: <b>{game['bet']:,} coins</b>\n"
            f"💣 Mines: <b>{mines_count} 💣</b>\n"
            f"💎 Diamonds: <b>{revealed_count} 💎</b>\n"
            f"📈 Multiplier: <b>{multiplier}x</b>\n"
            f"💰 Potential Win: <b>{win_amt:,} coins</b></blockquote>\n"
            f"👉 Keep clicking or cash out!"
        )
        
        try:
            await callback.message.edit_text(text, reply_markup=get_mines_keyboard(user_id, game), parse_mode="HTML")
        except Exception:
            pass
        await callback.answer(f"Diamond #{revealed_count}! 💎 ({multiplier}x)")

@router.callback_query(F.data.startswith("mines_cash_"))
async def cb_mines_cashout(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    user_id = int(parts[2])
    
    if callback.from_user.id != user_id:
        await callback.answer("❌ This is not your game!", show_alert=True)
        return

    async with user_locks[user_id]:
        game = await get_or_load_game(user_id, db)
        if not game or game.get("ended", False):
            await callback.answer("⚠️ Game has expired or already ended.", show_alert=True)
            return

        revealed_count = len(game["revealed"])
        if revealed_count <= 0:
            await callback.answer("⚠️ You must reveal at least one diamond before cashing out!", show_alert=True)
            return

        game["ended"] = True
        multiplier = calculate_multiplier(game["mines_count"], revealed_count)
        win_amt = int(game["bet"] * multiplier)

        await delete_game_state(user_id, db)

        # Credit user
        stmt = select(User).where(User.id == user_id)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()
        if user:
            user.coins += win_amt
            try:
                await log_transaction(user_id, win_amt, "MINES_CASHOUT", f"Mines Cashout at {multiplier}x ({win_amt:,} coins)", db)
            except Exception:
                pass
            await db.commit()
            bal = user.coins
        else:
            bal = win_amt

        profit = win_amt - game["bet"]
        profit_str = f"+{profit:,}" if profit >= 0 else f"{profit:,}"

        text = (
            f"💰 <b>CASHOUT SUCCESSFUL!</b> 💰\n"
            f"<blockquote>👤 Trainer: <b>{html.escape(game['nickname'])}</b>\n"
            f"💎 Diamonds Found: <b>{revealed_count} 💎</b>\n"
            f"📈 Multiplier: <b>{multiplier}x</b>\n"
            f"💰 Earnings: <b>+{win_amt:,} coins</b> (Profit: <b>{profit_str} coins</b>)\n"
            f"💰 New Balance: <b>💰 {bal:,} coins</b></blockquote>"
        )

        try:
            await callback.message.edit_text(text, reply_markup=get_mines_keyboard(user_id, game), parse_mode="HTML")
        except Exception:
            pass
        await callback.answer(f"🎉 Cashed out +{win_amt:,} coins! 💰", show_alert=True)

@router.callback_query(F.data == "noop")
async def cb_noop(callback: CallbackQuery):
    await callback.answer()

@router.message(Command("endmines", ignore_mention=True))
async def cmd_endmines(message: Message, db: AsyncSession):
    user_id = message.from_user.id
    async with user_locks[user_id]:
        game = await get_or_load_game(user_id, db)
        if not game:
            await message.answer("❌ You do not have an active Mines game to end.")
            return
            
        await delete_game_state(user_id, db)
        await message.answer("🛑 <b>Your active Mines game has been terminated.</b>\n<i>Note: Since your bet was already placed, those coins are lost.</i>", parse_mode="HTML")
