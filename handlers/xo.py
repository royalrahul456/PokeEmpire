import random
import asyncio
import time
from typing import Optional
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import User
from database.database import SessionLocal
from utils.formatters import escape_md
from utils.settings import send_cover_media

router = Router()

# In-memory dictionary for active XO games
# Keys:
# - For AI: f"xo_ai_{chat_id}_{user_id}"
# - For PvP: f"xo_pvp_{chat_id}_{message_id}"
active_xo_games = {}

# -------------------------------------------------------------
# TIC TAC TOE GAME LOGIC & MINIMAX AI
# -------------------------------------------------------------

def check_winner(board) -> Optional[str]:
    """Checks the board state for a winner. Returns 'X', 'O', 'draw', or None."""
    win_states = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8], # Rows
        [0, 3, 6], [1, 4, 7], [2, 5, 8], # Columns
        [0, 4, 8], [2, 4, 6]             # Diagonals
    ]
    for win in win_states:
        if board[win[0]] == board[win[1]] == board[win[2]] and board[win[0]] != "":
            return board[win[0]]
    if "" not in board:
        return "draw"
    return None

def minimax(board, depth, is_maximizing) -> int:
    """Minimax recursive evaluation."""
    winner = check_winner(board)
    if winner == "O":    # AI
        return 10 - depth
    if winner == "X":    # Player
        return depth - 10
    if winner == "draw":
        return 0

    if is_maximizing:
        best_score = -float('inf')
        for i in range(9):
            if board[i] == "":
                board[i] = "O"
                score = minimax(board, depth + 1, False)
                board[i] = ""
                best_score = max(score, best_score)
        return best_score
    else:
        best_score = float('inf')
        for i in range(9):
            if board[i] == "":
                board[i] = "X"
                score = minimax(board, depth + 1, True)
                board[i] = ""
                best_score = min(score, best_score)
        return best_score

def get_best_move(board) -> int:
    """Computes the mathematically optimal move for the AI ('O')."""
    best_score = -float('inf')
    best_move = 0
    for i in range(9):
        if board[i] == "":
            board[i] = "O"
            score = minimax(board, 0, False)
            board[i] = ""
            if score > best_score:
                best_score = score
                best_move = i
    return best_move

def make_ai_move(board, difficulty: str) -> int:
    """Selects AI move based on difficulty settings."""
    empty_cells = [i for i, cell in enumerate(board) if cell == ""]
    if not empty_cells:
        return -1

    if difficulty == "easy":
        # 50% random, 50% winning/blocking
        if random.random() < 0.5:
            return random.choice(empty_cells)
        # Check if O can win in one move
        for move in empty_cells:
            board[move] = "O"
            if check_winner(board) == "O":
                board[move] = ""
                return move
            board[move] = ""
        # Check if X can win in one move (and block it)
        for move in empty_cells:
            board[move] = "X"
            if check_winner(board) == "X":
                board[move] = ""
                return move
            board[move] = ""
        return random.choice(empty_cells)

    elif difficulty == "medium":
        # 80% minimax, 20% random
        if random.random() < 0.2:
            return random.choice(empty_cells)
        return get_best_move(board)

    else:
        # Unbeatable Hard mode (100% minimax)
        return get_best_move(board)

