import random
import asyncio
import time
from typing import Optional
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database.models import User, Pokemon, UserPokemon
from utils.formatters import escape_md, get_rarity_emoji

router = Router()

# In-memory dictionary to track active trivia/scribble games per chat
active_games = {}
# In-memory dictionary to track trainer trivia command cooldowns
last_trivia_time = {}

@router.message(Command("daily"))
async def cmd_daily(message: Message, db: AsyncSession):
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

    now = datetime.now()
    if user.last_daily_at:
        cooldown = timedelta(hours=24)
        elapsed = now - user.last_daily_at
        if elapsed < cooldown:
            remaining = cooldown - elapsed
            hours, remainder = divmod(remaining.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_str = f"{hours}h {minutes}m {seconds}s"
            await message.answer(f"⏳ **Too early!** You can claim your next daily reward in **{time_str}**.")
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
        f"Balance: 💰 **{user.coins} coins**."
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(Command("spin"))
async def cmd_spin(message: Message, db: AsyncSession):
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

    now = datetime.now()
    if user.last_spin_at:
        cooldown = timedelta(hours=4)
        elapsed = now - user.last_spin_at
        if elapsed < cooldown:
            remaining = cooldown - elapsed
            hours, remainder = divmod(remaining.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_str = f"{hours}h {minutes}m {seconds}s"
            await message.answer(f"⏳ **Hold on!** The lucky wheel is recharging. Spin again in **{time_str}**.")
            return

    rewards = [50, 100, 150, 200, 300, 500]
    weights = [40, 30, 15, 10, 4, 1]
    won = random.choices(rewards, weights=weights, k=1)[0]

    user.coins += won
    user.last_spin_at = now
    await db.commit()

    # Simple text-based spin animation
    wheels = [
        "🎡 **LUCKY SPIN WHEEL** 🎡\n───────────────\nSpinning... 🎰 [ 🔴 | 🟡 | 🟢 | 🔵 ]",
        "🎡 **LUCKY SPIN WHEEL** 🎡\n───────────────\nSpinning... 🎰 [ 50 | 150 | 500 ]",
        f"🎡 **LUCKY SPIN RESULT** 🎡\n───────────────\n"
        f"🎉 **STAY!** 🎉\n\n"
        f"Trainer **{escape_md(user.nickname)}** spun the wheel and won:\n"
        f"💰 **+{won} coins**!\n\n"
        f"Balance: 💰 **{user.coins} coins**."
    ]
    
    msg = await message.answer(wheels[0], parse_mode="Markdown")
    await asyncio.sleep(0.5)
    await msg.edit_text(wheels[1], parse_mode="Markdown")
    await asyncio.sleep(0.5)
    await msg.edit_text(wheels[2], parse_mode="Markdown")

@router.message(Command("coinflip"))
async def cmd_coinflip(message: Message, db: AsyncSession):
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

    if bet < 10 or bet > 500:
        await message.answer("⚠️ Bet must be between 10 and 500 coins.")
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
            f"🪙 **COINFLIP RESULT** 🪙\n"
            f"───────────────\n"
            f"The coin landed on: **{outcome.upper()}**!\n\n"
            f"🎉 **Victory!** You double your bet and gained:\n"
            f"💰 **+{bet} coins**!\n\n"
            f"Balance: 💰 **{user.coins} coins**."
        )
    else:
        user.coins -= bet
        await db.commit()
        text = (
            f"🪙 **COINFLIP RESULT** 🪙\n"
            f"───────────────\n"
            f"The coin landed on: **{outcome.upper()}**!\n\n"
            f"💀 **Defeat!** You lost your bet of:\n"
            f"💰 **-{bet} coins**...\n\n"
            f"Balance: 💰 **{user.coins} coins**."
        )

    msg = await message.answer("🪙 Flipping the coin... 🪙\n───────────────\n🔄 *Spinning in the air...*")
    await asyncio.sleep(0.5)
    await msg.edit_text("🪙 Flipping the coin... 🪙\n───────────────\n✨ *Falling down...*")
    await asyncio.sleep(0.5)
    await msg.edit_text(text, parse_mode="Markdown")

@router.message(Command("rps"))
async def cmd_rps(message: Message, db: AsyncSession):
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

    if bet < 10 or bet > 500:
        await message.answer("⚠️ Bet must be between 10 and 500 coins.")
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
            f"✊✋✌️ **ROCK-PAPER-SCISSORS** ✊✋✌️\n"
            f"───────────────\n"
            f"• You chose: **{user_choice.title()}**\n"
            f"• Bot chose: **{bot_choice.title()}**\n\n"
            f"🤝 **Draw!** Your bet of 💰 **{bet} coins** has been refunded."
        )
    elif outcome == "win":
        user.coins += bet
        await db.commit()
        text = (
            f"✊✋✌️ **ROCK-PAPER-SCISSORS** ✊✋✌️\n"
            f"───────────────\n"
            f"• You chose: **{user_choice.title()}**\n"
            f"• Bot chose: **{bot_choice.title()}**\n\n"
            f"🎉 **Victory!** You won the duel and gained:\n"
            f"💰 **+{bet} coins**!\n\n"
            f"Balance: 💰 **{user.coins} coins**."
        )
    else:
        user.coins -= bet
        await db.commit()
        text = (
            f"✊✋✌️ **ROCK-PAPER-SCISSORS** ✊✋✌️\n"
            f"───────────────\n"
            f"• You chose: **{user_choice.title()}**\n"
            f"• Bot chose: **{bot_choice.title()}**\n\n"
            f"💀 **Defeat!** You lost the duel and lost:\n"
            f"💰 **-{bet} coins**...\n\n"
            f"Balance: 💰 **{user.coins} coins**."
        )

    msg = await message.answer("✊✋✌️ Dueling... ✊✋✌️\n───────────────\n🔄 *Rock... Paper... Scissors...*")
    await asyncio.sleep(0.5)
    await msg.edit_text("✊✋✌️ Dueling... ✊✋✌️\n───────────────\n💥 *SHOOT!* 💥")
    await asyncio.sleep(0.5)
    await msg.edit_text(text, parse_mode="Markdown")

