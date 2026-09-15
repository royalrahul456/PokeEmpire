import random
import asyncio
import html
import time
import os
import json
from typing import Optional, Tuple
from datetime import datetime, timedelta
import io
import re
import aiohttp
try:
    from PIL import Image
except ImportError:
    Image = None
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import config
from database.models import User, Pokemon, UserPokemon
from database.database import SessionLocal
from utils.formatters import escape_md, get_rarity_emoji
from utils.settings import (
    is_scribble_enabled, 
    set_scribble_status, 
    is_nameguess_enabled, 
    set_nameguess_status,
    send_safe_media
)
from keyboards.inline import (
    get_back_to_hub_keyboard, 
    create_styled_button, 
    get_official_group_keyboard, 
    GROUP_ONLY_GAMES_NOTICE
)

router = Router()

# In-memory dictionary to track active trivia/scribble games per chat
active_games = {}
# In-memory dictionary to track trainer trivia command cooldowns
last_trivia_time = {}

@router.message(Command("daily"))
async def cmd_daily(message: Message, db: AsyncSession):
    import html
    user_id = message.from_user.id
    nickname = message.from_user.first_name

    # Check/Register user
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user:
        user = User(id=user_id, username=message.from_user.username, nickname=nickname)
        db.add(user)
        await db.flush()

    now = datetime.utcnow()
    if user.last_daily_at:
        cooldown = timedelta(hours=24)
        elapsed = now - user.last_daily_at
        if elapsed < cooldown:
            remaining = cooldown - elapsed
            hours, remainder = divmod(remaining.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_str = f"{hours}h {minutes}m {seconds}s"
            await message.answer(
                f"⏳ <b>DAILY REWARD COOLDOWN</b>\n"
                f"<blockquote>Too early! You can claim your next daily reward in <b>{time_str}</b>.</blockquote>",
                parse_mode="HTML"
            )
            return

    reward = random.randint(250, 550)
    user.coins += reward
    user.last_daily_at = now
    await db.commit()

    text = (
        f"📅 <b>DAILY REWARD SUCCESS</b>\n"
        f"───────────────\n"
        f"<blockquote>👤 Trainer: <b>{html.escape(user.nickname)}</b>\n"
        f"💰 Earned: <b>+{reward} coins</b>\n"
        f"💳 Balance: <b>{user.coins} coins</b></blockquote>"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(Command("claim"))
async def cmd_claim(message: Message, db: AsyncSession):
    import html
    user_id = message.from_user.id
    nickname = message.from_user.first_name
    
    # Check claim cooldown using utils/claim.py
    from utils.claim import check_claim_cooldown, update_claim_cooldown
    remaining_cooldown = check_claim_cooldown(user_id)
    if remaining_cooldown > 0:
        hours = remaining_cooldown // 3600
        minutes = (remaining_cooldown % 3600) // 60
        seconds = remaining_cooldown % 60
        time_str = f"{hours}h {minutes}m {seconds}s"
        await message.answer(
            f"⏳ <b>DAILY CLAIM COOLDOWN</b>\n"
            f"<blockquote>Too early! You can claim your next free Pokémon in <b>{time_str}</b>.</blockquote>",
            parse_mode="HTML"
        )
        return
        
    # Get all Pokémon list from database
    stmt = select(Pokemon)
    res = await db.execute(stmt)
    pokemon_list = res.scalars().all()
    
    if not pokemon_list:
        await message.answer("❌ <b>Error:</b> No Pokémon found in database to claim.")
        return
        
    # Select random Pokémon
    selected_pokemon = random.choice(pokemon_list)
    
    # Roll shiny (1% chance)
    is_shiny = random.randint(1, 100) == 1
    
    # Generate random IVs
    iv_hp = random.randint(0, 31)
    iv_atk = random.randint(0, 31)
    iv_def = random.randint(0, 31)
    iv_spd = random.randint(0, 31)
    
    # Check/Register user in DB
    stmt_user = select(User).where(User.id == user_id)
    res_user = await db.execute(stmt_user)
    user = res_user.scalar_one_or_none()
    
    if not user:
        user = User(id=user_id, username=message.from_user.username, nickname=nickname)
        db.add(user)
        await db.flush()
        
    # Create capture entry
    capture = UserPokemon(
        user_id=user_id,
        pokemon_id=selected_pokemon.id,
        is_shiny=is_shiny,
        level=1,
        xp=0,
        iv_hp=iv_hp,
        iv_atk=iv_atk,
        iv_def=iv_def,
        iv_spd=iv_spd
    )
    db.add(capture)
    
    # Update cooldown
    update_claim_cooldown(user_id)
    await db.commit()
    
    # Build text using HTML blockquote style (excluding IV stats line)
    shiny_prefix = "✨ Shiny " if is_shiny else ""
    r_emoji = get_rarity_emoji(selected_pokemon.rarity)
    
    text = (
        f"🎁 <b>POKÉMON CLAIMED</b> 🎁\n"
        f"───────────────\n"
        f"<blockquote>👤 Trainer: <b>{html.escape(user.nickname)}</b>\n"
        f"👾 Pokémon: <b>{shiny_prefix}{selected_pokemon.name.title()}</b>\n"
        f"{r_emoji} Rarity: <b>{r_emoji} {selected_pokemon.rarity}</b></blockquote>"
    )
    
    # Resolve media for the claimed pokemon: try form 1 (Art/AMV) first, then video_url, then image_url
    from database.models import PokemonFormMedia
    from handlers.profile import parse_stored_media_value
    
    media_value = None
    media_type = "photo"
    
    if is_shiny:
        s_media_stmt = select(PokemonFormMedia.media_value).where(
            PokemonFormMedia.pokemon_id == selected_pokemon.id,
            PokemonFormMedia.form_index == 6
        )
        s_media_res = await db.execute(s_media_stmt)
        s_media = s_media_res.scalar_one_or_none()
        if s_media:
            media_type, media_value = parse_stored_media_value(s_media)
            form1_media = None
        else:
            form1_media = None
    else:
        form1_stmt = select(PokemonFormMedia.media_value).where(
            PokemonFormMedia.pokemon_id == selected_pokemon.id,
            PokemonFormMedia.form_index == 1
        )
        form1_res = await db.execute(form1_stmt)
        form1_media = form1_res.scalar_one_or_none()
    
    if not media_value:
        media_type = "photo"
        media_value = selected_pokemon.image_url
        if selected_pokemon.image_url:
            media_type, media_value = parse_stored_media_value(selected_pokemon.image_url)
            
    await send_safe_media(
        bot=message.bot,
        chat_id=message.chat.id,
        media_type=media_type,
        media_value=media_value,
        caption=text,
        parse_mode="HTML",
        message_to_reply=message
    )

@router.message(Command("spin", "wheel"))
async def cmd_spin(message: Message, db: AsyncSession):
    if message.chat.type == "private":
        await message.answer(GROUP_ONLY_GAMES_NOTICE, reply_markup=get_official_group_keyboard(), parse_mode="HTML")
        return

    import html
    user_id = message.from_user.id
    nickname = message.from_user.first_name

    # Check/Register user
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user:
        user = User(id=user_id, username=message.from_user.username, nickname=nickname)
        db.add(user)
        await db.flush()

    now = datetime.utcnow()
    if user.last_spin_at:
        cooldown = timedelta(hours=1)
        elapsed = now - user.last_spin_at
        if elapsed < cooldown:
            remaining = cooldown - elapsed
            hours, remainder = divmod(remaining.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_str = f"{hours}h {minutes}m {seconds}s"
            await message.answer(
                f"⏳ <b>SPIN WHEEL COOLDOWN</b>\n"
                f"<blockquote>The lucky wheel is recharging. Spin again in <b>{time_str}</b>.</blockquote>",
                parse_mode="HTML"
            )
            return

    rewards = [100, 150, 200, 250, 350, 550]
    weights = [40, 30, 15, 10, 4, 1]
    won = random.choices(rewards, weights=weights, k=1)[0]

    user.coins += won
    user.last_spin_at = now
    await db.commit()

    # Simple text-based spin animation in HTML
    wheels = [
        "🎡 <b>LUCKY SPIN WHEEL</b> 🎡\n───────────────\nSpinning... 🎰 [ 🔴 | 🟡 | 🟢 | 🔵 ]",
        "🎡 <b>LUCKY SPIN WHEEL</b> 🎡\n───────────────\nSpinning... 🎰 [ 100 | 250 | 550 ]",
        f"🎡 <b>LUCKY SPIN RESULT</b> 🎡\n───────────────\n"
        f"🎉 <b>STAY!</b> 🎉\n\n"
        f"<blockquote>👤 Trainer: <b>{html.escape(user.nickname)}</b>\n"
        f"💰 Won: <b>+{won} coins</b>\n"
        f"💳 Balance: <b>{user.coins} coins</b></blockquote>"
    ]
    
    msg = await message.answer(wheels[0], parse_mode="HTML")
    await asyncio.sleep(0.5)
    await msg.edit_text(wheels[1], parse_mode="HTML")
    await asyncio.sleep(0.5)
    await msg.edit_text(wheels[2], parse_mode="HTML")
@router.message(Command("coinflip", "cf", "flip"))
async def cmd_coinflip(message: Message, db: AsyncSession):
    if message.chat.type == "private":
        await message.answer(GROUP_ONLY_GAMES_NOTICE, reply_markup=get_official_group_keyboard(), parse_mode="HTML")
        return

    user_id = message.from_user.id

    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("⚠️ Format: `/coinflip <bet_amount> <heads/tails>`\n(e.g., `/coinflip 100 heads`)")
        return

    # Parse bet
    bet_str = parts[1]
    if not bet_str.isdigit():
        await message.answer("⚠️ Bet amount must be a number.")
        return
    bet = int(bet_str)

    if bet < 10 or bet > 10000:
        await message.answer("⚠️ Bet must be between 10 and 10,000 coins.")
        return

    # Parse guess
    guess = parts[2].lower()
    if guess in ["h", "head", "heads"]:
        user_choice = "heads"
    elif guess in ["t", "tail", "tails"]:
        user_choice = "tails"
    else:
        await message.answer("⚠️ Choice must be `heads` or `tails`.")
        return

    # Query user
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user or user.coins < bet:
        await message.answer("⚠️ You do not have enough coins to place this bet!")
        return

    # Flip coin
    outcome = random.choice(["heads", "tails"])
    won = user_choice == outcome

    if won:
        user.coins += bet
        await db.commit()
        text = (
            f"🪙 <b>COINFLIP RESULT</b> 🪙\n"
            f"───────────────\n"
            f"<blockquote>🪙 Landed on: <b>{outcome.upper()}</b>\n"
            f"🎉 Result: <b>Victory!</b>\n"
            f"💰 Gained: <b>+{bet} coins</b>\n"
            f"💳 Balance: <b>{user.coins} coins</b></blockquote>"
        )
    else:
        user.coins -= bet
        await db.commit()
        text = (
            f"🪙 <b>COINFLIP RESULT</b> 🪙\n"
            f"───────────────\n"
            f"<blockquote>🪙 Landed on: <b>{outcome.upper()}</b>\n"
            f"💀 Result: <b>Defeat!</b>\n"
            f"💰 Lost: <b>-{bet} coins</b>\n"
            f"💳 Balance: <b>{user.coins} coins</b></blockquote>"
        )

    msg = await message.answer("🪙 Flipping the coin... 🪙\n───────────────\n🔄 *Spinning in the air...*")
    await asyncio.sleep(0.5)
    await msg.edit_text("🪙 Flipping the coin... 🪙\n───────────────\n✨ *Falling down...*")
    await asyncio.sleep(0.5)
    await msg.edit_text(text, parse_mode="HTML")

@router.message(Command("rps"))
async def cmd_rps(message: Message, db: AsyncSession):
    if message.chat.type == "private":
        await message.answer(GROUP_ONLY_GAMES_NOTICE, reply_markup=get_official_group_keyboard(), parse_mode="HTML")
        return

    user_id = message.from_user.id

    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("⚠️ Format: `/rps <bet_amount> <rock/paper/scissors>`\n(e.g., `/rps 100 rock`)")
        return

    bet_str = parts[1]
    if not bet_str.isdigit():
        await message.answer("⚠️ Bet amount must be a number.")
        return
    bet = int(bet_str)

    if bet < 10 or bet > 10000:
        await message.answer("⚠️ Bet must be between 10 and 10,000 coins.")
        return

    choice = parts[2].lower()
    valid = ["rock", "paper", "scissors", "r", "p", "s"]
    if choice not in valid:
        await message.answer("⚠️ Choice must be `rock`, `paper`, or `scissors`.")
        return

    # Map shortcuts
    shortcuts = {"r": "rock", "p": "paper", "s": "scissors"}
    user_choice = shortcuts.get(choice, choice)

    # Query user
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user or user.coins < bet:
        await message.answer("⚠️ You do not have enough coins to place this bet!")
        return

    bot_choice = random.choice(["rock", "paper", "scissors"])
    
    # Check outcomes
    if user_choice == bot_choice:
        outcome = "draw"
    elif (user_choice == "rock" and bot_choice == "scissors") or \
         (user_choice == "paper" and bot_choice == "rock") or \
         (user_choice == "scissors" and bot_choice == "paper"):
        outcome = "win"
    else:
        outcome = "lose"

    if outcome == "draw":
        text = (
            f"✊✋✌️ <b>ROCK-PAPER-SCISSORS</b> ✊✋✌️\n"
            f"───────────────\n"
            f"<blockquote>👤 You: <b>{user_choice.title()}</b>\n"
            f"🤖 Bot: <b>{bot_choice.title()}</b>\n"
            f"🤝 Result: <b>Draw!</b> (Refunded {bet} coins)</blockquote>"
        )
    elif outcome == "win":
        user.coins += bet
        await db.commit()
        text = (
            f"✊✋✌️ <b>ROCK-PAPER-SCISSORS</b> ✊✋✌️\n"
            f"───────────────\n"
            f"<blockquote>👤 You: <b>{user_choice.title()}</b>\n"
            f"🤖 Bot: <b>{bot_choice.title()}</b>\n"
            f"🎉 Result: <b>Victory!</b>\n"
            f"💰 Gained: <b>+{bet} coins</b>\n"
            f"💳 Balance: <b>{user.coins} coins</b></blockquote>"
        )
    else:
        user.coins -= bet
        await db.commit()
        text = (
            f"✊✋✌️ <b>ROCK-PAPER-SCISSORS</b> ✊✋✌️\n"
            f"───────────────\n"
            f"<blockquote>👤 You: <b>{user_choice.title()}</b>\n"
            f"🤖 Bot: <b>{bot_choice.title()}</b>\n"
            f"💀 Result: <b>Defeat!</b>\n"
            f"💰 Lost: <b>-{bet} coins</b>\n"
            f"💳 Balance: <b>{user.coins} coins</b></blockquote>"
        )

    msg = await message.answer("✊✋✌️ Dueling... ✊✋✌️\n───────────────\n🔄 *Rock... Paper... Scissors...*")
    await asyncio.sleep(0.5)
    await msg.edit_text("✊✋✌️ Dueling... ✊✋✌️\n───────────────\n💥 *SHOOT!* 💥")
    await asyncio.sleep(0.5)
    await msg.edit_text(text, parse_mode="HTML")

@router.message(Command("dice", "roll"))
async def cmd_dice(message: Message, db: AsyncSession):
    if message.chat.type == "private":
        await message.answer(GROUP_ONLY_GAMES_NOTICE, reply_markup=get_official_group_keyboard(), parse_mode="HTML")
        return

    user_id = message.from_user.id
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("⚠️ <b>Dice Duel Format:</b> <code>/dice &lt;bet_amount&gt;</code>\n<i>(e.g., <code>/dice 500</code>)</i>", parse_mode="HTML")
        return

    bet = int(parts[1])
    if bet < 10 or bet > 100000:
        await message.answer("⚠️ Bet must be between 10 and 100,000 coins.", parse_mode="HTML")
        return

    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user or user.coins < bet:
        user_coins = user.coins if user else 0
        await message.answer(f"❌ You do not have enough coins! Balance: 💰 <code>{user_coins:,} coins</code>.", parse_mode="HTML")
        return

    user.coins -= bet
    await db.flush()

    sender_name = html.escape(user.nickname or user.username or message.from_user.first_name or "Trainer")

    await message.answer(f"🎲 <b>Dice Duel</b> against PokeArena AI!\n👤 <b>{sender_name}</b> throws first:", parse_mode="HTML")
    user_dice_msg = await message.answer_dice(emoji="🎲")
    await asyncio.sleep(2.5)
    user_roll = user_dice_msg.dice.value

    await message.answer("🤖 <b>PokeArena AI</b> throws:", parse_mode="HTML")
    bot_dice_msg = await message.answer_dice(emoji="🎲")
    await asyncio.sleep(2.5)
    bot_roll = bot_dice_msg.dice.value

    if user_roll > bot_roll:
        win_amt = bet * 2
        user.coins += win_amt
        try:
            from utils.trainer_level import log_transaction
            await log_transaction(user_id, bet, "DICE_WIN", f"Won Dice Duel ({user_roll} vs {bot_roll})", db)
        except Exception:
            pass
        result_text = (
            f"🎲 <b>DICE DUEL RESULT</b> 🎲\n"
            f"───────────────\n"
            f"<blockquote>👤 You rolled: <b>{user_roll}</b> 🎲\n"
            f"🤖 Bot rolled: <b>{bot_roll}</b> 🎲\n"
            f"🎉 Result: <b>Victory!</b>\n"
            f"💰 Won: <b>+{win_amt:,} coins</b> (Net: <code>+{bet:,}</code>)\n"
            f"💳 Balance: <code>💰 {user.coins:,} coins</code></blockquote>"
        )
    elif user_roll == bot_roll:
        user.coins += bet  # Refund bet
        result_text = (
            f"🎲 <b>DICE DUEL RESULT</b> 🎲\n"
            f"───────────────\n"
            f"<blockquote>👤 You rolled: <b>{user_roll}</b> 🎲\n"
            f"🤖 Bot rolled: <b>{bot_roll}</b> 🎲\n"
            f"🤝 Result: <b>Tie / Draw!</b> (Bet refunded)\n"
            f"💳 Balance: <code>💰 {user.coins:,} coins</code></blockquote>"
        )
    else:
        try:
            from utils.trainer_level import log_transaction
            await log_transaction(user_id, -bet, "DICE_LOSS", f"Lost Dice Duel ({user_roll} vs {bot_roll})", db)
        except Exception:
            pass
        result_text = (
            f"🎲 <b>DICE DUEL RESULT</b> 🎲\n"
            f"───────────────\n"
            f"<blockquote>👤 You rolled: <b>{user_roll}</b> 🎲\n"
            f"🤖 Bot rolled: <b>{bot_roll}</b> 🎲\n"
            f"💀 Result: <b>Defeat!</b>\n"
            f"💰 Lost: <b>-{bet:,} coins</b>\n"
            f"💳 Balance: <code>💰 {user.coins:,} coins</code></blockquote>"
        )

    await db.commit()
    builder = InlineKeyboardBuilder()
    builder.row(create_styled_button(text="🎲 Roll Again", key="games", callback_data="btn_launch_dice", style="primary"))
    await message.answer(result_text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.message(Command("darts", "dart"))
async def cmd_darts(message: Message, db: AsyncSession):
    if message.chat.type == "private":
        await message.answer(GROUP_ONLY_GAMES_NOTICE, reply_markup=get_official_group_keyboard(), parse_mode="HTML")
        return

    user_id = message.from_user.id
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("⚠️ <b>Darts Format:</b> <code>/darts &lt;bet_amount&gt;</code>\n<i>(e.g., <code>/darts 500</code>)</i>", parse_mode="HTML")
        return

    bet = int(parts[1])
    if bet < 10 or bet > 100000:
        await message.answer("⚠️ Bet must be between 10 and 100,000 coins.", parse_mode="HTML")
        return

    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user or user.coins < bet:
        user_coins = user.coins if user else 0
        await message.answer(f"❌ You do not have enough coins! Balance: 💰 <code>{user_coins:,} coins</code>.", parse_mode="HTML")
        return

    user.coins -= bet
    await db.flush()

    sender_name = html.escape(user.nickname or user.username or message.from_user.first_name or "Trainer")
    await message.answer(f"🎯 <b>{sender_name}</b> throws a dart at the target!", parse_mode="HTML")
    dice_msg = await message.answer_dice(emoji="🎯")
    await asyncio.sleep(2.5)
    score = dice_msg.dice.value

    if score == 6:
        multiplier = 3.0
        label = "🎯 BULLSEYE! DEAD CENTER!"
    elif score in (4, 5):
        multiplier = 1.5
        label = "✨ INNER RING HIT!"
    elif score in (2, 3):
        multiplier = 0.5
        label = "🔘 OUTER RING HIT (Partial refund)"
    else:
        multiplier = 0.0
        label = "💨 COMPLETE MISS! Off-target."

    win_amt = int(bet * multiplier)
    net_profit = win_amt - bet

    if win_amt > 0:
        user.coins += win_amt
        try:
            from utils.trainer_level import log_transaction
            await log_transaction(user_id, win_amt, "DARTS_WIN", f"Won Darts ({multiplier}x)", db)
        except Exception:
            pass
    else:
        try:
            from utils.trainer_level import log_transaction
            await log_transaction(user_id, -bet, "DARTS_LOSS", "Lost Darts", db)
        except Exception:
            pass

    await db.commit()

    result_text = (
        f"🎯 <b>DARTS RESULT</b> 🎯\n"
        f"───────────────\n"
        f"🎯 <b>{label}</b> (Score: <b>{score}/6</b>)\n\n"
        f"<blockquote>👤 Trainer: <b>{sender_name}</b>\n"
        f"💰 Multiplier: <b>{multiplier}x</b>\n"
        f"💵 Payout: <b>+{win_amt:,} coins</b> (Net: <code>{'+' if net_profit >= 0 else ''}{net_profit:,}</code>)\n"
        f"💳 Balance: <code>💰 {user.coins:,} coins</code></blockquote>"
    )
    builder = InlineKeyboardBuilder()
    builder.row(create_styled_button(text="🎯 Throw Again", key="games", callback_data="btn_launch_darts", style="primary"))
    await message.answer(result_text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.message(Command("basketball", "basket", "bb"))
async def cmd_basketball(message: Message, db: AsyncSession):
    if message.chat.type == "private":
        await message.answer(GROUP_ONLY_GAMES_NOTICE, reply_markup=get_official_group_keyboard(), parse_mode="HTML")
        return

    user_id = message.from_user.id
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("⚠️ <b>Basketball Format:</b> <code>/basketball &lt;bet_amount&gt;</code>\n<i>(e.g., <code>/basketball 500</code>)</i>", parse_mode="HTML")
        return

    bet = int(parts[1])
    if bet < 10 or bet > 100000:
        await message.answer("⚠️ Bet must be between 10 and 100,000 coins.", parse_mode="HTML")
        return

    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user or user.coins < bet:
        user_coins = user.coins if user else 0
        await message.answer(f"❌ You do not have enough coins! Balance: 💰 <code>{user_coins:,} coins</code>.", parse_mode="HTML")
        return

    user.coins -= bet
    await db.flush()

    sender_name = html.escape(user.nickname or user.username or message.from_user.first_name or "Trainer")
    await message.answer(f"🏀 <b>{sender_name}</b> shoots for the hoop!", parse_mode="HTML")
    dice_msg = await message.answer_dice(emoji="🏀")
    await asyncio.sleep(2.5)
    score = dice_msg.dice.value

    if score in (4, 5):
        multiplier = 2.0
        label = "🏀 SWISH! BASKET SCORED! 🎉"
    else:
        multiplier = 0.0
        label = "❌ MISSED THE HOOP! 💀"

    win_amt = int(bet * multiplier)
    net_profit = win_amt - bet

    if win_amt > 0:
        user.coins += win_amt
        try:
            from utils.trainer_level import log_transaction
            await log_transaction(user_id, win_amt, "BASKETBALL_WIN", "Won Basketball Shot", db)
        except Exception:
            pass
    else:
        try:
            from utils.trainer_level import log_transaction
            await log_transaction(user_id, -bet, "BASKETBALL_LOSS", "Lost Basketball Shot", db)
        except Exception:
            pass

    await db.commit()

    result_text = (
        f"🏀 <b>BASKETBALL SHOT RESULT</b> 🏀\n"
        f"───────────────\n"
        f"<b>{label}</b>\n\n"
        f"<blockquote>👤 Trainer: <b>{sender_name}</b>\n"
        f"💰 Multiplier: <b>{multiplier}x</b>\n"
        f"💵 Payout: <b>+{win_amt:,} coins</b> (Net: <code>{'+' if net_profit >= 0 else ''}{net_profit:,}</code>)\n"
        f"💳 Balance: <code>💰 {user.coins:,} coins</code></blockquote>"
    )
    builder = InlineKeyboardBuilder()
    builder.row(create_styled_button(text="🏀 Shoot Again", key="games", callback_data="btn_launch_basket", style="primary"))
    await message.answer(result_text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.message(Command("football", "soccer", "goal"))
async def cmd_football(message: Message, db: AsyncSession):
    if message.chat.type == "private":
        await message.answer(GROUP_ONLY_GAMES_NOTICE, reply_markup=get_official_group_keyboard(), parse_mode="HTML")
        return

    user_id = message.from_user.id
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("⚠️ <b>Football Penalty Format:</b> <code>/football &lt;bet_amount&gt;</code>\n<i>(e.g., <code>/football 500</code>)</i>", parse_mode="HTML")
        return

    bet = int(parts[1])
    if bet < 10 or bet > 100000:
        await message.answer("⚠️ Bet must be between 10 and 100,000 coins.", parse_mode="HTML")
        return

    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user or user.coins < bet:
        user_coins = user.coins if user else 0
        await message.answer(f"❌ You do not have enough coins! Balance: 💰 <code>{user_coins:,} coins</code>.", parse_mode="HTML")
        return

    user.coins -= bet
    await db.flush()

    sender_name = html.escape(user.nickname or user.username or message.from_user.first_name or "Trainer")
    await message.answer(f"⚽ <b>{sender_name}</b> steps up for a penalty kick!", parse_mode="HTML")
    dice_msg = await message.answer_dice(emoji="⚽")
    await asyncio.sleep(2.5)
    score = dice_msg.dice.value

    if score in (3, 4, 5):
        multiplier = 1.8
        label = "⚽ GOOOOAL! BACK OF THE NET! 🚀"
    else:
        multiplier = 0.0
        label = "🧤 SAVED BY KEEPER / WIDE! 💀"

    win_amt = int(bet * multiplier)
    net_profit = win_amt - bet

    if win_amt > 0:
        user.coins += win_amt
        try:
            from utils.trainer_level import log_transaction
            await log_transaction(user_id, win_amt, "FOOTBALL_WIN", "Scored Football Penalty", db)
        except Exception:
            pass
    else:
        try:
            from utils.trainer_level import log_transaction
            await log_transaction(user_id, -bet, "FOOTBALL_LOSS", "Missed Football Penalty", db)
        except Exception:
            pass

    await db.commit()

    result_text = (
        f"⚽ <b>PENALTY SHOOTOUT RESULT</b> ⚽\n"
        f"───────────────\n"
        f"<b>{label}</b>\n\n"
        f"<blockquote>👤 Trainer: <b>{sender_name}</b>\n"
        f"💰 Multiplier: <b>{multiplier}x</b>\n"
        f"💵 Payout: <b>+{win_amt:,} coins</b> (Net: <code>{'+' if net_profit >= 0 else ''}{net_profit:,}</code>)\n"
        f"💳 Balance: <code>💰 {user.coins:,} coins</code></blockquote>"
    )
    builder = InlineKeyboardBuilder()
    builder.row(create_styled_button(text="⚽ Kick Again", key="games", callback_data="btn_launch_football", style="primary"))
    await message.answer(result_text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.message(Command("bowling", "bowl"))
async def cmd_bowling(message: Message, db: AsyncSession):
    if message.chat.type == "private":
        await message.answer(GROUP_ONLY_GAMES_NOTICE, reply_markup=get_official_group_keyboard(), parse_mode="HTML")
        return

    user_id = message.from_user.id
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("⚠️ <b>Bowling Format:</b> <code>/bowling &lt;bet_amount&gt;</code>\n<i>(e.g., <code>/bowling 500</code>)</i>", parse_mode="HTML")
        return

    bet = int(parts[1])
    if bet < 10 or bet > 100000:
        await message.answer("⚠️ Bet must be between 10 and 100,000 coins.", parse_mode="HTML")
        return

    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user or user.coins < bet:
        user_coins = user.coins if user else 0
        await message.answer(f"❌ You do not have enough coins! Balance: 💰 <code>{user_coins:,} coins</code>.", parse_mode="HTML")
        return

    user.coins -= bet
    await db.flush()

    sender_name = html.escape(user.nickname or user.username or message.from_user.first_name or "Trainer")
    await message.answer(f"🎳 <b>{sender_name}</b> rolls the bowling ball down the lane!", parse_mode="HTML")
    dice_msg = await message.answer_dice(emoji="🎳")
    await asyncio.sleep(2.5)
    score = dice_msg.dice.value

    if score == 6:
        multiplier = 3.5
        label = "🎳 STRIKE! ALL PINS DOWN! 💥"
    elif score in (4, 5):
        multiplier = 1.5
        label = "✨ SPARE! Great hit!"
    elif score in (2, 3):
        multiplier = 0.5
        label = "🎳 Partial Knockdown (Partial refund)"
    else:
        multiplier = 0.0
        label = "💨 GUTTER BALL! 0 Pins. 💀"

    win_amt = int(bet * multiplier)
    net_profit = win_amt - bet

    if win_amt > 0:
        user.coins += win_amt
        try:
            from utils.trainer_level import log_transaction
            await log_transaction(user_id, win_amt, "BOWLING_WIN", f"Bowling result ({score}/6)", db)
        except Exception:
            pass
    else:
        try:
            from utils.trainer_level import log_transaction
            await log_transaction(user_id, -bet, "BOWLING_LOSS", "Lost Bowling", db)
        except Exception:
            pass

    await db.commit()

    result_text = (
        f"🎳 <b>BOWLING RESULT</b> 🎳\n"
        f"───────────────\n"
        f"<b>{label}</b> (Pins: <b>{score}/6</b>)\n\n"
        f"<blockquote>👤 Trainer: <b>{sender_name}</b>\n"
        f"💰 Multiplier: <b>{multiplier}x</b>\n"
        f"💵 Payout: <b>+{win_amt:,} coins</b> (Net: <code>{'+' if net_profit >= 0 else ''}{net_profit:,}</code>)\n"
        f"💳 Balance: <code>💰 {user.coins:,} coins</code></blockquote>"
    )
    builder = InlineKeyboardBuilder()
    builder.row(create_styled_button(text="🎳 Bowl Again", key="games", callback_data="btn_launch_bowling", style="primary"))
    await message.answer(result_text, reply_markup=builder.as_markup(), parse_mode="HTML")


def generate_hint(name: str) -> str:
    revealed_indices = set()
    alpha_indices = [i for i, c in enumerate(name) if c.isalpha()]
    
    if alpha_indices:
        revealed_indices.add(alpha_indices[0])
        revealed_indices.add(alpha_indices[-1])
        if len(alpha_indices) > 5:
            mid_idx = alpha_indices[len(alpha_indices) // 2]
            revealed_indices.add(mid_idx)
            
    hint_parts = []
    for i, c in enumerate(name):
        if c == ' ':
            hint_parts.append("  ")  # double space for word separation
        elif not c.isalpha():
            hint_parts.append(c)
        elif i in revealed_indices:
            hint_parts.append(c.upper())
        else:
            hint_parts.append("_")
            
    return " ".join(hint_parts)

async def get_silhouette_bytes(image_url: str) -> bytes | None:
    if Image is None:
        return None
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(image_url, timeout=aiohttp.ClientTimeout(total=8)) as resp:
                if resp.status == 200:
                    data = await resp.read()
                    img = Image.open(io.BytesIO(data)).convert("RGBA")
                    r, g, b, a = img.split()
                    silhouette = Image.new("RGBA", img.size, (15, 23, 42, 255))
                    silhouette.putalpha(a)
                    out = io.BytesIO()
                    silhouette.save(out, format="PNG")
                    return out.getvalue()
    except Exception as e:
        print(f"Error generating silhouette: {e}")
    return None

# ========================================================
# TYPE MATCHUP BLITZ (THE ELEMENTAL ADVANTAGE MATRIX)
# ========================================================
POKEMON_TYPES = [
    "Normal", "Fire", "Water", "Grass", "Electric", "Ice",
    "Fighting", "Poison", "Ground", "Flying", "Psychic", "Bug",
    "Rock", "Ghost", "Dragon", "Steel", "Dark", "Fairy"
]

TYPE_ATTACK_CHART = {
    "Normal": {"Rock": 0.5, "Ghost": 0.0, "Steel": 0.5},
    "Fire": {"Fire": 0.5, "Water": 0.5, "Grass": 2.0, "Ice": 2.0, "Bug": 2.0, "Rock": 0.5, "Dragon": 0.5, "Steel": 2.0},
    "Water": {"Fire": 2.0, "Water": 0.5, "Grass": 0.5, "Ground": 2.0, "Rock": 2.0, "Dragon": 0.5},
    "Grass": {"Fire": 0.5, "Water": 2.0, "Grass": 0.5, "Poison": 0.5, "Ground": 2.0, "Flying": 0.5, "Bug": 0.5, "Rock": 2.0, "Dragon": 0.5, "Steel": 0.5},
    "Electric": {"Water": 2.0, "Electric": 0.5, "Grass": 0.5, "Ground": 0.0, "Flying": 2.0, "Dragon": 0.5},
    "Ice": {"Fire": 0.5, "Water": 0.5, "Grass": 2.0, "Ice": 0.5, "Ground": 2.0, "Flying": 2.0, "Dragon": 2.0, "Steel": 0.5},
    "Fighting": {"Normal": 2.0, "Ice": 2.0, "Poison": 0.5, "Flying": 0.5, "Psychic": 0.5, "Bug": 0.5, "Rock": 2.0, "Ghost": 0.0, "Dark": 2.0, "Steel": 2.0, "Fairy": 0.5},
    "Poison": {"Grass": 2.0, "Poison": 0.5, "Ground": 0.5, "Rock": 0.5, "Ghost": 0.5, "Steel": 0.0, "Fairy": 2.0},
    "Ground": {"Fire": 2.0, "Electric": 2.0, "Grass": 0.5, "Poison": 2.0, "Flying": 0.0, "Bug": 0.5, "Rock": 2.0, "Steel": 2.0},
    "Flying": {"Electric": 0.5, "Grass": 2.0, "Fighting": 2.0, "Bug": 2.0, "Rock": 0.5, "Steel": 0.5},
    "Psychic": {"Fighting": 2.0, "Poison": 2.0, "Psychic": 0.5, "Dark": 0.0, "Steel": 0.5},
    "Bug": {"Fire": 0.5, "Grass": 2.0, "Fighting": 0.5, "Poison": 0.5, "Flying": 0.5, "Psychic": 2.0, "Ghost": 0.5, "Dark": 2.0, "Steel": 0.5, "Fairy": 0.5},
    "Rock": {"Fire": 2.0, "Ice": 2.0, "Fighting": 0.5, "Ground": 0.5, "Flying": 2.0, "Bug": 2.0, "Steel": 0.5},
    "Ghost": {"Normal": 0.0, "Psychic": 2.0, "Ghost": 2.0, "Dark": 0.5},
    "Dragon": {"Dragon": 2.0, "Steel": 0.5, "Fairy": 0.0},
    "Steel": {"Fire": 0.5, "Water": 0.5, "Electric": 0.5, "Ice": 2.0, "Rock": 2.0, "Steel": 0.5, "Fairy": 2.0},
    "Dark": {"Fighting": 0.5, "Psychic": 2.0, "Ghost": 2.0, "Dark": 0.5, "Fairy": 0.5},
    "Fairy": {"Fire": 0.5, "Fighting": 2.0, "Poison": 0.5, "Dragon": 2.0, "Dark": 2.0, "Steel": 0.5}
}

def calculate_type_multiplier(atk_type: str, def_t1: str, def_t2: str = None) -> float:
    t1 = def_t1.title() if def_t1 else "Normal"
    m1 = TYPE_ATTACK_CHART.get(atk_type.title(), {}).get(t1, 1.0)
    m2 = 1.0
    if def_t2:
        t2 = def_t2.title()
        m2 = TYPE_ATTACK_CHART.get(atk_type.title(), {}).get(t2, 1.0)
    return m1 * m2

def get_super_effective_types(def_t1: str, def_t2: str = None) -> list[str]:
    valid = []
    for atk in POKEMON_TYPES:
        if calculate_type_multiplier(atk, def_t1, def_t2) > 1.0:
            valid.append(atk.lower())
    return valid

def get_resistant_immune_types(atk_type: str) -> list[str]:
    valid = []
    for def_t in POKEMON_TYPES:
        if calculate_type_multiplier(atk_type, def_t) < 1.0:
            valid.append(def_t.lower())
    return valid

async def cleanup_scribble_messages(bot: Bot, chat_id: int, game: dict):
    if "message_id" in game:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=game["message_id"])
        except Exception:
            pass
    if "hint_message_id" in game:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=game["hint_message_id"])
        except Exception:
            pass

async def cleanup_nameguess_messages(bot: Bot, chat_id: int, game: dict):
    if "message_id" in game:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=game["message_id"])
        except Exception:
            pass
    if "hint_message_id" in game:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=game["hint_message_id"])
        except Exception:
            pass

async def cleanup_silhouette_messages(bot: Bot, chat_id: int, game: dict):
    if "message_id" in game:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=game["message_id"])
        except Exception:
            pass
    if "hint_message_id" in game:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=game["hint_message_id"])
        except Exception:
            pass

async def cleanup_typematch_messages(bot: Bot, chat_id: int, game: dict):
    if "message_id" in game:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=game["message_id"])
        except Exception:
            pass
    if "hint_message_id" in game:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=game["hint_message_id"])
        except Exception:
            pass