# Helper to format inline keyboard buttons
def get_xo_keyboard(game_key: str, board, is_pvp: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    prefix = "xo_pvp_play" if is_pvp else "xo_ai_play"
    
    for idx, cell in enumerate(board):
        text = cell if cell != "" else "⬜"
        # Callback data structure: prefix_gamekey_cellidx
        builder.button(text=text, callback_data=f"{prefix}_{game_key}_{idx}")
    
    builder.adjust(3)
    return builder.as_markup()

# Auto-cleanup helper for finished/expired games
async def delete_message_after(message: Message, delay: int):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass

# -------------------------------------------------------------
# HANDLERS - MAIN MENU & AI GAME LOOPS
# -------------------------------------------------------------

@router.message(Command("xo"))
async def cmd_xo(message: Message, db: AsyncSession):
    user_id = message.from_user.id
    parts = message.text.split()
    
    # Check if a PvP challenge is initiated
    if len(parts) >= 2:
        # Format: /xo <bet> <@username/reply>
        bet_str = parts[1]
        if not bet_str.isdigit():
            await message.answer("⚠️ Bet amount must be a number.")
            return
        bet = int(bet_str)
        if bet < 10 or bet > 10000:
            await message.answer("⚠️ Bet must be between 10 and 10,000 coins.")
            return
            
        target_user = None
        # Option A: Mentioned user
        if message.entities:
            for entity in message.entities:
                if entity.type == "mention":
                    username = message.text[entity.offset:entity.offset + entity.length].replace("@", "")
                    stmt = select(User).where(User.username == username)
                    res = await db.execute(stmt)
                    target_user = res.scalar_one_or_none()
                    break
                elif entity.type == "text_mention":
                    target_user = entity.user
                    break

        # Option B: Replying to a message
        if not target_user and message.reply_to_message:
            rep_user = message.reply_to_message.from_user
            if not rep_user.is_bot:
                stmt = select(User).where(User.id == rep_user.id)
                res = await db.execute(stmt)
                target_user = res.scalar_one_or_none()

        if not target_user:
            await message.answer("⚠️ Challenge a player by mentioning them or replying to their message:\n"
                                 "👉 `/xo <bet> @username` or reply with `/xo <bet>`")
            return

        if target_user.id == user_id:
            await message.answer("❌ You cannot challenge yourself!")
            return

        # Query Challenger to check coins
        stmt = select(User).where(User.id == user_id)
        res = await db.execute(stmt)
        challenger = res.scalar_one_or_none()
        
        if not challenger or challenger.coins < bet:
            await message.answer("❌ You do not have enough coins to place this bet!")
            return

        if target_user.coins < bet:
            await message.answer(f"❌ Trainer <b>{escape_md(target_user.nickname or 'Opponent')}</b> does not have enough coins!", parse_mode="HTML")
            return

        # Send challenge invitation
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="✅ Accept", callback_data=f"xo_pvp_accept_{user_id}_{target_user.id}_{bet}"),
            InlineKeyboardButton(text="❌ Decline", callback_data=f"xo_pvp_decline_{user_id}_{target_user.id}")
        )
        
        text = (
            f"⚔️ <b>TIC TAC TOE CHALLENGE</b> ⚔️\n"
            f"───────────────\n"
            f"👤 <b>Challenger</b>: <a href='tg://user?id={user_id}'>{escape_md(challenger.nickname or message.from_user.first_name)}</a>\n"
            f"👤 <b>Opponent</b>: <a href='tg://user?id={target_user.id}'>{escape_md(target_user.nickname or target_user.username or 'Trainer')}</a>\n"
            f"💰 <b>Bet</b>: 💰 <b>{bet} coins</b> each\n\n"
            f"Hey, do you accept this challenge?"
        )
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        return

    # Default: Show Main Menu
    caption = (
        f"🎲 <b>Tic Tac Toe</b>\n\n"
        f"🟢 Easy — +150 coins\n"
        f"🟡 Medium — +300 coins\n"
        f"🔴 Hard — +20,000 coins 💀\n"
        f"⚠️ <i>(Genuinely unbeatable AI — good luck!)</i>\n\n"
        f"👥 PvP — Challenge a friend"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🟢 Easy (+150)", callback_data="xo_ai_start_easy"),
        InlineKeyboardButton(text="🟡 Medium (+300)", callback_data="xo_ai_start_medium")
    )
    builder.row(
        InlineKeyboardButton(text="🔴 Hard (+20k 💀)", callback_data="xo_ai_start_hard")
    )
    builder.row(
        InlineKeyboardButton(text="👥 PvP Mode Info", callback_data="xo_pvp_info")
    )
    
    await send_cover_media(
        chat_id=message.chat.id,
        key="xo",
        caption=caption,
        reply_markup=builder.as_markup(),
        bot=message.bot,
        default_url="https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/890.png"
    )