async def start_auto_scribble_game(chat_id: int, message: Message, db: AsyncSession):
    # Set a synchronous lock to prevent overlapping auto-starts in the same chat
    active_games[chat_id] = {
        "type": "initializing",
        "created_at": time.time()
    }
    
    try:
        # Select random Pokémon
        random_id = random.randint(1, 1025)
        stmt = select(Pokemon).where(Pokemon.id == random_id)
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

        r_emoji = get_rarity_emoji(pokemon.rarity)

        text = (
            f"✏️ **POKÉMON SCRIBBLE** ✏️\n"
            f"───────────────\n\n"
            f"Unscramble this Pokémon's name:\n"
            f"👉 **`{scrambled.upper()}`**\n\n"
            f"✨ **Rarity**: {r_emoji} `{pokemon.rarity}`\n"
            f"🧬 **Generation**: `Gen {pokemon.generation}`\n\n"
            f"👉 Type the correct name to win 💰 **10-50 coins**! (Ends in 60s)"
        )
        await message.answer(text, parse_mode="Markdown")
    except Exception as e:
        # Clean up lock on error
        if chat_id in active_games and active_games[chat_id].get("type") == "initializing":
            del active_games[chat_id]
        raise e

async def initiate_trivia_game(chat_id: int, db: AsyncSession, is_auto: bool = False) -> Optional[str]:
    """Starts a trivia game logic and returns the formatted question card text, or None on error."""
    random_id = random.randint(1, 1025)
    stmt = select(Pokemon).where(Pokemon.id == random_id)
    res = await db.execute(stmt)
    pokemon = res.scalar_one_or_none()

    if not pokemon:
        return None

    q_type = random.choice([1, 2, 3])
    options_dict = {}
    options_display = []
    
    if q_type == 1:
        correct_gen = pokemon.generation
        question = f"What **Generation** is the Pokémon **{pokemon.name.title()}**?"
        answer = str(correct_gen)
        
        all_gens = [1, 2, 3, 4, 5, 6, 7, 8, 9]
        incorrect_pool = [g for g in all_gens if g != correct_gen]
        incorrects = random.sample(incorrect_pool, 3)
        options_list = [correct_gen] + incorrects
        random.shuffle(options_list)
        
        letters = ["🇦", "🇧", "🇨", "🇩"]
        for idx, val in enumerate(options_list):
            letter_char = chr(97 + idx)
            options_dict[letter_char] = str(val)
            options_display.append(f"{letters[idx]} **Gen {val}**")
            
    elif q_type == 2:
        correct_rarity = pokemon.rarity.lower()
        question = f"What **Rarity Tier** is the Pokémon **{pokemon.name.title()}**?"
        answer = correct_rarity
        
        all_rarities = ["common", "uncommon", "rare", "epic", "legendary", "mythical"]
        incorrect_pool = [r for r in all_rarities if r != correct_rarity]
        incorrects = random.sample(incorrect_pool, 3)
        options_list = [correct_rarity] + incorrects
        random.shuffle(options_list)
        
        letters = ["🇦", "🇧", "🇨", "🇩"]
        for idx, val in enumerate(options_list):
            letter_char = chr(97 + idx)
            options_dict[letter_char] = val
            r_emoji = get_rarity_emoji(val.title())
            options_display.append(f"{letters[idx]} {r_emoji} **{val.title()}**")
            
    else:
        correct_name = pokemon.name.lower()
        question = f"Which Pokémon has the National Pokédex ID **#{pokemon.id:03d}**?"
        answer = correct_name
        
        stmt = select(Pokemon.name).where(Pokemon.id != pokemon.id).order_by(func.random()).limit(3)
        q_res = await db.execute(stmt)
        incorrects = [r[0].lower() for r in q_res.all()]
        
        if len(incorrects) < 3:
            incorrects = ["bulbasaur", "charmander", "squirtle"][:3]
            
        options_list = [correct_name] + incorrects
        random.shuffle(options_list)
        
        letters = ["🇦", "🇧", "🇨", "🇩"]
        for idx, val in enumerate(options_list):
            letter_char = chr(97 + idx)
            options_dict[letter_char] = val
            options_display.append(f"{letters[idx]} **{val.title()}**")

    options_text = "\n".join(options_display)
    
    active_games[chat_id] = {
        "type": "trivia",
        "answer": answer,
        "options": options_dict,
        "created_at": time.time(),
        "is_auto": is_auto
    }
    
    text = (
        f"❓ **POKÉMON TRIVIA** ❓\n"
        f"───────────────\n\n"
        f"{question}\n\n"
        f"{options_text}\n\n"
        f"👉 Type the option letter (`A`, `B`, `C`, `D`) or the correct answer to win 💰 **100 coins**! (Ends in 60s)"
    )
    return text

