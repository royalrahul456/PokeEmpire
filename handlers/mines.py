import random
import math
import html
import json
import asyncio
import time
from datetime import datetime
from collections import defaultdict
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.exceptions import TelegramBadRequest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from database.models import User, ActiveMinesGame
from database.database import SessionLocal
from utils.trainer_level import log_transaction
import config

from keyboards.inline import create_styled_button, get_official_group_keyboard, GROUP_ONLY_GAMES_NOTICE

router = Router()

DAILY_MINES_LIMIT = 4
MINES_INACTIVITY_TIMEOUT = 120  # 120 seconds (2 minutes)

# In-memory store for active Mines games (backed by database for persistent cashout resilience)
# Key: user_id (int), Value: game state dict
active_mines_games = {}
user_locks = defaultdict(asyncio.Lock)
inactivity_tasks = {}  # user_id -> asyncio.Task

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
            "message_id": db_game.message_id,
            "last_activity": time.time()
        }
        active_mines_games[user_id] = game_state
        return game_state
    return None

async def save_game_state(user_id: int, game_state: dict, db: AsyncSession, chat_id: int = None, message_id: int = None):
    """Saves game state to in-memory dictionary and database."""
    game_state["last_activity"] = time.time()
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
        db_game.last_activity_at = datetime.utcnow()
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
            nickname=game_state.get("nickname", "Trainer"),
            last_activity_at=datetime.utcnow()
        )
        db.add(db_game)
    await db.commit()

async def delete_game_state(user_id: int, db: AsyncSession):
    """Deletes game state from in-memory dictionary and database."""
    active_mines_games.pop(user_id, None)
    if user_id in inactivity_tasks:
        inactivity_tasks[user_id].cancel()
        inactivity_tasks.pop(user_id, None)
    stmt = delete(ActiveMinesGame).where(ActiveMinesGame.user_id == user_id)
    await db.execute(stmt)
    await db.commit()