async def cleanup_voltorb_messages(bot: Bot, chat_id: int, game: dict):
    if "message_id" in game:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=game["message_id"])
        except Exception:
            pass
    if "last_hint_msg_id" in game:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=game["last_hint_msg_id"])
        except Exception:
            pass

async def silhouette_timeout_task(chat_id: int, message_id: int, bot: Bot):
    await asyncio.sleep(60)
    if chat_id in active_games:
        game = active_games[chat_id]
        if game.get("type") == "silhouette" and game.get("message_id") == message_id:
            del active_games[chat_id]
            await cleanup_silhouette_messages(bot, chat_id, game)
            try:
                ans_name = game.get("pokemon_name") or game["answer"].title()
                msg = await bot.send_message(
                    chat_id=chat_id,
                    text=f"⏳ <b>Silhouette Simulation Expired!</b>\nThe wild Pokémon vanished back into the shadows.\n💡 The Pokémon was: <b>{ans_name}</b>",
                    parse_mode="HTML"
                )
                asyncio.create_task(delete_message_after(msg, 60))
            except Exception:
                pass

async def typematch_timeout_task(chat_id: int, message_id: int, bot: Bot):
    await asyncio.sleep(60)
    if chat_id in active_games:
        game = active_games[chat_id]
        if game.get("type") == "typematch" and game.get("message_id") == message_id:
            del active_games[chat_id]
            await cleanup_typematch_messages(bot, chat_id, game)
            try:
                ans_list = ", ".join(t.title() for t in game.get("valid_answers", []))
                msg = await bot.send_message(
                    chat_id=chat_id,
                    text=f"⏳ <b>Type Matchup Simulation Expired!</b>\nBattle Academy combat timer ended.\n💡 Valid Elemental Counters were: <b>{ans_list}</b>",
                    parse_mode="HTML"
                )
                asyncio.create_task(delete_message_after(msg, 60))
            except Exception:
                pass