@router.message(Command("trivia"))
async def cmd_trivia(message: Message, db: AsyncSession):
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

    trivia_text = await initiate_trivia_game(chat_id, db, is_auto=False)
    if not trivia_text:
        await message.answer("❌ Error initiating trivia. Try again.")
        return

    # Set trainer cooldown
    last_trivia_time[user_id] = time.time()
    await message.answer(trivia_text, parse_mode="Markdown")

@router.message(Command("scribble"))
@router.message(Command("unscramble"))
async def cmd_scribble(message: Message, db: AsyncSession):
    chat_id = message.chat.id

    if message.chat.type in ["group", "supergroup"]:
        await message.answer("✏️ **Scribble** runs automatically in this group chat all the time! Keep an eye out for active words.")
        return

    if chat_id in active_games:
        await message.answer("⚠️ There is already an active trivia or scribble game in this chat! Answer it first.")
        return

    # Select random Pokémon
    random_id = random.randint(1, 1025)
    stmt = select(Pokemon).where(Pokemon.id == random_id)
    res = await db.execute(stmt)
    pokemon = res.scalar_one_or_none()

    if not pokemon:
        await message.answer("❌ Error initiating scribble. Try again.")
        return

    name = pokemon.name.lower()
    name_list = list(name)
    random.shuffle(name_list)
    scrambled = "".join(name_list)

    # Make sure scrambled name is not identical to original
    while scrambled == name and len(name) > 1:
        random.shuffle(name_list)
        scrambled = "".join(name_list)

    active_games[chat_id] = {
        "type": "scribble",
        "answer": name,
        "created_at": time.time(),
        "is_auto": False
    }

    r_emoji = get_rarity_emoji(pokemon.rarity)

    text = (
        f"✏️ **POKÉMON SCRIBBLE** ✏️\n"
        f"───────────────\n\n"
        f"Unscramble this Pokémon's name:\n"
        f"👉 **`{scrambled.upper()}`**\n\n"
        f"✨ **Rarity**: {r_emoji} `{pokemon.rarity}`\n"
        f"🧬 **Generation**: `Gen {pokemon.generation}`\n\n"
        f"👉 Type the correct name to win 💰 **100 coins**! (Ends in 60s)"
    )
    await message.answer(text, parse_mode="Markdown")

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
        del active_games[chat_id]
        await message.answer("⏳ **Time is up!** No one guessed the correct answer in time.")
        
        # Automatically trigger next scribble game in group chats
        if message.chat.type in ["group", "supergroup"]:
            await start_auto_scribble_game(chat_id, message, db)
        return

    guess = message.text.strip().lower()
    correct_answer = game["answer"]

    # Check multiple choice option mapping for trivia
    if game["type"] == "trivia" and "options" in game:
        if guess in ["a", "b", "c", "d"]:
            guess = game["options"][guess]

    if guess == correct_answer:
        user_id = message.from_user.id
        nickname = message.from_user.first_name

        # Query/Register user
        stmt = select(User).where(User.id == user_id)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()

        if not user:
            user = User(id=user_id, username=message.from_user.username, nickname=nickname)
            db.add(user)
            await db.flush()

        # Group automatic scribble games award a random reward between 10 and 50 coins
        if message.chat.type in ["group", "supergroup"] and game.get("is_auto"):
            reward = random.randint(10, 50)
        else:
            reward = 100

        user.coins += reward
        await db.commit()

        # Clear active game
        del active_games[chat_id]

        game_title = "Trivia" if game["type"] == "trivia" else "Scribble"
        text = (
            f"🎉 **{game_title.upper()} CHAMPION!** 🎉\n"
            f"───────────────\n"
            f"Trainer **{escape_md(user.nickname)}** answered correctly!\n\n"
            f"💡 Correct Answer: **{escape_md(correct_answer.title())}**\n"
            f"💰 Reward: **+{reward} coins**\n"
            f"Balance: 💰 **{user.coins} coins**."
        )
        await message.answer(text, parse_mode="Markdown")

        # Automatically start another scribble game in group chats
        if message.chat.type in ["group", "supergroup"]:
            await start_auto_scribble_game(chat_id, message, db)