@router.callback_query(F.data == "xo_pvp_info")
async def cb_xo_pvp_info(callback: CallbackQuery):
    text = (
        f"👥 <b>Tic Tac Toe PvP Mode</b> 👥\n"
        f"───────────────\n"
        f"Challenge another trainer to a 3x3 game of Tic Tac Toe with coins at stake!\n\n"
        f"👉 <b>How to challenge</b>:\n"
        f"• <code>/xo &lt;bet&gt; @username</code>\n"
        f"• Reply to their message with <code>/xo &lt;bet&gt;</code>\n\n"
        f"⚠️ <i>Bets can range from 10 to 10,000 coins. Both players must have enough coins.</i>"
    )
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Back to Menu", callback_data="xo_menu_back"))
    await callback.message.edit_caption(caption=text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data == "xo_menu_back")
async def cb_xo_menu_back(callback: CallbackQuery):
    caption = (
        f"🎲 <b>Tic Tac Toe</b>\n\n"
        f"🟢 Easy — +150 coins\n"
        f"🟡 Medium — +300 coins\n"
        f"🔴 Hard — +20,000 coins 💀\n"
        f"⚠️ <i>(Genuinely unbeatable AI — good luck!)</i>\n\n"
        f"👥 PvP — Challenge a friend"
    )
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🟢 Easy (+150)", callback_data="xo_ai_start_easy"),
        InlineKeyboardButton(text="🟡 Medium (+300)", callback_data="xo_ai_start_medium")
    )
    builder.row(
        InlineKeyboardButton(text="🔴 Hard (+20k 💀)", callback_data="xo_ai_start_hard")
    )
    builder.row(
        InlineKeyboardButton(text="👥 PvP Mode Info", callback_data="xo_pvp_info")
    )
    await callback.message.edit_caption(caption=caption, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data.startswith("xo_ai_start_"))
async def cb_xo_ai_start(callback: CallbackQuery):
    difficulty = callback.data.replace("xo_ai_start_", "")
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    game_key = f"{chat_id}_{user_id}"
    
    # Initialize game
    active_xo_games[f"xo_ai_{game_key}"] = {
        "type": "ai",
        "board": [""] * 9,
        "difficulty": difficulty,
        "player_x": user_id,
        "player_x_name": callback.from_user.first_name,
        "turn": "X",
        "created_at": time.time()
    }
    
    text = (
        f"🎲 <b>Tic Tac Toe (AI - {difficulty.title()})</b> 🎲\n"
        f"───────────────\n"
        f"Trainer: ❌ <b>{escape_md(callback.from_user.first_name)}</b>\n"
        f"Opponent: ⭕ <b>AI</b>\n\n"
        f"🟢 It's your turn! Click an empty square below:"
    )
    
    # Replace menu with the active board
    await callback.message.edit_caption(
        caption=text, 
        reply_markup=get_xo_keyboard(game_key, [""] * 9, is_pvp=False),
        parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("xo_ai_play_"))