async def voltorb_timeout_task(chat_id: int, message_id: int, bot: Bot):
    await asyncio.sleep(60)
    if chat_id in active_games:
        game = active_games[chat_id]
        if game.get("type") == "voltorb" and game.get("message_id") == message_id:
            del active_games[chat_id]
            await cleanup_voltorb_messages(bot, chat_id, game)
            try:
                msg = await bot.send_message(
                    chat_id=chat_id,
                    text=f"⏳ <b>Vault Security Lockdown!</b>\n💥 <i>BOOM! Voltorb detonated and sealed the terminal.</i>\n🔐 Correct Security PIN was: <code>{game['target']}</code>",
                    parse_mode="HTML"
                )
                asyncio.create_task(delete_message_after(msg, 60))
            except Exception:
                pass

async def delete_message_after(message: Message, delay: int):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass

async def scribble_timeout_task(chat_id: int, message_id: int, bot: Bot):
    await asyncio.sleep(60)
    if chat_id in active_games:
        game = active_games[chat_id]
        if game.get("type") == "scribble" and game.get("message_id") == message_id:
            del active_games[chat_id]
            await cleanup_scribble_messages(bot, chat_id, game)
            try:
                msg = await bot.send_message(
                    chat_id=chat_id,
                    text=f"⏳ <b>Time is up!</b> No one guessed the correct answer in time.\n💡 Correct Answer: <b>{game['answer'].title()}</b>",
                    parse_mode="HTML"
                )
                asyncio.create_task(delete_message_after(msg, 60))
            except Exception:
                pass
            
            # Automatically start next auto game if enabled
            if game.get("is_auto"):
                await asyncio.sleep(2)
                async with SessionLocal() as db:
                    try:
                        chat = await bot.get_chat(chat_id)
                        is_official = (chat.username and chat.username.lower() == "pokeempireunion")
                    except Exception:
                        is_official = False
                    
                    if is_official and chat_id not in active_games:
                        scrib_ok = is_scribble_enabled(chat_id)
                        nameg_ok = is_nameguess_enabled(chat_id)
                        if scrib_ok and nameg_ok:
                            if random.choice([True, False]):
                                await start_auto_nameguess_game(chat_id, bot, db)
                            else:
                                await start_auto_scribble_game(chat_id, bot, db)
                        elif scrib_ok:
                            await start_auto_scribble_game(chat_id, bot, db)
                        elif nameg_ok:
                            await start_auto_nameguess_game(chat_id, bot, db)

async def nameguess_timeout_task(chat_id: int, message_id: int, bot: Bot):
    await asyncio.sleep(60)
    if chat_id in active_games:
        game = active_games[chat_id]
        if game.get("type") == "nameguess" and game.get("message_id") == message_id:
            del active_games[chat_id]
            await cleanup_nameguess_messages(bot, chat_id, game)
            try:
                msg = await bot.send_message(
                    chat_id=chat_id,
                    text=f"⏳ <b>Time is up!</b> No one guessed the Pokémon in time.\n💡 Correct Answer: <b>{game['answer'].title()}</b>",
                    parse_mode="HTML"
                )
                asyncio.create_task(delete_message_after(msg, 60))
            except Exception:
                pass
            
            # Automatically start next auto game if enabled
            if game.get("is_auto"):
                await asyncio.sleep(2)
                async with SessionLocal() as db:
                    try:
                        chat = await bot.get_chat(chat_id)
                        is_official = (chat.username and chat.username.lower() == "pokeempireunion")
                    except Exception:
                        is_official = False
                    
                    if is_official and chat_id not in active_games:
                        scrib_ok = is_scribble_enabled(chat_id)
                        nameg_ok = is_nameguess_enabled(chat_id)
                        if scrib_ok and nameg_ok:
                            if random.choice([True, False]):
                                await start_auto_nameguess_game(chat_id, bot, db)
                            else:
                                await start_auto_scribble_game(chat_id, bot, db)
                        elif scrib_ok:
                            await start_auto_scribble_game(chat_id, bot, db)
                        elif nameg_ok:
                            await start_auto_nameguess_game(chat_id, bot, db)