# Automatic trigger: starts a scribble game when conversation happens in group chat with no active game
def no_active_game_in_group(message: Message) -> bool:
    return message.chat.type in ["group", "supergroup"] and message.chat.id not in active_games

@router.message(F.text, ~F.text.startswith("/"), no_active_game_in_group)
async def auto_start_scribble(message: Message, db: AsyncSession):
    await start_auto_scribble_game(message.chat.id, message, db)

@router.callback_query(F.data == "dm_games")
async def cb_dm_games(callback: CallbackQuery, db: AsyncSession):
    text = (
        f"🎮 **GAMES CENTER** 🎮\n"
        f"───────────────\n\n"
        f"Welcome to the PokéEmpire Games Center! Earn coins by playing these games:\n\n"
        f"📅 **Daily Reward** (24h cooldown)\n"
        f"🎡 **Lucky Spin** (4h cooldown)\n"
        f"🪙 **Coinflip**: `/coinflip <bet> <heads/tails>`\n"
        f"✊ **Rock-Paper-Scissors**: `/rps <bet> <rock/paper/scissors>`\n"
        f"❓ **Pokémon Trivia**: Test your knowledge!\n"
        f"✏️ **Pokémon Scribble**: Unscramble species names!\n"
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
    builder.row(InlineKeyboardButton(text="🔙 Back to Hub Menu", callback_data="dm_home"))
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

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

    now = datetime.now()
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
    user_id = callback.from_user.id
    nickname = callback.from_user.first_name

    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user:
        user = User(id=user_id, username=callback.from_user.username, nickname=nickname)
        db.add(user)
        await db.flush()

    now = datetime.now()
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
    chat_id = callback.message.chat.id

    if chat_id in active_games:
        await callback.answer("⚠️ An active game is already running in this chat!", show_alert=True)
        return

    trivia_text = await initiate_trivia_game(chat_id, db, is_auto=False)
    if not trivia_text:
        await callback.answer("❌ Error initiating trivia.", show_alert=True)
        return

    await callback.message.answer(trivia_text, parse_mode="Markdown")
    await callback.answer("Trivia started!")

@router.callback_query(F.data == "play_scribble")
async def cb_play_scribble(callback: CallbackQuery, db: AsyncSession):
    chat_id = callback.message.chat.id

    if chat_id in active_games:
        await callback.answer("⚠️ An active game is already running in this chat!", show_alert=True)
        return

    # Select random Pokémon
    random_id = random.randint(1, 1025)
    stmt = select(Pokemon).where(Pokemon.id == random_id)
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

    r_emoji = get_rarity_emoji(pokemon.rarity)

    text = (
        f"✏️ **POKÉMON SCRIBBLE** ✏️\n"
        f"───────────────\n\n"
        f"Unscramble this Pokémon's name:\n"
        f"👉 **`{scrambled.upper()}`**\n\n"
        f"✨ **Rarity**: {r_emoji} `{pokemon.rarity}`\n"
        f"🧬 **Generation**: `Gen {pokemon.generation}`\n\n"
        f"👉 Type the correct name to win 💰 **100 coins**! (Ends in 60s)\n"
        f"───────────────"
    )
    
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer("Scribble started!")