async def cb_xo_ai_play(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    # Structure: xo_ai_play_<chat_id>_<user_id>_<cell_index>
    chat_id = int(parts[3])
    user_id = int(parts[4])
    cell_idx = int(parts[5])
    
    game_key = f"{chat_id}_{user_id}"
    game_id = f"xo_ai_{game_key}"
    
    if game_id not in active_xo_games:
        await callback.answer("⚠️ Game has expired or already ended.", show_alert=True)
        return
        
    game = active_xo_games[game_id]
    
    # Ensure only the player who started this game can click
    if callback.from_user.id != game["player_x"]:
        await callback.answer("❌ This is not your game!", show_alert=True)
        return
        
    board = game["board"]
    if board[cell_idx] != "":
        await callback.answer("⚠️ That space is already taken!", show_alert=True)
        return
        
    # Apply player move
    board[cell_idx] = "X"
    
    # Check if player won
    winner = check_winner(board)
    if winner:
        await handle_ai_game_over(callback, game_id, winner, db)
        return
        
    # AI makes its move
    ai_move = make_ai_move(board, game["difficulty"])
    if ai_move != -1:
        board[ai_move] = "O"
        
    # Check if AI won
    winner = check_winner(board)
    if winner:
        await handle_ai_game_over(callback, game_id, winner, db)
        return
        
    # Continue game
    text = (
        f"🎲 <b>Tic Tac Toe (AI - {game['difficulty'].title()})</b> 🎲\n"
        f"───────────────\n"
        f"Trainer: ❌ <b>{escape_md(game['player_x_name'])}</b>\n"
        f"Opponent: ⭕ <b>AI</b>\n\n"
        f"🟢 Your turn! Click an empty square:"
    )
    await callback.message.edit_caption(
        caption=text,
        reply_markup=get_xo_keyboard(game_key, board, is_pvp=False),
        parse_mode="HTML"
    )
    await callback.answer()

async def handle_ai_game_over(callback: CallbackQuery, game_id: str, winner: str, db: AsyncSession):
    game = active_xo_games.pop(game_id, None)
    if not game:
        return
        
    board = game["board"]
    difficulty = game["difficulty"]
    user_id = game["player_x"]
    
    # Final board representation
    final_kb = get_xo_keyboard(f"{callback.message.chat.id}_{user_id}", board, is_pvp=False)
    
    if winner == "X":
        # Player won!
        rewards = {"easy": 150, "medium": 300, "hard": 20000}
        reward = rewards.get(difficulty, 150)
        
        # Credit user
        stmt = select(User).where(User.id == user_id)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()
        if user:
            user.coins += reward
            await db.commit()
            coins_str = f"Balance: 💰 <b>{user.coins} coins</b>."
        else:
            coins_str = ""
            
        text = (
            f"🎉 <b>VICTORY!</b> 🎉\n"
            f"───────────────\n"
            f"You defeated the AI on <b>{difficulty.title()}</b> mode!\n\n"
            f"💰 Reward: <b>+{reward} coins</b>\n"
            f"{coins_str}"
        )
    elif winner == "O":
        # AI won
        text = (
            f"💀 <b>DEFEAT!</b> 💀\n"
            f"───────────────\n"
            f"The AI on <b>{difficulty.title()}</b> mode has defeated you.\n\n"
            f"Better luck next time, Trainer!"
        )
    else:
        # Tie
        text = (
            f"🤝 <b>DRAW!</b> 🤝\n"
            f"───────────────\n"
            f"The match has ended in a draw on <b>{difficulty.title()}</b> mode.\n\n"
            f"Good game!"
        )
        
    await callback.message.edit_caption(caption=text, reply_markup=final_kb, parse_mode="HTML")
    await callback.answer("Game Over!")
    # Auto delete the game message after 60s
    asyncio.create_task(delete_message_after(callback.message, 60))

# -------------------------------------------------------------
# HANDLERS - PVP MODE (CHALLENGE / ACCEPT / GAMEPLAY)
# -------------------------------------------------------------

@router.callback_query(F.data.startswith("xo_pvp_decline_"))
async def cb_xo_pvp_decline(callback: CallbackQuery):
    parts = callback.data.split("_")
    challenger_id = int(parts[3])
    target_id = int(parts[4])
    
    if callback.from_user.id != target_id:
        await callback.answer("❌ This challenge was not sent to you!", show_alert=True)
        return
        
    await callback.message.edit_text("❌ Challenge declined.")
    await callback.answer()
    asyncio.create_task(delete_message_after(callback.message, 10))

@router.callback_query(F.data.startswith("xo_pvp_accept_"))
async def cb_xo_pvp_accept(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    challenger_id = int(parts[3])
    target_id = int(parts[4])
    bet = int(parts[5])
    
    chat_id = callback.message.chat.id
    msg_id = callback.message.message_id
    
    if callback.from_user.id != target_id:
        await callback.answer("❌ This challenge was not sent to you!", show_alert=True)
        return

    # Check challenger balance
    stmt = select(User).where(User.id == challenger_id)
    res = await db.execute(stmt)
    challenger = res.scalar_one_or_none()
    
    if not challenger or challenger.coins < bet:
        await callback.answer("❌ Challenger no longer has enough coins!", show_alert=True)
        await callback.message.edit_text("❌ Match cancelled due to insufficient funds of challenger.")
        return

    # Check opponent balance
    stmt = select(User).where(User.id == target_id)
    res = await db.execute(stmt)
    opponent = res.scalar_one_or_none()
    
    if not opponent or opponent.coins < bet:
        await callback.answer("❌ You do not have enough coins to accept this challenge!", show_alert=True)
        return

    # Deduct bets
    challenger.coins -= bet
    opponent.coins -= bet
    await db.commit()

    game_key = f"{chat_id}_{msg_id}"
    game_id = f"xo_pvp_{game_key}"
    
    # Initialize PvP game
    active_xo_games[game_id] = {
        "type": "pvp",
        "board": [""] * 9,
        "player_x": challenger_id,
        "player_x_name": challenger.nickname or "Challenger",
        "player_o": target_id,
        "player_o_name": opponent.nickname or "Opponent",
        "turn": "X",
        "bet": bet,
        "created_at": time.time()
    }
    
    text = (
        f"🎲 <b>Tic Tac Toe PvP</b> 🎲\n"
        f"───────────────\n"
        f"❌ <b>{escape_md(challenger.nickname or 'Challenger')}</b> vs ⭕ <b>{escape_md(opponent.nickname or 'Opponent')}</b>\n"
        f"💰 Bet: 💰 <b>{bet} coins</b> each\n\n"
        f"🟢 It's <a href='tg://user?id={challenger_id}'>{escape_md(challenger.nickname or 'Challenger')}</a>'s turn! (X)"
    )
    
    # Delete the original invitation and start the game with the board
    try:
        await callback.message.delete()
    except Exception:
        pass
        
    sent_msg = await callback.message.channel_post.answer_photo(
        photo="https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/890.png"
    ) if False else None # Wait, let's just send it as photo, or send a new photo message!
    
    # Actually, sending a new photo message is much better for UI:
    new_msg = await callback.bot.send_photo(
        chat_id=chat_id,
        photo="https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/890.png",
        caption=text,
        reply_markup=get_xo_keyboard(game_key, [""] * 9, is_pvp=True),
        parse_mode="HTML"
    )
    
    # Re-key the game state with the new message ID so gameplay clicks map correctly!
    active_xo_games.pop(game_id)
    new_game_key = f"{chat_id}_{new_msg.message_id}"
    active_xo_games[f"xo_pvp_{new_game_key}"] = {
        "type": "pvp",
        "board": [""] * 9,
        "player_x": challenger_id,
        "player_x_name": challenger.nickname or "Challenger",
        "player_o": target_id,
        "player_o_name": opponent.nickname or "Opponent",
        "turn": "X",
        "bet": bet,
        "created_at": time.time()
    }
    await callback.answer("Challenge accepted!")

@router.callback_query(F.data.startswith("xo_pvp_play_"))
async def cb_xo_pvp_play(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    # Structure: xo_pvp_play_<chat_id>_<message_id>_<cell_index>
    chat_id = int(parts[3])
    msg_id = int(parts[4])
    cell_idx = int(parts[5])
    
    game_key = f"{chat_id}_{msg_id}"
    game_id = f"xo_pvp_{game_key}"
    
    if game_id not in active_xo_games:
        await callback.answer("⚠️ Game has expired or already ended.", show_alert=True)
        return
        
    game = active_xo_games[game_id]
    user_id = callback.from_user.id
    
    # Verify turns
    current_symbol = game["turn"]
    current_player_id = game["player_x"] if current_symbol == "X" else game["player_o"]
    
    if user_id != current_player_id:
        await callback.answer("❌ It's not your turn!", show_alert=True)
        return
        
    board = game["board"]
    if board[cell_idx] != "":
        await callback.answer("⚠️ That space is already taken!", show_alert=True)
        return
        
    # Apply move
    board[cell_idx] = current_symbol
    
    # Check for winner
    winner = check_winner(board)
    if winner:
        await handle_pvp_game_over(callback, game_id, winner, db)
        return
        
    # Toggle turn
    next_symbol = "O" if current_symbol == "X" else "X"
    game["turn"] = next_symbol
    next_player_id = game["player_x"] if next_symbol == "X" else game["player_o"]
    next_player_name = game["player_x_name"] if next_symbol == "X" else game["player_o_name"]
    
    text = (
        f"🎲 <b>Tic Tac Toe PvP</b> 🎲\n"
        f"───────────────\n"
        f"❌ <b>{escape_md(game['player_x_name'])}</b> vs ⭕ <b>{escape_md(game['player_o_name'])}</b>\n"
        f"💰 Bet: 💰 <b>{game['bet']} coins</b> each\n\n"
        f"🟢 It's <a href='tg://user?id={next_player_id}'>{escape_md(next_player_name)}</a>'s turn! ({next_symbol})"
    )
    
    await callback.message.edit_caption(
        caption=text,
        reply_markup=get_xo_keyboard(game_key, board, is_pvp=True),
        parse_mode="HTML"
    )
    await callback.answer()

async def handle_pvp_game_over(callback: CallbackQuery, game_id: str, winner: str, db: AsyncSession):
    game = active_xo_games.pop(game_id, None)
    if not game:
        return
        
    board = game["board"]
    bet = game["bet"]
    chat_id = callback.message.chat.id
    
    final_kb = get_xo_keyboard(f"{chat_id}_{callback.message.message_id}", board, is_pvp=True)
    
    if winner == "draw":
        # Draw: Refund both
        stmt_x = select(User).where(User.id == game["player_x"])
        res_x = await db.execute(stmt_x)
        user_x = res_x.scalar_one_or_none()
        if user_x:
            user_x.coins += bet
            
        stmt_o = select(User).where(User.id == game["player_o"])
        res_o = await db.execute(stmt_o)
        user_o = res_o.scalar_one_or_none()
        if user_o:
            user_o.coins += bet
            
        await db.commit()
        
        text = (
            f"🤝 <b>DRAW!</b> 🤝\n"
            f"───────────────\n"
            f"❌ <b>{escape_md(game['player_x_name'])}</b> vs ⭕ <b>{escape_md(game['player_o_name'])}</b>\n\n"
            f"The match ended in a draw! Both players have been refunded their bets of 💰 <b>{bet} coins</b>."
        )
    else:
        # X or O won
        winner_id = game["player_x"] if winner == "X" else game["player_o"]
        winner_name = game["player_x_name"] if winner == "X" else game["player_o_name"]
        
        # Credit winner double the bet (their bet + opponent's bet)
        stmt = select(User).where(User.id == winner_id)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()
        
        if user:
            user.coins += bet * 2
            await db.commit()
            coins_str = f"Balance: 💰 <b>{user.coins} coins</b>."
        else:
            coins_str = ""
            
        text = (
            f"🎉 <b>VICTORY!</b> 🎉\n"
            f"───────────────\n"
            f"❌ <b>{escape_md(game['player_x_name'])}</b> vs ⭕ <b>{escape_md(game['player_o_name'])}</b>\n\n"
            f"🏆 <b>Winner</b>: <a href='tg://user?id={winner_id}'>{escape_md(winner_name)}</a>\n"
            f"💰 Earned: 💰 <b>+{bet} coins</b> from the opponent!\n"
            f"{coins_str}"
        )
        
    await callback.message.edit_caption(caption=text, reply_markup=final_kb, parse_mode="HTML")
    await callback.answer("Match Over!")
    # Auto delete board message after 60s
    asyncio.create_task(delete_message_after(callback.message, 60))