async def start_auto_scribble_game(chat_id: int, bot: Bot, db: AsyncSession):
    # Set a synchronous lock to prevent overlapping auto-starts in the same chat
    active_games[chat_id] = {
        "type": "initializing",
        "created_at": time.time()
    }
    
    try:
        # Select random Pokémon
        stmt = select(Pokemon).order_by(func.random()).limit(1)
        res = await db.execute(stmt)
        pokemon = res.scalar_one_or_none()

        if not pokemon:
            # Clean up lock
            if chat_id in active_games and active_games[chat_id].get("type") == "initializing":
                del active_games[chat_id]
            return

        name = pokemon.name.lower()
        name_list = list(name)
        random.shuffle(name_list)
        scrambled = "".join(name_list)

        while scrambled == name and len(name) > 1:
            random.shuffle(name_list)
            scrambled = "".join(name_list)

        active_games[chat_id] = {
            "type": "scribble",
            "answer": name,
            "created_at": time.time(),
            "is_auto": True
        }

        # Format message in clean card style
        text = (
            f"💬 **Word Scramble!**\n"
            f"───────────────\n"
            f"🔀 **Scrambled**: `{scrambled.upper()}`\n"
            f"💰 **Reward**: `10-50 coins`\n"
            f"⌛ **Type the correct name! (60s)**"
        )
        
        # Add inline buttons
        builder = InlineKeyboardBuilder()
        builder.row(
            create_styled_button(text="🔍 Hint", key="hint", callback_data="scribble_hint"),
            create_styled_button(text="🚫 Stop Game", key="cancel", style="danger", callback_data="scribble_stop")
        )
        
        sent_msg = await bot.send_message(
            chat_id=chat_id,
            text=text,
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        
        active_games[chat_id]["message_id"] = sent_msg.message_id
        
        # Start background timeout task
        asyncio.create_task(scribble_timeout_task(chat_id, sent_msg.message_id, bot))
        
    except Exception as e:
        # Clean up lock on error
        if chat_id in active_games and active_games[chat_id].get("type") == "initializing":
            del active_games[chat_id]
        raise e

async def start_auto_nameguess_game(chat_id: int, bot: Bot, db: AsyncSession):
    active_games[chat_id] = {
        "type": "initializing",
        "created_at": time.time()
    }
    
    try:
        stmt = select(Pokemon).order_by(func.random()).limit(1)
        res = await db.execute(stmt)
        pokemon = res.scalar_one_or_none()

        if not pokemon:
            if chat_id in active_games and active_games[chat_id].get("type") == "initializing":
                del active_games[chat_id]
            return

        name = pokemon.name.lower()
        initial_hint = generate_hint(name)

        active_games[chat_id] = {
            "type": "nameguess",
            "answer": name,
            "pokemon_name": pokemon.name,
            "created_at": time.time(),
            "is_auto": True
        }

        type_info = f" | Type: <b>{pokemon.type1}{'/' + pokemon.type2 if pokemon.type2 else ''}</b>" if getattr(pokemon, 'type1', None) else ""
        gen_info = f" | Gen: <b>{pokemon.generation}</b>" if getattr(pokemon, 'generation', None) else ""

        text = (
            f"⚡ <b>POKÉMON NAME GUESS</b> ⚡\n"
            f"◈ ────────────────────────── ◈\n"
            f"🧠 <i>Who's That Pokémon?</i>\n\n"
            f"🔍 <b>Clue:</b> <code>{initial_hint}</code>{type_info}{gen_info}\n"
            f"⏳ <b>Time Limit:</b> <code>60 seconds</code>\n"
            f"🎁 <b>Reward:</b> <code>+150 to 250 coins</code>\n"
            f"◈ ────────────────────────── ◈\n"
            f"<i>Type the correct name in chat to win!</i>"
        )
        
        builder = InlineKeyboardBuilder()
        builder.row(
            create_styled_button(text="🔍 Get Hint", key="hint", callback_data="nameguess_hint"),
            create_styled_button(text="🚫 Stop Game", key="cancel", style="danger", callback_data="nameguess_stop")
        )
        
        sent_msg = await send_safe_media(
            bot=bot,
            chat_id=chat_id,
            media_type="photo",
            media_value=pokemon.image_url,
            caption=text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        
        active_games[chat_id]["message_id"] = sent_msg.message_id
        asyncio.create_task(nameguess_timeout_task(chat_id, sent_msg.message_id, bot))
        
    except Exception as e:
        if chat_id in active_games and active_games[chat_id].get("type") == "initializing":
            del active_games[chat_id]
        print(f"Error in start_auto_nameguess_game: {e}")

# Settings are now dynamically managed by utils.settings cache & DB

TRIVIA_QUESTIONS = [
    {
        "question": "What was Ash Ketchum's starter Pokémon in the anime?",
        "options": ["Pikachu", "Bulbasaur", "Charmander", "Squirtle"],
        "answer": "Pikachu"
    },
    {
        "question": "In which region did Ash Ketchum start his Pokémon journey?",
        "options": ["Kanto", "Johto", "Hoenn", "Sinnoh"],
        "answer": "Kanto"
    },
    {
        "question": "Who is the leader of the villainous Team Rocket in the anime?",
        "options": ["Giovanni", "Jessie", "James", "Butch"],
        "answer": "Giovanni"
    },
    {
        "question": "What is the name of Ash's first companion and Gym Leader of Cerulean City?",
        "options": ["Misty", "May", "Dawn", "Serena"],
        "answer": "Misty"
    },
    {
        "question": "Which Pokémon is known for singing to put everyone to sleep?",
        "options": ["Jigglypuff", "Clefairy", "Wigglytuff", "Chansey"],
        "answer": "Jigglypuff"
    },
    {
        "question": "What is the signature move of Ash's Pikachu?",
        "options": ["Thunderbolt", "Volt Tackle", "Iron Tail", "Electro Ball"],
        "answer": "Thunderbolt"
    },
    {
        "question": "Which legendary Pokémon did Ash see on his very first day as a trainer?",
        "options": ["Ho-Oh", "Lugia", "Articuno", "Mewtwo"],
        "answer": "Ho-Oh"
    },
    {
        "question": "What is Brock's signature rock Pokémon in the Kanto region?",
        "options": ["Onix", "Geodude", "Rhyhorn", "Kabuto"],
        "answer": "Onix"
    },
    {
        "question": "Which Pokémon is known as the 'Lizard Pokémon' and is Fire-type?",
        "options": ["Charmander", "Charmeleon", "Charizard", "Salandit"],
        "answer": "Charmander"
    },
    {
        "question": "Who was Ash Ketchum's main childhood rival from Pallet Town?",
        "options": ["Gary Oak", "Paul", "Trip", "Gladion"],
        "answer": "Gary Oak"
    },
    {
        "question": "What item does Ash use to Mega Evolve his Lucario in Pokémon Journeys?",
        "options": ["Key Stone", "Mega Ring", "Mega Glove", "Mega Bracelet"],
        "answer": "Key Stone"
    },
    {
        "question": "Which Pokémon was Ash's first Kanto capture (excluding Pikachu)?",
        "options": ["Caterpie", "Pidgeotto", "Bulbasaur", "Charmander"],
        "answer": "Caterpie"
    },
    {
        "question": "Which Pokémon did Ash temporarily trade his Butterfree for?",
        "options": ["Raticate", "Pidgeot", "Beedrill", "Primeape"],
        "answer": "Raticate"
    },
    {
        "question": "What is Brock's ultimate dream career path in the anime?",
        "options": ["Pokémon Doctor", "Pokémon Breeder", "Gym Leader", "Pokémon Master"],
        "answer": "Pokémon Doctor"
    },
    {
        "question": "What is the name of the group of rogue Squirtle Ash befriended?",
        "options": ["Squirtle Squad", "Shell Shockers", "Water Warriors", "Blue Blast"],
        "answer": "Squirtle Squad"
    },
    {
        "question": "Who is Ash's main rival during his journey in Sinnoh?",
        "options": ["Paul", "Gary Oak", "Trip", "Barry"],
        "answer": "Paul"
    },
    {
        "question": "What is the national Pokédex number of Pikachu?",
        "options": ["#025", "#001", "#150", "#133"],
        "answer": "#025"
    },
    {
        "question": "Which mythical Pokémon sleeps for 1,000 years and wakes for only 7 days?",
        "options": ["Jirachi", "Celebi", "Mew", "Manaphy"],
        "answer": "Jirachi"
    },
    {
        "question": "Which regional Pokémon League was Ash's first official Championship win?",
        "options": ["Alola League", "Indigo League", "Sinnoh League", "Kalos League"],
        "answer": "Alola League"
    },
    {
        "question": "Which companion of Ash is known for cooking and Brock's younger siblings?",
        "options": ["Brock", "Cilan", "Clemont", "Tracy"],
        "answer": "Brock"
    },
    {
        "question": "Jessie from Team Rocket accidentally traded her Lickitung for which Pokémon?",
        "options": ["Wobbuffet", "Meowth", "Arbok", "Seviper"],
        "answer": "Wobbuffet"
    },
    {
        "question": "On which island did Mewtwo build his castle in the first Pokémon movie?",
        "options": ["New Island", "Cinnabar Island", "Faraway Island", "Pallet Island"],
        "answer": "New Island"
    },
    {
        "question": "Which female companion of Ash became a famous Pokémon Coordinator?",
        "options": ["May", "Serena", "Iris", "Lillie"],
        "answer": "May"
    },
    {
        "question": "Which Pokémon is famously known for carrying a leek stalk?",
        "options": ["Farfetch'd", "Psyduck", "Doduo", "Pidgey"],
        "answer": "Farfetch'd"
    },
    {
        "question": "Which Pokémon does Professor Oak give to Ash because he woke up late?",
        "options": ["Pikachu", "Bulbasaur", "Charmander", "Squirtle"],
        "answer": "Pikachu"
    },
    {
        "question": "Which Pokémon type is completely immune to Electric-type moves?",
        "options": ["Ground", "Rock", "Steel", "Grass"],
        "answer": "Ground"
    },
    {
        "question": "Which evolved form of Eevee is a Fairy-type Pokémon?",
        "options": ["Sylveon", "Espeon", "Umbreon", "Glaceon"],
        "answer": "Sylveon"
    },
    {
        "question": "Who is the Pokémon mascot of Team Rocket's primary trio?",
        "options": ["Meowth", "Wobbuffet", "Weezing", "Arbok"],
        "answer": "Meowth"
    },
    {
        "question": "Who is the Pokémon Professor of the Sinnoh region?",
        "options": ["Professor Rowan", "Professor Oak", "Professor Elm", "Professor Birch"],
        "answer": "Professor Rowan"
    },
    {
        "question": "Who is Ash Ketchum's primary rival in the Unova region?",
        "options": ["Trip", "Paul", "Gary Oak", "Barry"],
        "answer": "Trip"
    },
    {
        "question": "Which legendary Pokémon did Ash ride and summon in the Alola region?",
        "options": ["Solgaleo", "Lunala", "Necrozma", "Tapu Koko"],
        "answer": "Solgaleo"
    },
    {
        "question": "What special Z-Move can Ash's Pikachu use with Ash's cap?",
        "options": ["10,000,000 Volt Thunderbolt", "Catastropika", "Gigavolt Havoc", "Stoked Sparksurfer"],
        "answer": "10,000,000 Volt Thunderbolt"
    },
    {
        "question": "What is the unique battle bond form of Ash's Greninja called?",
        "options": ["Ash-Greninja", "Mega Greninja", "Primal Greninja", "Bond Greninja"],
        "answer": "Ash-Greninja"
    },
    {
        "question": "Which Pokémon did James purchase from a shady salesman on the St. Anne?",
        "options": ["Magikarp", "Gyreados", "Chimecho", "Growlithe"],
        "answer": "Magikarp"
    },
    {
        "question": "Who is the Ghost-type Gym Leader of Ecruteak City in Johto?",
        "options": ["Morty", "Falkner", "Bugsy", "Chuck"],
        "answer": "Morty"
    },
    {
        "question": "Which Pokémon is classified as the 'Genetic Pokémon' in the Pokédex?",
        "options": ["Mewtwo", "Mew", "Deoxys", "Genesect"],
        "answer": "Mewtwo"
    },
    {
        "question": "Which fossil Pokémon did Ash awaken in Grampa Canyon?",
        "options": ["Aerodactyl", "Omanyte", "Kabuto", "Cradily"],
        "answer": "Aerodactyl"
    },
    {
        "question": "Where did Ash leave his Charizard to train and become stronger?",
        "options": ["Charicific Valley", "Cinnabar Island", "Cerulean Gym", "Professor Oak's Lab"],
        "answer": "Charicific Valley"
    },
    {
        "question": "What type of Gym does Lt. Surge run in Vermilion City?",
        "options": ["Electric", "Steel", "Rock", "Fighting"],
        "answer": "Electric"
    },
    {
        "question": "Which Pokémon has cannons on its shell to blast water?",
        "options": ["Blastoise", "Wartortle", "Feraligatr", "Gyarados"],
        "answer": "Blastoise"
    },
    {
        "question": "What is the name of Ash Ketchum's mother in the anime?",
        "options": ["Delia", "Daisy", "Caroline", "Johanna"],
        "answer": "Delia"
    },
    {
        "question": "How did Ash evolve his Pikachu in the anime?",
        "options": ["Pikachu refused to evolve", "Using a Thunder Stone", "By leveling up to 100", "Trading with Gary"],
        "answer": "Pikachu refused to evolve"
    },
    {
        "question": "Which Pokémon region is heavily inspired by France?",
        "options": ["Kalos", "Unova", "Alola", "Galar"],
        "answer": "Kalos"
    },
    {
        "question": "Who is the Grass-type Gym Leader of Celadon City?",
        "options": ["Erika", "Sabrina", "Misty", "Whitney"],
        "answer": "Erika"
    },
    {
        "question": "Which starter Pokémon did Dawn choose in the Sinnoh region?",
        "options": ["Piplup", "Turtwig", "Chimchar", "Pikachu"],
        "answer": "Piplup"
    },
    {
        "question": "Which Pokémon did Ash release to protect wild Pidgey from a Fearow?",
        "options": ["Pidgeot", "Butterfree", "Lapras", "Greninja"],
        "answer": "Pidgeot"
    },
    {
        "question": "Who is the undefeated Champion of the Galar region?",
        "options": ["Leon", "Lance", "Steven", "Cynthia"],
        "answer": "Leon"
    },
    {
        "question": "What is the name of Ash Ketchum's hometown in Kanto?",
        "options": ["Pallet Town", "Viridian City", "Pewter City", "Cerulean City"],
        "answer": "Pallet Town"
    },
    {
        "question": "Which Pokémon belonging to James always bites his head affectionately?",
        "options": ["Carnivine", "Victreebel", "Cacnea", "Chimecho"],
        "answer": "Carnivine"
    },
    {
        "question": "What legendary Pokémon is associated with the mysterious GS Ball?",
        "options": ["Celebi", "Lugia", "Ho-Oh", "Mew"],
        "answer": "Celebi"
    },
    {
        "question": "Who is the Champion of the Sinnoh region League?",
        "options": ["Cynthia", "Diantha", "Iris", "Steven"],
        "answer": "Cynthia"
    },
    {
        "question": "Which Pokémon is the fully evolved form of Dragonair?",
        "options": ["Dragonite", "Salamence", "Garchomp", "Hydreigon"],
        "answer": "Dragonite"
    }
]

async def trivia_timeout_task(chat_id: int, message_id: int, bot: Bot):
    await asyncio.sleep(60)
    if chat_id in active_games:
        game = active_games[chat_id]
        if game.get("type") == "trivia" and game.get("message_id") == message_id:
            del active_games[chat_id]
            try:
                escaped_q = html.escape(game['question'])
                escaped_ans = html.escape(game['answer'])
                text = (
                    f"⏳ <b>TRIVIA EXPIRED</b> ⏳\n"
                    f"───────────────\n\n"
                    f"<b>Question:</b>\n"
                    f"{escaped_q}\n\n"
                    f"❌ Time is up! No one answered in time.\n"
                    f"💡 Correct Answer: <b>{escaped_ans}</b>"
                )
                msg = await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=None,
                    parse_mode="HTML"
                )
                asyncio.create_task(delete_message_after(msg, 60))
            except Exception as e:
                print(f"Error editing trivia timeout message: {e}")

async def initiate_trivia_game(chat_id: int, db: AsyncSession, is_auto: bool = False) -> Optional[Tuple[str, InlineKeyboardMarkup]]:
    """Starts a trivia game logic and returns the formatted question text and reply markup, or None on error."""
    if not TRIVIA_QUESTIONS:
        return None

    q_data = random.choice(TRIVIA_QUESTIONS)
    
    # Shuffle options
    options = list(q_data["options"])
    random.shuffle(options)

    active_games[chat_id] = {
        "type": "trivia",
        "question": q_data["question"],
        "options": options,
        "answer": q_data["answer"],
        "created_at": time.time(),
        "is_auto": is_auto,
        "guesses": set()
    }

    builder = InlineKeyboardBuilder()
    for idx, opt in enumerate(options):
        builder.button(text=opt, callback_data=f"trivia_ans_{idx}")
    builder.adjust(1) # 1 button per row

    escaped_q = html.escape(q_data["question"])
    text = (
        f"❓ <b>POKÉMON TRIVIA</b> ❓\n"
        f"───────────────\n\n"
        f"<b>Question:</b>\n"
        f"{escaped_q}\n\n"
        f"👉 Select the correct option below! You get only <b>one guess</b>! (Ends in 60s)"
    )
    return text, builder.as_markup()

@router.message(Command("trivia"))
async def cmd_trivia(message: Message, db: AsyncSession):
    if message.chat.type == "private":
        await message.answer(GROUP_ONLY_GAMES_NOTICE, reply_markup=get_official_group_keyboard(), parse_mode="HTML")
        return

    chat_id = message.chat.id
    user_id = message.from_user.id

    # Enforce 15-minute cooldown per trainer
    now = time.time()
    if user_id in last_trivia_time:
        elapsed = now - last_trivia_time[user_id]
        if elapsed < 900:  # 15 minutes = 900 seconds
            remaining = int(900 - elapsed)
            minutes = remaining // 60
            seconds = remaining % 60
            await message.answer(f"⏳ **Trivia Cooldown!** You can use `/trivia` again in **{minutes}m {seconds}s**.")
            return

    if chat_id in active_games:
        game = active_games[chat_id]
        # Only allow preempting/overwriting the active game if it's an automatic scribble game
        if game.get("type") == "trivia" or not game.get("is_auto"):
            await message.answer("⚠️ There is already an active trivia game in this chat! Answer it first.")
            return

    res = await initiate_trivia_game(chat_id, db, is_auto=False)
    if not res:
        await message.answer("❌ Error initiating trivia. Try again.")
        return

    trivia_text, reply_markup = res

    # Set trainer cooldown
    last_trivia_time[user_id] = time.time()
    sent_msg = await message.answer(trivia_text, reply_markup=reply_markup, parse_mode="HTML")
    active_games[chat_id]["message_id"] = sent_msg.message_id
    asyncio.create_task(trivia_timeout_task(chat_id, sent_msg.message_id, message.bot))

@router.message(Command("scribble"))
@router.message(Command("unscramble"))
async def cmd_scribble(message: Message, db: AsyncSession):
    if message.chat.type == "private":
        await message.answer(GROUP_ONLY_GAMES_NOTICE, reply_markup=get_official_group_keyboard(), parse_mode="HTML")
        return

    chat_id = message.chat.id

    if chat_id in active_games:
        await message.answer("⚠️ There is already an active trivia or scribble game in this chat! Answer it first.")
        return

    # Select random Pokémon
    stmt = select(Pokemon).order_by(func.random()).limit(1)
    res = await db.execute(stmt)
    pokemon = res.scalar_one_or_none()

    if not pokemon:
        await message.answer("❌ Error initiating scribble. Try again.")
        return

    name = pokemon.name.lower()
    name_list = list(name)
    random.shuffle(name_list)
    scrambled = "".join(name_list)

    while scrambled == name and len(name) > 1:
        random.shuffle(name_list)
        scrambled = "".join(name_list)

    active_games[chat_id] = {
        "type": "scribble",
        "answer": name,
        "created_at": time.time(),
        "is_auto": False
    }

    text = (
        f"💬 **Word Scramble!**\n"
        f"───────────────\n"
        f"🔀 **Scrambled**: `{scrambled.upper()}`\n"
        f"💰 **Reward**: `100 coins`\n"
        f"⌛ **Type the correct name! (60s)**"
    )

    # Add inline buttons
    builder = InlineKeyboardBuilder()
    builder.row(
        create_styled_button(text="🔍 Hint", key="hint", callback_data="scribble_hint"),
        create_styled_button(text="🚫 Stop Game", key="cancel", style="danger", callback_data="scribble_stop")
    )

    sent_msg = await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    active_games[chat_id]["message_id"] = sent_msg.message_id

    # Start background timeout task
    asyncio.create_task(scribble_timeout_task(chat_id, sent_msg.message_id, message.bot))

# Custom filter to check if there is an active game in the chat
def has_active_game(message: Message) -> bool:
    return message.chat.id in active_games

# Message handler to check active game answers (excluding commands)
@router.message(F.text, ~F.text.startswith("/"), has_active_game)
async def check_game_answers(message: Message, db: AsyncSession):
    chat_id = message.chat.id
    game = active_games[chat_id]

    # Ignore checks if the game state is in initializing lock
    if game.get("type") == "initializing":
        return

    # Check timeout (60 seconds)
    if time.time() - game["created_at"] > 60:
        return

    # For trivia, we ignore text guesses entirely as we now use buttons
    if game["type"] == "trivia":
        return

    # Handle Voltorb Lock Guessing
    if game["type"] == "voltorb":
        guess_text = message.text.strip()
        if not guess_text.isdigit():
            return
        guess_num = int(guess_text)
        target = game["target"]
        
        if guess_num == target:
            from aiogram.types import ReactionTypeEmoji
            try:
                await message.react(reaction=[ReactionTypeEmoji(emoji="🎉")])
            except Exception:
                pass

            user_id = message.from_user.id
            stmt = select(User).where(User.id == user_id)
            res = await db.execute(stmt)
            user = res.scalar_one_or_none()
            if not user:
                user = User(id=user_id, username=message.from_user.username, nickname=message.from_user.first_name)
                db.add(user)
                await db.flush()

            attempts_used = game["attempts"] + 1
            reward = max(150, (game["max_attempts"] - attempts_used + 1) * 150)
            user.coins += reward
            try:
                from utils.trainer_level import log_transaction
                await log_transaction(user_id, reward, "VOLTORB_WIN", f"Disarmed Voltorb Security PIN ({target})", db)
            except Exception:
                pass
            await db.commit()

            del active_games[chat_id]
            await cleanup_voltorb_messages(message.bot, chat_id, game)

            victory_text = (
                f"🎉 <b>VAULT UNLOCKED & DISARMED!</b> 🎉\n"
                f"───────────────\n"
                f"<blockquote>🔐 <b>Security PIN</b>: <code>{target}</code>\n"
                f"⚡ <b>Attempts</b>: <b>{attempts_used}/{game['max_attempts']}</b>\n"
                f"💰 <b>Reward</b>: <b>+{reward} coins</b>\n"
                f"👥 <b>Hacker</b>: {message.from_user.mention_html()}</blockquote>"
            )
            v_msg = await message.reply(victory_text, parse_mode="HTML")
            asyncio.create_task(delete_message_after(v_msg, 60))
            return
        elif guess_num < target:
            game["attempts"] += 1
            game["low_bound"] = max(game["low_bound"], guess_num + 1)
            if game["attempts"] >= game["max_attempts"]:
                del active_games[chat_id]
                await cleanup_voltorb_messages(message.bot, chat_id, game)
                boom_text = (
                    f"💥 <b>BOOM! VOLTORB SELF-DESTRUCTED!</b> 💥\n"
                    f"───────────────\n"
                    f"<blockquote>❌ <b>Security Breach Failed!</b> Max attempts (6/6) reached.\n"
                    f"🔐 <b>The correct PIN was</b>: <code>{target}</code></blockquote>"
                )
                b_msg = await message.reply(boom_text, parse_mode="HTML")
                asyncio.create_task(delete_message_after(b_msg, 60))
                return
            else:
                rem = game["max_attempts"] - game["attempts"]
                h_text = f"🔺 <b>HIGHER!</b> | Range: <code>[{game['low_bound']} – {game['high_bound']}]</code> | Attempts left: <b>{rem}</b>"
                h_msg = await message.reply(h_text, parse_mode="HTML")
                game["last_hint_msg_id"] = h_msg.message_id
                asyncio.create_task(delete_message_after(h_msg, 15))
                return
        else: # guess_num > target
            game["attempts"] += 1
            game["high_bound"] = min(game["high_bound"], guess_num - 1)
            if game["attempts"] >= game["max_attempts"]:
                del active_games[chat_id]
                await cleanup_voltorb_messages(message.bot, chat_id, game)
                boom_text = (
                    f"💥 <b>BOOM! VOLTORB SELF-DESTRUCTED!</b> 💥\n"
                    f"───────────────\n"
                    f"<blockquote>❌ <b>Security Breach Failed!</b> Max attempts (6/6) reached.\n"
                    f"🔐 <b>The correct PIN was</b>: <code>{target}</code></blockquote>"
                )
                b_msg = await message.reply(boom_text, parse_mode="HTML")
                asyncio.create_task(delete_message_after(b_msg, 60))
                return
            else:
                rem = game["max_attempts"] - game["attempts"]
                h_text = f"🔻 <b>LOWER!</b> | Range: <code>[{game['low_bound']} – {game['high_bound']}]</code> | Attempts left: <b>{rem}</b>"
                h_msg = await message.reply(h_text, parse_mode="HTML")
                game["last_hint_msg_id"] = h_msg.message_id
                asyncio.create_task(delete_message_after(h_msg, 15))
                return

    # Handle Type Matchup Blitz Guessing
    if game["type"] == "typematch":
        guess_raw = message.text.strip().lower()
        valid_answers = game.get("valid_answers", [])
        if guess_raw in valid_answers:
            from aiogram.types import ReactionTypeEmoji
            try:
                await message.react(reaction=[ReactionTypeEmoji(emoji="🎉")])
            except Exception:
                pass

            user_id = message.from_user.id
            nickname = message.from_user.first_name

            stmt = select(User).where(User.id == user_id)
            res = await db.execute(stmt)
            user = res.scalar_one_or_none()

            if not user:
                user = User(id=user_id, username=message.from_user.username, nickname=nickname)
                db.add(user)
                await db.flush()

            reward = random.randint(350, 500)
            user.coins += reward
            try:
                from utils.trainer_level import log_transaction
                await log_transaction(user_id, reward, "TYPEMATCH_WIN", f"Won Type Matchup Blitz ({guess_raw.title()})", db)
            except Exception:
                pass

            await db.commit()

            del active_games[chat_id]
            await cleanup_typematch_messages(message.bot, chat_id, game)

            all_valid_str = ", ".join(t.title() for t in valid_answers)
            vic_card = (
                f"⚡ <b>ELEMENTAL ADVANTAGE STRUCK!</b> ⚡\n"
                f"◈ ────────────────────────── ◈\n"
                f"🎯 <b>Winning Counter:</b> <b>{guess_raw.title()}</b>\n"
                f"💡 <b>All Valid Types:</b> <code>{all_valid_str}</code>\n"
                f"💰 <b>Earned:</b> <b>+{reward} coins</b>\n"
                f"👥 <b>Master Tactician:</b> {message.from_user.mention_html()}\n"
                f"◈ ────────────────────────── ◈"
            )
            v_msg = await message.reply(vic_card, parse_mode="HTML")
            asyncio.create_task(delete_message_after(v_msg, 60))
            return
        else:
            return

    # Handle Text Guess Matching (Scribble, Nameguess, Silhouette)
    import re
    def normalize_poke_name(val: str) -> str:
        return re.sub(r'[^a-z0-9]', '', val.lower())

    guess = message.text.strip().lower()
    correct_answer = game["answer"].lower()

    norm_guess = normalize_poke_name(guess)
    norm_correct = normalize_poke_name(correct_answer)
    norm_base = normalize_poke_name(correct_answer.split('-')[0])

    is_match = (
        guess == correct_answer or
        (norm_guess and norm_guess == norm_correct) or
        (len(norm_guess) >= 3 and norm_guess == norm_base)
    )

    if is_match:
        from aiogram.types import ReactionTypeEmoji
        try:
            await message.react(reaction=[ReactionTypeEmoji(emoji="🎉")])
        except Exception as e:
            print(f"Failed to react to game guess: {e}")

        user_id = message.from_user.id
        nickname = message.from_user.first_name

        stmt = select(User).where(User.id == user_id)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()

        if not user:
            user = User(id=user_id, username=message.from_user.username, nickname=nickname)
            db.add(user)
            await db.flush()

        gtype = game.get("type")
        if gtype == "silhouette":
            reward = random.randint(250, 450)
        elif gtype == "nameguess":
            if message.chat.type in ["group", "supergroup"] and game.get("is_auto"):
                reward = random.randint(150, 250)
            else:
                reward = 200
        else: # scribble
            if message.chat.type in ["group", "supergroup"] and game.get("is_auto"):
                reward = random.randint(60, 100)
            else:
                reward = 150

        user.coins += reward
        try:
            from utils.trainer_level import log_transaction
            await log_transaction(user_id, reward, f"{gtype.upper()}_WIN", f"Won {gtype.title()} ({correct_answer.title()})", db)
        except Exception:
            pass

        await db.commit()

        del active_games[chat_id]
        if gtype == "silhouette":
            await cleanup_silhouette_messages(message.bot, chat_id, game)
        elif gtype == "nameguess":
            await cleanup_nameguess_messages(message.bot, chat_id, game)
        else:
            await cleanup_scribble_messages(message.bot, chat_id, game)

        ans_display = game.get("pokemon_name") or game.get("display_name") or correct_answer.title()
        if gtype == "silhouette":
            text = (
                f"🎉 <b>SILHOUETTE IDENTIFIED!</b> 🎉\n"
                f"───────────────\n"
                f"<blockquote>👤 <b>Pokémon</b>: <b>{ans_display}</b>\n"
                f"💰 <b>Earned</b>: <b>+{reward} coins</b>\n"
                f"👥 <b>Field Master</b>: {message.from_user.mention_html()}</blockquote>"
            )
        elif gtype == "nameguess":
            text = (
                f"🎉 <b>Correct!</b>\n"
                f"───────────────\n"
                f"<blockquote>🧠 <b>Pokémon</b>: <b>{ans_display}</b>\n"
                f"💰 <b>Earned</b>: <b>+{reward} coins</b>\n"
                f"👥 <b>Winner</b>: {message.from_user.mention_html()}</blockquote>"
            )
        else:
            text = (
                f"🎉 <b>Correct!</b>\n"
                f"───────────────\n"
                f"<blockquote>🛑 <b>Word</b>: <b>{ans_display}</b>\n"
                f"💰 <b>Earned</b>: <b>+{reward} coins</b>\n"
                f"👥 <b>Winner</b>: {message.from_user.mention_html()}</blockquote>"
            )

        victory_msg = await message.reply(text, parse_mode="HTML")
        asyncio.create_task(delete_message_after(victory_msg, 60))

        # Automatically start another game in group chats if enabled
        if message.chat.type in ["group", "supergroup"] and message.chat.username and message.chat.username.lower() == "pokeempireunion":
            await asyncio.sleep(2)
            if chat_id not in active_games:
                scrib_ok = is_scribble_enabled(chat_id)
                nameg_ok = is_nameguess_enabled(chat_id)
                if scrib_ok and nameg_ok:
                    if random.choice([True, False]):
                        await start_auto_nameguess_game(chat_id, message.bot, db)
                    else:
                        await start_auto_scribble_game(chat_id, message.bot, db)
                elif scrib_ok:
                    await start_auto_scribble_game(chat_id, message.bot, db)
                elif nameg_ok:
                    await start_auto_nameguess_game(chat_id, message.bot, db)

# Automatically start a scribble/nameguess game when conversation happens in group chat with no active game
def no_active_game_in_group(message: Message) -> bool:
    if message.chat.type not in ["group", "supergroup"]:
        return False
    if not message.chat.username or message.chat.username.lower() != "pokeempireunion":
        return False
    chat_id = message.chat.id
    return (chat_id not in active_games and 
            (is_scribble_enabled(chat_id) or is_nameguess_enabled(chat_id)))

@router.message(F.text, ~F.text.startswith("/"), no_active_game_in_group)
async def auto_start_scribble(message: Message, db: AsyncSession):
    chat_id = message.chat.id
    scrib_ok = is_scribble_enabled(chat_id)
    nameg_ok = is_nameguess_enabled(chat_id)
    
    if scrib_ok and nameg_ok:
        if random.choice([True, False]):
            await start_auto_nameguess_game(chat_id, message.bot, db)
        else:
            await start_auto_scribble_game(chat_id, message.bot, db)
    elif scrib_ok:
        await start_auto_scribble_game(chat_id, message.bot, db)
    elif nameg_ok:
        await start_auto_nameguess_game(chat_id, message.bot, db)

@router.callback_query(F.data == "dm_games")
async def cb_dm_games(callback: CallbackQuery, db: AsyncSession):
    text = (
        f"🎮 **GAMES CENTER** 🎮\n"
        f"───────────────\n\n"
        f"Earn coins and have fun with these games:\n\n"
        f"📅 **Daily Reward** — claim every 24h\n"
        f"🎡 **Lucky Spin** — spin every 4h\n"
        f"🪙 **Coinflip**: `/coinflip <bet> <heads/tails>`\n"
        f"✊ **Rock-Paper-Scissors**: `/rps <bet> <rock/paper/scissors>`\n"
        f"✏️ **Pokémon Scribble**: Unscramble species names!\n"
        f"💣 **Mines**: `/mines <bet> [mines]` (avoid mines in 5x5 grid!)\n"
        f"───────────────"
    )
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="📅 Claim Daily", callback_data="play_daily"),
        InlineKeyboardButton(text="🎡 Lucky Spin", callback_data="play_spin")
    )
    builder.row(
        InlineKeyboardButton(text="❓ Start Trivia", callback_data="play_trivia"),
        InlineKeyboardButton(text="✏️ Start Scribble", callback_data="play_scribble")
    )
    builder.row(
        InlineKeyboardButton(text="💣 Start Mines", callback_data="play_mines"),
        InlineKeyboardButton(text="🔙 Back to Hub Menu", callback_data="dm_home")
    )
    
    try:
        await callback.message.edit_caption(caption=text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    except Exception:
        try:
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        except Exception:
            pass
    await callback.answer()

@router.callback_query(F.data == "play_mines")
async def cb_play_mines(callback: CallbackQuery):
    await callback.answer()
    if callback.message.chat.type == "private":
        await callback.message.answer(GROUP_ONLY_GAMES_NOTICE, reply_markup=get_official_group_keyboard(), parse_mode="HTML")
        return
    text = (
        f"💣 **MINES GAME** 💣\n"
        f"───────────────\n"
        f"Test your luck in a 5x5 grid! Place a bet, choose how many mines (1-24) to hide, and reveal tiles. "
        f"Each diamond you find increases your multiplier. Cash out before hitting a mine!\n\n"
        f"👉 **To start playing, send**:\n"
        f"• `/mines <bet> [mines_count]` in group\n"
        f"  _(e.g. <code>/mines 100 3</code> starts a game with a 100 coin bet and 3 hidden mines)_\n\n"
        f"⚠️ Default mines count is 3. Bets must be between 10 and 100,000 coins."
    )
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Back to Games", callback_data="dm_games"))
    try:
        await callback.message.edit_caption(caption=text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        try:
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception:
            pass

@router.callback_query(F.data == "play_daily")
async def cb_play_daily(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id
    nickname = callback.from_user.first_name

    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user:
        user = User(id=user_id, username=callback.from_user.username, nickname=nickname)
        db.add(user)
        await db.flush()

    now = datetime.utcnow()
    if user.last_daily_at:
        cooldown = timedelta(hours=24)
        elapsed = now - user.last_daily_at
        if elapsed < cooldown:
            remaining = cooldown - elapsed
            hours, remainder = divmod(remaining.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_str = f"{hours}h {minutes}m {seconds}s"
            await callback.answer(f"⏳ Daily reward available in {time_str}!", show_alert=True)
            return

    reward = random.randint(200, 500)
    user.coins += reward
    user.last_daily_at = now
    await db.commit()

    text = (
        f"📅 **DAILY REWARD** 📅\n"
        f"───────────────\n"
        f"Trainer **{escape_md(user.nickname)}** successfully claimed their daily reward:\n"
        f"💰 **+{reward} coins**!\n\n"
        f"Balance: 💰 **{user.coins} coins**.\n"
        f"───────────────"
    )
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Back to Games", callback_data="dm_games"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer("Daily reward claimed!")

@router.callback_query(F.data == "play_spin")
async def cb_play_spin(callback: CallbackQuery, db: AsyncSession):
    await callback.answer()
    if callback.message.chat.type == "private":
        await callback.message.answer(GROUP_ONLY_GAMES_NOTICE, reply_markup=get_official_group_keyboard(), parse_mode="HTML")
        return
    user_id = callback.from_user.id
    nickname = callback.from_user.first_name

    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user:
        user = User(id=user_id, username=callback.from_user.username, nickname=nickname)
        db.add(user)
        await db.flush()

    now = datetime.utcnow()
    if user.last_spin_at:
        cooldown = timedelta(hours=4)
        elapsed = now - user.last_spin_at
        if elapsed < cooldown:
            remaining = cooldown - elapsed
            hours, remainder = divmod(remaining.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_str = f"{hours}h {minutes}m {seconds}s"
            await callback.answer(f"⏳ Lucky spin available in {time_str}!", show_alert=True)
            return

    rewards = [50, 100, 150, 200, 300, 500]
    weights = [40, 30, 15, 10, 4, 1]
    won = random.choices(rewards, weights=weights, k=1)[0]

    user.coins += won
    user.last_spin_at = now
    await db.commit()

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Back to Games", callback_data="dm_games"))

    wheels = [
        "🎡 **LUCKY SPIN WHEEL** 🎡\n───────────────\nSpinning... 🎰 [ 🔴 | 🟡 | 🟢 | 🔵 ]",
        "🎡 **LUCKY SPIN WHEEL** 🎡\n───────────────\nSpinning... 🎰 [ 50 | 150 | 500 ]",
        f"🎡 **LUCKY SPIN RESULT** 🎡\n───────────────\n"
        f"🎉 **STAY!** 🎉\n\n"
        f"Trainer **{escape_md(user.nickname)}** spun the wheel and won:\n"
        f"💰 **+{won} coins**!\n\n"
        f"Balance: 💰 **{user.coins} coins**.\n"
        f"───────────────"
    ]
    
    await callback.message.edit_text(wheels[0], parse_mode="Markdown")
    await asyncio.sleep(0.5)
    await callback.message.edit_text(wheels[1], parse_mode="Markdown")
    await asyncio.sleep(0.5)
    await callback.message.edit_text(wheels[2], reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer("Lucky spin complete!")

@router.callback_query(F.data == "play_trivia")
async def cb_play_trivia(callback: CallbackQuery, db: AsyncSession):
    await callback.answer()
    if callback.message.chat.type == "private":
        await callback.message.answer(GROUP_ONLY_GAMES_NOTICE, reply_markup=get_official_group_keyboard(), parse_mode="HTML")
        return
    chat_id = callback.message.chat.id

    if chat_id in active_games:
        await callback.answer("⚠️ An active game is already running in this chat!", show_alert=True)
        return

    res = await initiate_trivia_game(chat_id, db, is_auto=False)
    if not res:
        await callback.answer("❌ Error initiating trivia.", show_alert=True)
        return

    trivia_text, reply_markup = res

    sent_msg = await callback.message.answer(trivia_text, reply_markup=reply_markup, parse_mode="HTML")
    active_games[chat_id]["message_id"] = sent_msg.message_id
    await callback.answer("Trivia started!")
    asyncio.create_task(trivia_timeout_task(chat_id, sent_msg.message_id, callback.bot))

@router.callback_query(F.data == "play_scribble")
async def cb_play_scribble(callback: CallbackQuery, db: AsyncSession):
    await callback.answer()
    if callback.message.chat.type == "private":
        await callback.message.answer(GROUP_ONLY_GAMES_NOTICE, reply_markup=get_official_group_keyboard(), parse_mode="HTML")
        return
    chat_id = callback.message.chat.id

    if chat_id in active_games:
        await callback.answer("⚠️ An active game is already running in this chat!", show_alert=True)
        return

    # Select random Pokémon
    stmt = select(Pokemon).order_by(func.random()).limit(1)
    res = await db.execute(stmt)
    pokemon = res.scalar_one_or_none()

    if not pokemon:
        await callback.answer("❌ Error initiating scribble.", show_alert=True)
        return

    name = pokemon.name.lower()
    name_list = list(name)
    random.shuffle(name_list)
    scrambled = "".join(name_list)

    while scrambled == name and len(name) > 1:
        random.shuffle(name_list)
        scrambled = "".join(name_list)

    active_games[chat_id] = {
        "type": "scribble",
        "answer": name,
        "created_at": time.time(),
        "is_auto": False
    }

    text = (
        f"💬 **Word Scramble!**\n"
        f"───────────────\n"
        f"🔀 **Scrambled**: `{scrambled.upper()}`\n"
        f"💰 **Reward**: `100 coins`\n"
        f"⌛ **Type the correct name! (60s)**"
    )

    # Add inline buttons
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔍 Hint", callback_data="scribble_hint"),
        InlineKeyboardButton(text="🚫 Stop Game", callback_data="scribble_stop")
    )

    sent_msg = await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    active_games[chat_id]["message_id"] = sent_msg.message_id

    await callback.answer("Scribble started!")

    # Start background timeout task
    asyncio.create_task(scribble_timeout_task(chat_id, sent_msg.message_id, callback.bot))


# ==========================================
# SCRIBBLE AND NAMEGUESS GAME CONTROLS
# ==========================================

@router.callback_query(F.data == "scribble_hint")
async def cb_scribble_hint(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    
    if chat_id not in active_games:
        await callback.answer("⚠️ No active scribble game in this chat.", show_alert=True)
        return
        
    game = active_games[chat_id]
    if game.get("type") != "scribble":
        await callback.answer("⚠️ No active scribble game in this chat.", show_alert=True)
        return
        
    # Check if hint already exists to avoid spamming
    if "hint_text" in game:
        hint_text = game["hint_text"]
        await callback.answer(f"💡 Hint already sent: {hint_text}", show_alert=True)
        return
        
    # Generate hint
    hint_text = generate_hint(game["answer"])
    game["hint_text"] = hint_text
    
    # Send the hint message (replying to the scramble message)
    hint_msg = await callback.message.reply(
        f"💡 **Scribble Hint**\n"
        f"───────────────\n"
        f"👉 `{hint_text}`",
        parse_mode="Markdown"
    )
    
    game["hint_message_id"] = hint_msg.message_id
    await callback.answer("Hint generated!")


@router.callback_query(F.data == "scribble_stop")
async def cb_scribble_stop(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    
    if chat_id not in active_games:
        await callback.answer("⚠️ No active scribble game to stop.", show_alert=True)
        return
        
    game = active_games[chat_id]
    if game.get("type") != "scribble":
        await callback.answer("⚠️ No active scribble game to stop.", show_alert=True)
        return

    # Check permission
    is_allowed = False
    if callback.message.chat.type == "private":
        is_allowed = True
    else:
        # Group chat: only admin or owner
        if user_id in config.ADMIN_IDS:
            is_allowed = True
        else:
            try:
                member = await callback.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
                is_allowed = member.status in ["creator", "administrator"]
            except Exception:
                is_allowed = False
                
    if not is_allowed:
        await callback.answer("❌ Only group administrators or bot owners can stop the game.", show_alert=True)
        return
        
    # Clean up the game state
    del active_games[chat_id]
    
    # Delete the prompt and hint messages
    await cleanup_scribble_messages(callback.bot, chat_id, game)
    
    # Send game stopped notification
    await callback.message.answer(f"🛑 **Scribble game stopped** by {callback.from_user.first_name}.")
    await callback.answer("Game stopped!")


@router.callback_query(F.data == "nameguess_hint")
async def cb_nameguess_hint(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    
    if chat_id not in active_games:
        await callback.answer("⚠️ No active NameGuess game in this chat.", show_alert=True)
        return
        
    game = active_games[chat_id]
    if game.get("type") != "nameguess":
        await callback.answer("⚠️ No active NameGuess game in this chat.", show_alert=True)
        return
        
    # Check if hint already exists to avoid spamming
    if "hint_text" in game:
        hint_text = game["hint_text"]
        await callback.answer(f"💡 Hint already revealed: {hint_text}", show_alert=True)
        return
        
    # Generate hint
    hint_text = generate_hint(game["answer"])
    game["hint_text"] = hint_text
    
    hint_msg = await callback.message.reply(
        f"💡 <b>NameGuess Hint Revealed:</b>\n"
        f"───────────────\n"
        f"👉 <code>{hint_text}</code>",
        parse_mode="HTML"
    )
    
    game["hint_message_id"] = hint_msg.message_id
    await callback.answer("💡 Hint revealed in chat!")


@router.callback_query(F.data == "nameguess_stop")
async def cb_nameguess_stop(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    
    if chat_id not in active_games:
        await callback.answer("⚠️ No active NameGuess game to stop.", show_alert=True)
        return
        
    game = active_games[chat_id]
    if game.get("type") != "nameguess":
        await callback.answer("⚠️ No active NameGuess game to stop.", show_alert=True)
        return

    # Check permission
    is_allowed = False
    if callback.message.chat.type == "private":
        is_allowed = True
    else:
        # Group chat: only admin or owner
        if user_id in config.ADMIN_IDS:
            is_allowed = True
        else:
            try:
                member = await callback.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
                is_allowed = member.status in ["creator", "administrator"]
            except Exception:
                is_allowed = False
                
    if not is_allowed:
        await callback.answer("❌ Only group administrators or bot owners can stop the game.", show_alert=True)
        return
        
    del active_games[chat_id]
    await cleanup_nameguess_messages(callback.bot, chat_id, game)
    
    ans_display = game.get("pokemon_name") or game["answer"].title()
    await callback.message.answer(
        f"🛑 <b>NameGuess game stopped</b> by {html.escape(callback.from_user.first_name)}.\n"
        f"💡 The Pokémon was: <b>{ans_display}</b>",
        parse_mode="HTML"
    )
    await callback.answer("Game stopped!")


@router.message(Command("nameguess", "guess"))
async def cmd_nameguess(message: Message, db: AsyncSession):
    if message.chat.type == "private":
        await message.answer(GROUP_ONLY_GAMES_NOTICE, reply_markup=get_official_group_keyboard(), parse_mode="HTML")
        return

    chat_id = message.chat.id
    user_id = message.from_user.id
            
    if chat_id in active_games:
        await message.answer("⚠️ There is already an active game (trivia/scribble/nameguess) in this chat! Answer it first.")
        return

    # Select random Pokémon
    stmt = select(Pokemon).order_by(func.random()).limit(1)
    res = await db.execute(stmt)
    pokemon = res.scalar_one_or_none()

    if not pokemon:
        await message.answer("❌ Error initiating NameGuess. No Pokémon found in database.")
        return

    name = pokemon.name.lower()
    initial_hint = generate_hint(name)

    active_games[chat_id] = {
        "type": "nameguess",
        "answer": name,
        "pokemon_name": pokemon.name,
        "created_at": time.time(),
        "is_auto": False
    }

    type_info = f" | Type: <b>{pokemon.type1}{'/' + pokemon.type2 if pokemon.type2 else ''}</b>" if getattr(pokemon, 'type1', None) else ""
    gen_info = f" | Gen: <b>{pokemon.generation}</b>" if getattr(pokemon, 'generation', None) else ""

    text = (
        f"💡 <b>POKÉMON NAMEGUESS QUIZ</b> 💡\n"
        f"◈ ────────────────────────── ◈\n"
        f"🧠 <i>Who's That Pokémon?</i>\n\n"
        f"🔍 <b>Initial Clue:</b> <code>{initial_hint}</code>{type_info}{gen_info}\n"
        f"⏳ <b>Time Limit:</b> <code>60 seconds</code>\n"
        f"💰 <b>Reward:</b> <code>+150 to 250 coins</code>\n"
        f"◈ ────────────────────────── ◈\n"
        f"<i>Type your answer directly in chat to win!</i>"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(
        create_styled_button(text="🔍 Get Hint", key="hint", callback_data="nameguess_hint"),
        create_styled_button(text="🚫 Stop Game", key="cancel", style="danger", callback_data="nameguess_stop")
    )

    try:
        sent_msg = await send_safe_media(
            bot=message.bot,
            chat_id=chat_id,
            media_type="photo",
            media_value=pokemon.image_url,
            caption=text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML",
            message_to_reply=message
        )
        active_games[chat_id]["message_id"] = sent_msg.message_id
        asyncio.create_task(nameguess_timeout_task(chat_id, sent_msg.message_id, message.bot))
    except Exception as e:
        if chat_id in active_games:
            del active_games[chat_id]
        print(f"Error initiating nameguess: {e}")
        await message.answer("❌ Error initiating NameGuess. Please try again.")

@router.callback_query(F.data.in_({"play_nameguess", "btn_launch_nameguess"}))
async def cb_play_nameguess(callback: CallbackQuery, db: AsyncSession):
    await callback.answer()
    if callback.message.chat.type == "private":
        await callback.message.answer(GROUP_ONLY_GAMES_NOTICE, reply_markup=get_official_group_keyboard(), parse_mode="HTML")
        return
    await cmd_nameguess(callback.message, db)


# ==========================================
# 1. "WHO IS THAT?" (THE SILHOUETTE TRIAL)
# ==========================================

@router.callback_query(F.data == "silhouette_hint")
async def cb_silhouette_hint(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    if chat_id not in active_games or active_games[chat_id].get("type") != "silhouette":
        await callback.answer("⚠️ No active Silhouette Trial in this chat.", show_alert=True)
        return
        
    game = active_games[chat_id]
    if "hint_text" in game:
        await callback.answer(f"💡 Hint already revealed: {game['hint_text']}", show_alert=True)
        return
        
    hint_text = game.get("clue_hint") or generate_hint(game["answer"])
    game["hint_text"] = hint_text
    
    hint_msg = await callback.message.reply(
        f"💡 <b>Silph Co. Sensor Hint Revealed:</b>\n"
        f"───────────────\n"
        f"👉 <code>{hint_text}</code>",
        parse_mode="HTML"
    )
    game["hint_message_id"] = hint_msg.message_id
    await callback.answer("💡 Sensor scan complete! Hint revealed.")

@router.callback_query(F.data == "silhouette_stop")
async def cb_silhouette_stop(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    
    if chat_id not in active_games or active_games[chat_id].get("type") != "silhouette":
        await callback.answer("⚠️ No active Silhouette game to stop.", show_alert=True)
        return
        
    game = active_games[chat_id]
    is_allowed = False
    if callback.message.chat.type == "private":
        is_allowed = True
    else:
        if user_id in config.ADMIN_IDS:
            is_allowed = True
        else:
            try:
                member = await callback.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
                is_allowed = member.status in ["creator", "administrator"]
            except Exception:
                is_allowed = False
                
    if not is_allowed:
        await callback.answer("❌ Only group administrators or bot owners can stop the game.", show_alert=True)
        return
        
    del active_games[chat_id]
    await cleanup_silhouette_messages(callback.bot, chat_id, game)
    
    ans_display = game.get("pokemon_name") or game["answer"].title()
    await callback.message.answer(
        f"🛑 <b>Silhouette Trial stopped</b> by {html.escape(callback.from_user.first_name)}.\n"
        f"💡 The Pokémon was: <b>{ans_display}</b>",
        parse_mode="HTML"
    )
    await callback.answer("Simulation aborted!")

@router.message(Command("whothat", "silhouette", "shadow"))
async def cmd_silhouette(message: Message, db: AsyncSession):
    if message.chat.type == "private":
        await message.answer(GROUP_ONLY_GAMES_NOTICE, reply_markup=get_official_group_keyboard(), parse_mode="HTML")
        return

    chat_id = message.chat.id
    if chat_id in active_games:
        await message.answer("⚠️ There is already an active game running in this chat! Complete or stop it first.")
        return

    # Select random Pokémon with valid image
    stmt = select(Pokemon).where(Pokemon.image_url.isnot(None)).order_by(func.random()).limit(1)
    res = await db.execute(stmt)
    pokemon = res.scalar_one_or_none()

    if not pokemon or not pokemon.image_url:
        await message.answer("❌ Error initiating Silhouette Trial. No Pokémon data available.")
        return

    name = pokemon.name.lower()
    initial_hint = generate_hint(name)
    type_info = f" | Type: <b>{pokemon.type1}{'/' + pokemon.type2 if pokemon.type2 else ''}</b>" if getattr(pokemon, 'type1', None) else ""
    gen_info = f" | Gen: <b>{pokemon.generation}</b>" if getattr(pokemon, 'generation', None) else ""

    active_games[chat_id] = {
        "type": "silhouette",
        "answer": name,
        "pokemon_name": pokemon.name,
        "clue_hint": f"{initial_hint}{type_info}{gen_info}",
        "created_at": time.time(),
        "is_auto": False
    }

    text = (
        f"👤 <b>THE SILHOUETTE TRIAL</b> 👤\n"
        f"◈ ────────────────────────── ◈\n"
        f"🔬 <i>Prof. Oak & Silph Co. Recognition Lab</i>\n"
        f"A wild Pokémon's signal flickers in the dark! Can you recognize it by its shadow?\n\n"
        f"⏳ <b>Time Limit:</b> <code>60 seconds</code>\n"
        f"💰 <b>Bounty Reward:</b> <code>+250 to 450 coins</code>\n"
        f"◈ ────────────────────────── ◈\n"
        f"<i>Type the Pokémon's name in chat to identify it!</i>"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        create_styled_button(text="🔍 Sensor Scan (Hint)", key="hint", callback_data="silhouette_hint"),
        create_styled_button(text="🚫 Abort Sim", key="cancel", style="danger", callback_data="silhouette_stop")
    )

    # Try generating silhouette bytes
    sil_bytes = await get_silhouette_bytes(pokemon.image_url)
    try:
        if sil_bytes:
            photo_file = BufferedInputFile(sil_bytes, filename="silhouette.png")
            sent_msg = await message.answer_photo(
                photo=photo_file,
                caption=text,
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
        else:
            sent_msg = await send_safe_media(
                bot=message.bot,
                chat_id=chat_id,
                media_type="photo",
                media_value=pokemon.image_url,
                caption=text,
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
                message_to_reply=message
            )
        active_games[chat_id]["message_id"] = sent_msg.message_id
        asyncio.create_task(silhouette_timeout_task(chat_id, sent_msg.message_id, message.bot))
    except Exception as e:
        if chat_id in active_games:
            del active_games[chat_id]
        print(f"Error launching silhouette: {e}")
        await message.answer("❌ Error generating silhouette simulation. Please try again.")

@router.callback_query(F.data.in_({"play_silhouette", "btn_launch_silhouette"}))
async def cb_play_silhouette(callback: CallbackQuery, db: AsyncSession):
    await callback.answer()
    if callback.message.chat.type == "private":
        await callback.message.answer(GROUP_ONLY_GAMES_NOTICE, reply_markup=get_official_group_keyboard(), parse_mode="HTML")
        return
    await cmd_silhouette(callback.message, db)


# ==========================================
# 2. TYPE MATCHUP BLITZ (THE ELEMENTAL ADVANTAGE)
# ==========================================

@router.callback_query(F.data == "typematch_hint")
async def cb_typematch_hint(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    if chat_id not in active_games or active_games[chat_id].get("type") != "typematch":
        await callback.answer("⚠️ No active Type Matchup Blitz in this chat.", show_alert=True)
        return
        
    game = active_games[chat_id]
    if game.get("hint_given"):
        await callback.answer("💡 Hint already revealed in chat!", show_alert=True)
        return
        
    valid_list = game.get("valid_answers", [])
    if not valid_list:
        await callback.answer("⚠️ No valid counters found.", show_alert=True)
        return

    sample_type = random.choice(valid_list)
    hint_text = f"Total valid counter types: <b>{len(valid_list)}</b> | One valid counter starts with: <b>{sample_type[0].upper()}...</b>"
    game["hint_given"] = True
    
    hint_msg = await callback.message.reply(
        f"💡 <b>Battle Academy Tactical Hint:</b>\n"
        f"───────────────\n"
        f"👉 {hint_text}",
        parse_mode="HTML"
    )
    game["hint_message_id"] = hint_msg.message_id
    await callback.answer("💡 Tactical scan complete! Hint revealed.")

@router.callback_query(F.data == "typematch_stop")
async def cb_typematch_stop(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    
    if chat_id not in active_games or active_games[chat_id].get("type") != "typematch":
        await callback.answer("⚠️ No active Type Matchup Blitz to stop.", show_alert=True)
        return
        
    game = active_games[chat_id]
    is_allowed = False
    if callback.message.chat.type == "private":
        is_allowed = True
    else:
        if user_id in config.ADMIN_IDS:
            is_allowed = True
        else:
            try:
                member = await callback.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
                is_allowed = member.status in ["creator", "administrator"]
            except Exception:
                is_allowed = False
                
    if not is_allowed:
        await callback.answer("❌ Only group administrators or bot owners can stop the game.", show_alert=True)
        return
        
    del active_games[chat_id]
    await cleanup_typematch_messages(callback.bot, chat_id, game)
    
    ans_list = ", ".join(t.title() for t in game.get("valid_answers", []))
    await callback.message.answer(
        f"🛑 <b>Type Matchup Blitz stopped</b> by {html.escape(callback.from_user.first_name)}.\n"
        f"💡 Valid Elemental Counters were: <b>{ans_list}</b>",
        parse_mode="HTML"
    )
    await callback.answer("Combat simulation aborted!")

@router.message(Command("blitz", "typematch", "typeblitz", "matchup", "unown", ignore_mention=True))
async def cmd_typematch(message: Message, db: AsyncSession):
    if message.chat.type == "private":
        await message.answer(GROUP_ONLY_GAMES_NOTICE, reply_markup=get_official_group_keyboard(), parse_mode="HTML")
        return

    chat_id = message.chat.id
    if chat_id in active_games:
        await message.answer("⚠️ There is already an active game running in this chat! Complete or stop it first.")
        return

    # Choose scenario mode (Offensive vs Defensive)
    mode = random.choice(["offensive", "defensive"])

    # Query a random Pokémon
    stmt = select(Pokemon).where(Pokemon.type1.isnot(None)).order_by(func.random()).limit(1)
    res = await db.execute(stmt)
    pokemon = res.scalar_one_or_none()

    if not pokemon:
        await message.answer("❌ Error initiating Type Matchup Blitz. No Pokémon data available.")
        return

    p_name = pokemon.name.title()
    p_t1 = pokemon.type1.title()
    p_t2 = pokemon.type2.title() if pokemon.type2 else None
    types_str = f"{p_t1}/{p_t2}" if p_t2 else p_t1

    if mode == "offensive":
        valid_answers = get_super_effective_types(p_t1, p_t2)
        if not valid_answers:
            valid_answers = ["normal", "fighting", "ground"]
        
        scenario_title = f"Wild {p_name} ({types_str})"
        text = (
            f"⚡ <b>TYPE MATCHUP BLITZ — OFFENSIVE STRIKE</b> ⚡\n"
            f"◈ ────────────────────────── ◈\n"
            f"🏟️ <i>Indigo Plateau Battle Academy Simulation</i>\n\n"
            f"A wild <b>{p_name}</b> ({types_str}) appeared in the arena!\n"
            f"🎯 <b>Objective:</b> Name an attack type that is <b>SUPER-EFFECTIVE</b> against {p_name}!\n\n"
            f"⏳ <b>Time Limit:</b> <code>60 seconds</code>\n"
            f"💰 <b>Reward:</b> <code>+350 to 500 coins</code>\n"
            f"◈ ────────────────────────── ◈\n"
            f"<i>Type the super-effective type name directly in chat to strike!</i>"
        )
    else:
        # Defensive Mode
        atk_type = random.choice(POKEMON_TYPES)
        valid_answers = get_resistant_immune_types(atk_type)
        if not valid_answers:
            valid_answers = ["steel", "dragon", "fire"]

        scenario_title = f"Incoming {atk_type}-type Attack toward {p_name}"
        text = (
            f"🛡️ <b>TYPE MATCHUP BLITZ — DEFENSIVE COUNTER</b> 🛡️\n"
            f"◈ ────────────────────────── ◈\n"
            f"🏟️ <i>Indigo Plateau Battle Academy Simulation</i>\n\n"
            f"An incoming <b>{atk_type}-type</b> attack is heading toward {p_name} ({types_str})!\n"
            f"🛡️ <b>Objective:</b> Name any Pokémon type that <b>RESISTS</b> or is <b>IMMUNE</b> to {atk_type}!\n\n"
            f"⏳ <b>Time Limit:</b> <code>60 seconds</code>\n"
            f"💰 <b>Reward:</b> <code>+350 to 500 coins</code>\n"
            f"◈ ────────────────────────── ◈\n"
            f"<i>Type any resistant or immune type directly in chat to defend!</i>"
        )

    active_games[chat_id] = {
        "type": "typematch",
        "mode": mode,
        "valid_answers": valid_answers,
        "scenario_title": scenario_title,
        "hint_given": False,
        "created_at": time.time(),
        "is_auto": False
    }

    builder = InlineKeyboardBuilder()
    builder.row(
        create_styled_button(text="💡 Tactical Hint", key="hint", callback_data="typematch_hint"),
        create_styled_button(text="🚫 Abort Battle", key="cancel", style="danger", callback_data="typematch_stop")
    )

    try:
        if pokemon.image_url:
            sent_msg = await send_safe_media(
                bot=message.bot,
                chat_id=chat_id,
                media_type="photo",
                media_value=pokemon.image_url,
                caption=text,
                reply_markup=builder.as_markup(),
                parse_mode="HTML",
                message_to_reply=message
            )
        else:
            sent_msg = await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
            
        active_games[chat_id]["message_id"] = sent_msg.message_id
        asyncio.create_task(typematch_timeout_task(chat_id, sent_msg.message_id, message.bot))
    except Exception as e:
        if chat_id in active_games:
            del active_games[chat_id]
        print(f"Error launching typematch: {e}")
        await message.answer("❌ Error initiating Type Matchup Blitz. Please try again.")

@router.callback_query(F.data.in_({"play_typematch", "btn_launch_typematch", "play_unown", "btn_launch_unown"}))
async def cb_play_typematch(callback: CallbackQuery, db: AsyncSession):
    await callback.answer()
    if callback.message.chat.type == "private":
        await callback.message.answer(GROUP_ONLY_GAMES_NOTICE, reply_markup=get_official_group_keyboard(), parse_mode="HTML")
        return
    await cmd_typematch(callback.message, db)


# ==========================================
# 3. NUMGUESS (THE VOLTORB LOCK & KEY)
# ==========================================

@router.callback_query(F.data == "voltorb_stop")
async def cb_voltorb_stop(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    
    if chat_id not in active_games or active_games[chat_id].get("type") != "voltorb":
        await callback.answer("⚠️ No active Voltorb Lock in this chat.", show_alert=True)
        return
        
    game = active_games[chat_id]
    is_allowed = False
    if callback.message.chat.type == "private":
        is_allowed = True
    else:
        if user_id in config.ADMIN_IDS:
            is_allowed = True
        else:
            try:
                member = await callback.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
                is_allowed = member.status in ["creator", "administrator"]
            except Exception:
                is_allowed = False
                
    if not is_allowed:
        await callback.answer("❌ Only group administrators or bot owners can stop the game.", show_alert=True)
        return
        
    del active_games[chat_id]
    await cleanup_voltorb_messages(callback.bot, chat_id, game)
    
    await callback.message.answer(
        f"🛑 <b>Voltorb Lock breach aborted</b> by {html.escape(callback.from_user.first_name)}.\n"
        f"🔐 Security PIN was: <code>{game['target']}</code>",
        parse_mode="HTML"
    )
    await callback.answer("Vault lock reset!")

@router.message(Command("voltorb", "numguess", "vault"))
async def cmd_voltorb(message: Message, db: AsyncSession):
    if message.chat.type == "private":
        await message.answer(GROUP_ONLY_GAMES_NOTICE, reply_markup=get_official_group_keyboard(), parse_mode="HTML")
        return

    chat_id = message.chat.id
    if chat_id in active_games:
        await message.answer("⚠️ There is already an active game running in this chat! Complete or stop it first.")
        return

    target = random.randint(1, 50)
    active_games[chat_id] = {
        "type": "voltorb",
        "target": target,
        "attempts": 0,
        "max_attempts": 6,
        "low_bound": 1,
        "high_bound": 50,
        "created_at": time.time(),
        "is_auto": False
    }

    text = (
        f"⚡ <b>THE VOLTORB LOCK & KEY</b> ⚡\n"
        f"◈ ────────────────────────── ◈\n"
        f"🏢 <i>Power Plant Security Vault System</i>\n"
        f"A live Voltorb guards the security lockbox! Guess the PIN between <b>1 and 50</b> before it uses Self-Destruct!\n\n"
        f"🎯 <b>Initial Range:</b> <code>[ 1 – 50 ]</code>\n"
        f"💣 <b>Attempts Remaining:</b> <code>6 / 6</code>\n"
        f"💰 <b>Max Bounty Reward:</b> <code>+900 coins</code> (scales with speed!)\n"
        f"⏳ <b>Time Limit:</b> <code>60 seconds</code>\n"
        f"◈ ────────────────────────── ◈\n"
        f"<i>Type any number between 1 and 50 in chat to hack the terminal!</i>"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        create_styled_button(text="🚫 Abort Hack", key="cancel", style="danger", callback_data="voltorb_stop")
    )

    try:
        sent_msg = await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        active_games[chat_id]["message_id"] = sent_msg.message_id
        asyncio.create_task(voltorb_timeout_task(chat_id, sent_msg.message_id, message.bot))
    except Exception as e:
        if chat_id in active_games:
            del active_games[chat_id]
        print(f"Error launching voltorb: {e}")
        await message.answer("❌ Error initializing Voltorb Lock. Please try again.")

@router.callback_query(F.data.in_({"play_voltorb", "btn_launch_voltorb"}))
async def cb_play_voltorb(callback: CallbackQuery, db: AsyncSession):
    await callback.answer()
    if callback.message.chat.type == "private":
        await callback.message.answer(GROUP_ONLY_GAMES_NOTICE, reply_markup=get_official_group_keyboard(), parse_mode="HTML")
        return
    await cmd_voltorb(callback.message, db)


# ==========================================
# ADMIN SCRIBBLE TOGGLE & TRIVIA CALLBACKS
# ==========================================

@router.message(Command("togglescribble"))
async def cmd_toggle_scribble(message: Message):
    if message.chat.type not in ["group", "supergroup"]:
        await message.answer("⚠️ This command can only be used in group chats.")
        return

    from handlers.admin import is_user_admin
    if not await is_user_admin(message):
        await message.answer("❌ Denied. Only group administrators or bot owners can toggle scribble mode.")
        return

    chat_id = message.chat.id
    current_status = is_scribble_enabled(chat_id)
    new_status = not current_status
    await set_scribble_status(chat_id, new_status)

    status_str = "Enabled 🟢" if new_status else "Disabled 🔴"
    await message.answer(f"✏️ <b>Scribble Mode</b> is now <b>{status_str}</b> in this chat.", parse_mode="HTML")

@router.message(Command("togglenameguess"))
async def cmd_toggle_nameguess(message: Message):
    if message.chat.type not in ["group", "supergroup"]:
        await message.answer("⚠️ This command can only be used in group chats.")
        return

    from handlers.admin import is_user_admin
    if not await is_user_admin(message):
        await message.answer("❌ Denied. Only group administrators or bot owners can toggle nameguess mode.")
        return

    chat_id = message.chat.id
    current_status = is_nameguess_enabled(chat_id)
    new_status = not current_status
    await set_nameguess_status(chat_id, new_status)

    status_str = "Enabled 🟢" if new_status else "Disabled 🔴"
    await message.answer(f"🖼️ <b>Nameguess Mode</b> is now <b>{status_str}</b> in this chat.", parse_mode="HTML")

@router.callback_query(F.data.startswith("trivia_ans_"))
async def cb_trivia_answer(callback: CallbackQuery, db: AsyncSession):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    nickname = callback.from_user.first_name
    
    if chat_id not in active_games:
        await callback.answer("⚠️ This trivia game has ended or expired.", show_alert=True)
        return
        
    game = active_games[chat_id]
    if game.get("type") != "trivia":
        await callback.answer("⚠️ No active trivia game found.", show_alert=True)
        return
        
    if user_id in game["guesses"]:
        await callback.answer("⚠️ You have already guessed once! Only one guess allowed per trainer.", show_alert=True)
        return
        
    if time.time() - game["created_at"] > 60:
        del active_games[chat_id]
        await callback.message.edit_text(
            f"⏳ <b>TRIVIA EXPIRED</b> ⏳\n"
            f"───────────────\n\n"
            f"❌ Time is up! No one guessed the correct answer in time.\n\n"
            f"💡 Correct Answer was: <b>{game['answer']}</b>\n"
            f"───────────────",
            reply_markup=None,
            parse_mode="HTML"
        )
        await callback.answer("This trivia game has expired.")
        return
        
    try:
        opt_idx = int(callback.data.replace("trivia_ans_", ""))
        selected_option = game["options"][opt_idx]
    except (ValueError, IndexError):
        await callback.answer("❌ Error processing your answer.", show_alert=True)
        return
        
    game["guesses"].add(user_id)
    
    if selected_option == game["answer"]:
        stmt = select(User).where(User.id == user_id)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()

        if not user:
            user = User(id=user_id, username=callback.from_user.username, nickname=nickname)
            db.add(user)
            await db.flush()

        reward = 150
        user.coins += reward
        await db.commit()

        del active_games[chat_id]

        escaped_q = html.escape(game['question'])
        escaped_ans = html.escape(game['answer'])
        text = (
            f"🎉 <b>TRIVIA CHAMPION!</b> 🎉\n"
            f"───────────────\n\n"
            f"<b>Question:</b>\n"
            f"{escaped_q}\n\n"
            f"<blockquote>💡 Correct Answer: <b>{escaped_ans}</b>\n"
            f"🏆 Winner: Trainer <b>{html.escape(user.nickname)}</b>\n"
            f"💰 Reward: <b>+{reward} coins</b>\n"
            f"💳 Balance: <b>{user.coins} coins</b></blockquote>\n"
            f"───────────────"
        )
        
        msg = await callback.message.edit_text(text, reply_markup=None, parse_mode="HTML")
        await callback.answer("🎉 Correct answer!")
        asyncio.create_task(delete_message_after(msg, 60))
    else:
        await callback.answer("❌ Incorrect answer! You are locked out of this question.", show_alert=True)
        
        if callback.message.chat.type == "private":
            del active_games[chat_id]
            escaped_ans = html.escape(game['answer'])
            msg = await callback.message.edit_text(
                f"❓ <b>TRIVIA OVER</b> ❓\n"
                f"───────────────\n\n"
                f"<blockquote>❌ You guessed incorrectly!\n\n"
                f"💡 Correct Answer: <b>{escaped_ans}</b></blockquote>\n"
                f"───────────────",
                reply_markup=None,
                parse_mode="HTML"
            )
            asyncio.create_task(delete_message_after(msg, 60))

@router.message(Command("balance", "bal", "coins", "wallet"))
async def cmd_balance(message: Message, db: AsyncSession):
    try:
        user_id = message.from_user.id
        u_stmt = select(User).where(User.id == user_id)
        u_res = await db.execute(u_stmt)
        user = u_res.scalar_one_or_none()

        if not user:
            user = User(
                id=user_id,
                username=message.from_user.username,
                nickname=message.from_user.first_name or "Trainer",
                coins=500,
                gems=10
            )
            db.add(user)
            await db.commit()

        from utils.trainer_level import get_trainer_title
        level = getattr(user, 'trainer_level', 1) or 1
        title = get_trainer_title(level)
        name = html.escape(user.nickname or message.from_user.first_name or "Trainer")
        
        text = (
            f"💳 <b>TRAINER BALANCE & WALLET</b> 💳\n"
            f"───────────────\n"
            f"👤 <b>Trainer</b>: <b>{name}</b> (<code>{user_id}</code>)\n"
            f"⭐ <b>Level</b>: <b>{level} ({title})</b>\n\n"
            f"💰 <b>Coins</b>: <code>{user.coins:,}</code> 🪙\n"
            f"💎 <b>Gems</b>: <code>{getattr(user, 'gems', 0):,}</code> 💎\n"
            f"───────────────\n"
            f"<i>All earnings are instantly usable across PokeEmpire & PokeArena!</i>"
        )
        builder = InlineKeyboardBuilder()
        builder.row(
            create_styled_button(text="🎰 Games Hub", key="games", callback_data="btn_open_games_hub", style="primary"),
            create_styled_button(text="🎡 Hourly Spin", key="games", callback_data="btn_launch_spin", style="success")
        )
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception as e:
        print(f"Error in games cmd_balance: {e}")
        await message.answer("❌ An error occurred while retrieving your balance.")

@router.message(Command("streak", "streaks"))
async def cmd_streak(message: Message, db: AsyncSession):
    user_id = message.from_user.id
    
    # Check registration
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        await message.answer("⚠️ You must register first with /start or catch a Pokémon!")
        return
        
    from utils.streak import get_streak_data, get_streak_rank
    import html
    
    s_data = await get_streak_data(user_id)
    
    today = datetime.utcnow().date().isoformat()
    yesterday = (datetime.utcnow() - timedelta(days=1)).date().isoformat()
    
    # Determine status
    last_sec = s_data.get("last_secured_date", "")
    if last_sec == today:
        status_str = "Active!"
        capped_count = 3
    elif last_sec == yesterday:
        status_str = "Active!"
        capped_count = min(s_data.get("catches_today", 0), 3)
    else:
        status_str = "Streak broken!"
        capped_count = min(s_data.get("catches_today", 0), 3)
        
    current_days = s_data.get("current_streak", 0)
    best_days = s_data.get("best_streak", 0)
    rank_str = get_streak_rank(current_days)
    
    # Progress bar
    bar_chars = "█" * (capped_count * 3) + "░" * (10 - (capped_count * 3))
    if capped_count == 3:
        bar_chars = "█" * 10
        
    text = (
        f" 🔥 <b>Daily Streak — {html.escape(user.nickname or 'Trainer')}</b>\n\n"
        f"<blockquote>💧 <b>Status</b>: <code>{status_str}</code>\n"
        f"🎁 <b>Current</b>: <code>{current_days} days</code>\n"
        f"🏆 <b>Best</b>: <code>{best_days} days</code>\n"
        f"🏆 <b>Rank</b>: <code>{rank_str}</code>\n"
        f"🎁 <b>Progress</b>: <code>[{bar_chars}] {capped_count}/3</code></blockquote>\n\n"
        f"👉 <i>Catch 3 Pokémon every day to keep your streak!</i>"
    )
    await message.answer(text, parse_mode="HTML")

@router.message(Command("streaklb", "slb", "streakslb", "streaksleaderboard"))
async def cmd_streak_leaderboard(message: Message, db: AsyncSession):
    from utils.streak import get_top_streaks
    from utils.formatters import escape_md
    
    top_users = await get_top_streaks(10)
    
    if not top_users:
        await message.answer("🏆 **STREAK LEADERBOARD** 🏆\n───────────────\n\n• *No active streaks recorded yet.*")
        return
        
    # Query nicknames and usernames for the top users
    import config
    bot_id = None
    if config.BOT_TOKEN and ":" in config.BOT_TOKEN:
        try:
            bot_id = int(config.BOT_TOKEN.split(":")[0])
        except ValueError:
            pass

    # Filter out bot ID
    filtered_users = []
    for uid, uinfo in top_users:
        if bot_id and uid == bot_id:
            continue
        filtered_users.append((uid, uinfo))
    filtered_users = filtered_users[:10]

    if not filtered_users:
        await message.answer("🏆 **STREAK LEADERBOARD** 🏆\n───────────────\n\n• *No active streaks recorded yet.*")
        return

    uids = [uid for uid, _ in filtered_users]
    u_stmt = select(User).where(User.id.in_(uids))
    u_res = await db.execute(u_stmt)
    users_dict = {u.id: u for u in u_res.scalars().all()}
    
    rows = []
    import html
    for idx, (uid, uinfo) in enumerate(filtered_users):
        rank_prefix = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx + 1}."
        user = users_dict.get(uid)
        username = user.username if user else None
        nickname = user.nickname if user else f"Trainer_{uid}"
        
        display_name = f"@{html.escape(username)}" if username else f"{html.escape(nickname)}"
        best = uinfo.get("best_streak", 0)
        curr = uinfo.get("current_streak", 0)
        rows.append(f"{rank_prefix} <b>{display_name}</b> • Best: <code>{best}d</code> (Current: <code>{curr}d</code>)")
        
    leaderboard_card = (
        f"🔥 <b>DAILY STREAK LEADERBOARD</b> 🔥\n"
        f"───────────────\n\n"
        f"<blockquote>{'\n'.join(rows)}</blockquote>\n\n"
        f"───────────────"
    )
    await message.answer(leaderboard_card, parse_mode="HTML")

@router.callback_query(F.data == "dm_streak")
async def cb_dm_streak(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id
    
    # Check registration
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        await callback.answer("⚠️ You must register first by catching a Pokémon!", show_alert=True)
        return
        
    from utils.streak import get_streak_data, get_streak_rank
    from keyboards.inline import get_back_to_hub_keyboard
    import html
    
    s_data = await get_streak_data(user_id)
    
    today = datetime.utcnow().date().isoformat()
    yesterday = (datetime.utcnow() - timedelta(days=1)).date().isoformat()
    
    # Determine status
    last_sec = s_data.get("last_secured_date", "")
    if last_sec == today:
        status_str = "Active!"
        capped_count = 3
    elif last_sec == yesterday:
        status_str = "Active!"
        capped_count = min(s_data.get("catches_today", 0), 3)
    else:
        status_str = "Streak broken!"
        capped_count = min(s_data.get("catches_today", 0), 3)
        
    current_days = s_data.get("current_streak", 0)
    best_days = s_data.get("best_streak", 0)
    rank_str = get_streak_rank(current_days)
    
    # Progress bar
    bar_chars = "█" * (capped_count * 3) + "░" * (10 - (capped_count * 3))
    if capped_count == 3:
        bar_chars = "█" * 10
        
    text = (
        f" 🔥 <b>Daily Streak — {html.escape(user.nickname)}</b>\n\n"
        f"<blockquote>💧 <b>Status</b>: <code>{status_str}</code>\n"
        f"🎁 <b>Current</b>: <code>{current_days} days</code>\n"
        f"🏆 <b>Best</b>: <code>{best_days} days</code>\n"
        f"🏆 <b>Rank</b>: <code>{rank_str}</code>\n"
        f"🎁 <b>Progress</b>: <code>[{bar_chars}] {capped_count}/3</code></blockquote>\n\n"
        f"👉 <i>Catch 3 Pokémon every day to keep your streak!</i>"
    )
    try:
        await callback.message.edit_caption(caption=text, reply_markup=get_back_to_hub_keyboard(), parse_mode="HTML")
    except Exception:
        try:
            await callback.message.edit_text(text, reply_markup=get_back_to_hub_keyboard(), parse_mode="HTML")
        except Exception:
            pass
    await callback.answer()

@router.callback_query(F.data == "dm_leaderboard")
async def cb_dm_leaderboard(callback: CallbackQuery, db: AsyncSession):
    from handlers.profile import get_leaderboard_text
    text = await get_leaderboard_text("catches", db)
    
    builder = InlineKeyboardBuilder()
    builder.row(
        create_styled_button(text="🏆 Pokémon", key="pokedex", style="success", callback_data="lb_type_catches_dm"),
        create_styled_button(text="💰 Coins", key="claim", style="primary", callback_data="lb_type_coins_dm"),
        create_styled_button(text="🔥 Streak", key="streak", style="danger", callback_data="lb_type_streak_dm")
    )
    builder.row(create_styled_button(text="Back to Hub Menu", key="back", style="primary", callback_data="dm_home"))
    
    try:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    except Exception:
        try:
            await callback.message.edit_text(
                text=text,
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
        except Exception:
            pass
    await callback.answer()

@router.callback_query(F.data == "dm_battle_menu")
async def cb_dm_battle_menu(callback: CallbackQuery):
    text = (
        "\ud83d\udee1\ufe0f **BATTLE**\n"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
        "Battle wild Pok\u00e9mon with your team!\n\n"
        "\ud83d\udc49 **Commands:**\n"
        "\u2022 `/battlebot` \u2014 Battle against the AI\n"
        "\u2022 `/duel @trainer` \u2014 Challenge another trainer\n"
    )
    try:
        await callback.message.edit_caption(caption=text, reply_markup=get_back_to_hub_keyboard(), parse_mode="Markdown")
    except Exception:
        try:
            await callback.message.edit_text(text, reply_markup=get_back_to_hub_keyboard(), parse_mode="Markdown")
        except Exception:
            pass
    await callback.answer()

@router.callback_query(F.data == "dm_duel_info")
async def cb_dm_duel_info(callback: CallbackQuery):
    text = (
        "\u2694\ufe0f **TRAINER DUEL**\n"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
        "Challenge another trainer to a Pok\u00e9mon battle!\n\n"
        "\ud83d\udc49 **Commands:**\n"
        "\u2022 `/duel @username` \u2014 Start a duel in group\n"
    )
    try:
        await callback.message.edit_caption(caption=text, reply_markup=get_back_to_hub_keyboard(), parse_mode="Markdown")
    except Exception:
        try:
            await callback.message.edit_text(text, reply_markup=get_back_to_hub_keyboard(), parse_mode="Markdown")
        except Exception:
            pass
    await callback.answer()

@router.callback_query(F.data == "dm_trade_info")
async def cb_dm_trade_info(callback: CallbackQuery):
    text = (
        "\ud83d\udd04 **TRADE**\n"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
        "Trade Pok\u00e9mon with other trainers!\n\n"
        "\ud83d\udc49 **Commands:**\n"
        "\u2022 `/trade @username` \u2014 Initiate a trade\n"
    )
    try:
        await callback.message.edit_caption(caption=text, reply_markup=get_back_to_hub_keyboard(), parse_mode="Markdown")
    except Exception:
        try:
            await callback.message.edit_text(text, reply_markup=get_back_to_hub_keyboard(), parse_mode="Markdown")
        except Exception:
            pass
    await callback.answer()

@router.callback_query(F.data == "dm_redeem_info")
async def cb_dm_redeem_info(callback: CallbackQuery):
    text = (
        "\ud83c\udf81 **REDEEM CODES**\n"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
        "Redeem special codes for coins or Pok\u00e9mon!\n\n"
        "\ud83d\udc49 **Commands:**\n"
        "\u2022 `/redeem <CODE>` \u2014 Use a promo code\n\n"
        "\u26a0\ufe0f *Codes are distributed during special events.*"
    )
    try:
        await callback.message.edit_caption(caption=text, reply_markup=get_back_to_hub_keyboard(), parse_mode="Markdown")
    except Exception:
        try:
            await callback.message.edit_text(text, reply_markup=get_back_to_hub_keyboard(), parse_mode="Markdown")
        except Exception:
            pass
    await callback.answer()