def reset_inactivity_timer(user_id: int, bot: Bot):
    """Schedules or resets the 120-second inactivity auto-end timer for a game."""
    if user_id in inactivity_tasks:
        inactivity_tasks[user_id].cancel()
        
    async def inactivity_watchdog():
        try:
            await asyncio.sleep(MINES_INACTIVITY_TIMEOUT)
            async with user_locks[user_id]:
                if user_id not in active_mines_games:
                    return
                game = active_mines_games.get(user_id)
                if not game or game.get("ended", False):
                    return
                    
                # Check if elapsed since last activity >= 120s
                last_act = game.get("last_activity", 0)
                elapsed = time.time() - last_act
                if elapsed < MINES_INACTIVITY_TIMEOUT - 1:
                    return

                game["ended"] = True
                chat_id = game.get("chat_id")
                message_id = game.get("message_id")
                revealed_count = len(game.get("revealed", set()))
                mines_count = game.get("mines_count", 3)
                bet = game.get("bet", 0)
                nickname = game.get("nickname", "Trainer")

                # Clean up game state from DB and memory
                async with SessionLocal() as session:
                    stmt = delete(ActiveMinesGame).where(ActiveMinesGame.user_id == user_id)
                    await session.execute(stmt)
                    
                    # Auto cashout if player had revealed at least 1 diamond
                    win_amt = 0
                    bal = 0
                    if revealed_count > 0:
                        mult = calculate_multiplier(mines_count, revealed_count)
                        win_amt = int(bet * mult)
                        u_stmt = select(User).where(User.id == user_id)
                        u_res = await session.execute(u_stmt)
                        db_user = u_res.scalar_one_or_none()
                        if db_user:
                            db_user.coins += win_amt
                            try:
                                await log_transaction(user_id, win_amt, "MINES_TIMEOUT_CASHOUT", f"Mines Inactivity Auto-Cashout ({win_amt:,} coins)", session)
                            except Exception:
                                pass
                            bal = db_user.coins
                    await session.commit()

                active_mines_games.pop(user_id, None)

                # Edit game message to notify expiration
                if chat_id and message_id:
                    if revealed_count > 0:
                        timeout_text = (
                            f"⏳ <b>MINES GAME EXPIRED (INACTIVITY)</b> ⏳\n"
                            f"<blockquote>👤 Trainer: <b>{html.escape(nickname)}</b>\n"
                            f"⏰ Reason: <b>No activity for 120 seconds</b>\n"
                            f"💎 Diamonds: <b>{revealed_count} 💎</b>\n"
                            f"💰 Auto-Cashed Out: <b>+{win_amt:,} coins</b>\n"
                            f"💰 New Balance: <b>💰 {bal:,} coins</b></blockquote>"
                        )
                    else:
                        timeout_text = (
                            f"⏳ <b>MINES GAME EXPIRED (INACTIVITY)</b> ⏳\n"
                            f"<blockquote>👤 Trainer: <b>{html.escape(nickname)}</b>\n"
                            f"⏰ Reason: <b>No activity for 120 seconds</b>\n"
                            f"💸 Lost Bet: <b>-{bet:,} coins</b></blockquote>\n"
                            f"<i>Start a new game with /mines when you are ready!</i>"
                        )
                    try:
                        await bot.edit_message_text(
                            chat_id=chat_id,
                            message_id=message_id,
                            text=timeout_text,
                            reply_markup=get_mines_keyboard(user_id, game),
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"Error in mines inactivity watchdog for user {user_id}: {e}")

    inactivity_tasks[user_id] = asyncio.create_task(inactivity_watchdog())

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
                "• Daily Limit: <b>4 games per day</b>\n"
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
        
        if not user:
            user = User(
                id=user_id,
                username=message.from_user.username,
                nickname=message.from_user.first_name or "Trainer",
                coins=1000
            )
            db.add(user)
            await db.flush()

        # Enforce Daily Limit (4 games per day)
        today = datetime.utcnow().date().isoformat()
        if user.last_mines_date != today:
            user.daily_mines_count = 0
            user.last_mines_date = today

        if user.daily_mines_count >= DAILY_MINES_LIMIT:
            await message.answer(
                f"⚠️ <b>Daily Mines Limit Reached!</b>\n"
                f"You have already played <b>{DAILY_MINES_LIMIT}/{DAILY_MINES_LIMIT}</b> Mines games today.\n"
                f"Come back tomorrow after midnight UTC for 4 more games!",
                parse_mode="HTML"
            )
            return

        if user.coins < bet:
            await message.answer("❌ You don't have enough coins to place this bet!")
            return

        # Increment daily mines count and deduct bet coins
        user.daily_mines_count += 1
        user.coins -= bet
        games_left = DAILY_MINES_LIMIT - user.daily_mines_count
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
            "nickname": user.nickname or message.from_user.first_name or "Trainer",
            "last_activity": time.time()
        }
        
        text = (
            f"💣 <b>MINES GAME STARTED</b> 💣\n"
            f"<blockquote>👤 Trainer: <b>{html.escape(game_state['nickname'])}</b>\n"
            f"💰 Bet: <b>{bet:,} coins</b>\n"
            f"💣 Mines: <b>{mines_count} 💣</b>\n"
            f"📈 Multiplier: <b>1.0x</b>\n"
            f"🎮 Daily Games Left: <b>{games_left}/{DAILY_MINES_LIMIT}</b>\n"
            f"⏳ Auto-end timer: <b>120s of inactivity</b></blockquote>\n"
            f"👉 Click on the tiles below to find diamonds! Avoid the mines!"
        )
        
        sent_msg = await message.answer(text, reply_markup=get_mines_keyboard(user_id, game_state), parse_mode="HTML")
        await save_game_state(user_id, game_state, db, chat_id=message.chat.id, message_id=sent_msg.message_id)
        reset_inactivity_timer(user_id, message.bot)

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

        # Keep inactivity timer fresh
        reset_inactivity_timer(user_id, callback.bot)
            
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
            except TelegramBadRequest as e:
                if "message is not modified" not in str(e).lower():
                    pass
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
            except TelegramBadRequest as e:
                if "message is not modified" not in str(e).lower():
                    pass
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
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e).lower():
                pass
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
        except TelegramBadRequest as e:
            if "message is not modified" not in str(e).lower():
                pass
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

