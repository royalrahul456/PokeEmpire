import random
import asyncio
import time
import os
import json
from typing import Optional, Tuple
from datetime import datetime, timedelta
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
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
    set_nameguess_status
)
from keyboards.inline import get_back_to_hub_keyboard

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
                        is_official = (chat.username == "pokeempireunion")
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
                        is_official = (chat.username == "pokeempireunion")
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
            InlineKeyboardButton(text="🔍 Hint", callback_data="scribble_hint"),
            InlineKeyboardButton(text="🚫 Stop Game", callback_data="scribble_stop")
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

        active_games[chat_id] = {
            "type": "nameguess",
            "answer": name,
            "created_at": time.time(),
            "is_auto": True
        }

        # Format message in clean card style with photo
        text = (
            f"🧠 **Guess The Pokémon!**\n"
            f"───────────────\n"
            f"💭 **Think you know this Pokémon?**\n"
            f"⌛ **You have 60 seconds!**\n"
            f"💰 **Reward**: `100-200 coins`"
        )
        
        # Add inline buttons
        builder = InlineKeyboardBuilder()
        builder.row(
            InlineKeyboardButton(text="🔍 Hint", callback_data="nameguess_hint"),
            InlineKeyboardButton(text="🚫 Stop Game", callback_data="nameguess_stop")
        )
        
        sent_msg = await bot.send_photo(
            chat_id=chat_id,
            photo=pokemon.image_url,
            caption=text,
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        
        active_games[chat_id]["message_id"] = sent_msg.message_id
        
        # Start background timeout task
        asyncio.create_task(nameguess_timeout_task(chat_id, sent_msg.message_id, bot))
        
    except Exception as e:
        # Clean up lock on error
        if chat_id in active_games and active_games[chat_id].get("type") == "initializing":
            del active_games[chat_id]
        raise e

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
                text = (
                    f"⏳ <b>TRIVIA EXPIRED</b> ⏳\n"
                    f"───────────────\n\n"
                    f"<b>Question:</b>\n"
                    f"{game['question']}\n\n"
                    f"❌ Time is up! No one answered in time.\n"
                    f"💡 Correct Answer: <b>{game['answer']}</b>"
                )
                msg = await bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=text,
                    reply_markup=None,
                    parse_mode="HTML"
                )
                asyncio.create_task(delete_message_after(msg, 60))
            except Exception:
                pass

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

    text = (
        f"❓ <b>POKÉMON TRIVIA</b> ❓\n"
        f"───────────────\n\n"
        f"<b>Question:</b>\n"
        f"{q_data['question']}\n\n"
        f"👉 Select the correct option below! You get only <b>one guess</b>! (Ends in 60s)"
    )
    return text, builder.as_markup()

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
    chat_id = message.chat.id

    if message.chat.type in ["group", "supergroup"]:
        if message.chat.username != "pokeempireunion":
            builder = InlineKeyboardBuilder()
            builder.row(InlineKeyboardButton(text="🔗 Join Official GC", url="https://t.me/pokeempireunion"))
            await message.answer(
                "⚠️ <b>Scribble and Nameguess games are only available in our official group chat!</b>\n\n"
                "Join us there to play and win coins!",
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
            return
        else:
            await message.answer("✏️ <b>Scribble</b> runs automatically in this group chat all the time! Keep an eye out for active words.")
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

    guess = message.text.strip().lower()
    correct_answer = game["answer"]

    if guess == correct_answer:
        from aiogram.types import ReactionTypeEmoji
        try:
            await message.react(reactions=[ReactionTypeEmoji(emoji="🎉")])
        except Exception as e:
            print(f"Failed to react to game guess: {e}")

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

        # Determine reward
        if game.get("type") == "nameguess":
            if message.chat.type in ["group", "supergroup"] and game.get("is_auto"):
                reward = random.randint(100, 200)
            else:
                reward = 150
        else: # scribble
            if message.chat.type in ["group", "supergroup"] and game.get("is_auto"):
                reward = random.randint(10, 50)
            else:
                reward = 100

        user.coins += reward
        await db.commit()

        # Clear active game and delete prompt/hint messages
        del active_games[chat_id]
        if game.get("type") == "nameguess":
            await cleanup_nameguess_messages(message.bot, chat_id, game)
        else:
            await cleanup_scribble_messages(message.bot, chat_id, game)

        # Format victory message in clean card style
        if game.get("type") == "nameguess":
            text = (
                f"🎉 <b>Correct!</b>\n"
                f"───────────────\n"
                f"🧠 <b>Pokémon</b>: {correct_answer.title()}\n"
                f"💰 <b>Earned</b>: +{reward} coins\n"
                f"👥 <b>Winner</b>: {message.from_user.mention_html()}"
            )
        else:
            text = (
                f"🎉 <b>Correct!</b>\n"
                f"───────────────\n"
                f"🛑 <b>Word</b>: {correct_answer.title()}\n"
                f"💰 <b>Earned</b>: +{reward} coins\n"
                f"👥 <b>Winner</b>: {message.from_user.mention_html()}"
            )

        victory_msg = await message.reply(text, parse_mode="HTML")
        asyncio.create_task(delete_message_after(victory_msg, 60))

        # Automatically start another game in group chats if enabled
        if message.chat.type in ["group", "supergroup"] and message.chat.username == "pokeempireunion":
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

# Automatic trigger: starts a scribble/nameguess game when conversation happens in group chat with no active game
def no_active_game_in_group(message: Message) -> bool:
    if message.chat.type not in ["group", "supergroup"]:
        return False
    if message.chat.username != "pokeempireunion":
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
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "play_mines")
async def cb_play_mines(callback: CallbackQuery):
    text = (
        f"💣 **MINES GAME** 💣\n"
        f"───────────────\n"
        f"Test your luck in a 5x5 grid! Place a bet, choose how many mines (1-24) to hide, and reveal tiles. "
        f"Each diamond you find increases your multiplier. Cash out before hitting a mine!\n\n"
        f"👉 **To start playing, send**:\n"
        f"• `/mines <bet> [mines_count]` in DM\n"
        f"  _(e.g. <code>/mines 100 3</code> starts a game with a 100 coin bet and 3 hidden mines)_\n\n"
        f"⚠️ Default mines count is 3. Bets must be between 10 and 100,000 coins."
    )
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Back to Games", callback_data="dm_games"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
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
        await callback.answer("⚠️ No active nameguess game in this chat.", show_alert=True)
        return
        
    game = active_games[chat_id]
    if game.get("type") != "nameguess":
        await callback.answer("⚠️ No active nameguess game in this chat.", show_alert=True)
        return
        
    # Check if hint already exists to avoid spamming
    if "hint_text" in game:
        hint_text = game["hint_text"]
        await callback.answer(f"💡 Hint already sent: {hint_text}", show_alert=True)
        return
        
    # Generate hint
    hint_text = generate_hint(game["answer"])
    game["hint_text"] = hint_text
    
    # Send the hint message (replying to the photo message)
    hint_msg = await callback.message.reply(
        f"💡 **Nameguess Hint**\n"
        f"───────────────\n"
        f"👉 `{hint_text}`",
        parse_mode="Markdown"
    )
    
    game["hint_message_id"] = hint_msg.message_id
    await callback.answer("Hint generated!")


@router.callback_query(F.data == "nameguess_stop")
async def cb_nameguess_stop(callback: CallbackQuery):
    chat_id = callback.message.chat.id
    user_id = callback.from_user.id
    
    if chat_id not in active_games:
        await callback.answer("⚠️ No active nameguess game to stop.", show_alert=True)
        return
        
    game = active_games[chat_id]
    if game.get("type") != "nameguess":
        await callback.answer("⚠️ No active nameguess game to stop.", show_alert=True)
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
    
    # Delete the prompt photo and hint messages
    await cleanup_nameguess_messages(callback.bot, chat_id, game)
    
    # Send game stopped notification
    await callback.message.answer(f"🛑 **Nameguess game stopped** by {callback.from_user.first_name}.")
    await callback.answer("Game stopped!")


@router.message(Command("nameguess"))
@router.message(Command("guess"))
async def cmd_nameguess(message: Message, db: AsyncSession):
    chat_id = message.chat.id
    user_id = message.from_user.id

    if message.chat.type in ["group", "supergroup"]:
        if message.chat.username != "pokeempireunion":
            builder = InlineKeyboardBuilder()
            builder.row(InlineKeyboardButton(text="🔗 Join Official GC", url="https://t.me/pokeempireunion"))
            await message.answer(
                "⚠️ <b>Scribble and Nameguess games are only available in our official group chat!</b>\n\n"
                "Join us there to play and win coins!",
                reply_markup=builder.as_markup(),
                parse_mode="HTML"
            )
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
        await message.answer("❌ Error initiating nameguess. Try again.")
        return

    name = pokemon.name.lower()

    active_games[chat_id] = {
        "type": "nameguess",
        "answer": name,
        "created_at": time.time(),
        "is_auto": False
    }

    text = (
        f"🧠 **Guess The Pokémon!**\n"
        f"───────────────\n"
        f"💭 **Think you know this Pokémon?**\n"
        f"⌛ **You have 60 seconds!**\n"
        f"💰 **Reward**: `150 coins`"
    )
    
    # Add inline buttons
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔍 Hint", callback_data="nameguess_hint"),
        InlineKeyboardButton(text="🚫 Stop Game", callback_data="nameguess_stop")
    )

    try:
        sent_msg = await message.answer_photo(
            photo=pokemon.image_url,
            caption=text,
            reply_markup=builder.as_markup(),
            parse_mode="Markdown"
        )
        active_games[chat_id]["message_id"] = sent_msg.message_id
        
        # Start background timeout task
        asyncio.create_task(nameguess_timeout_task(chat_id, sent_msg.message_id, message.bot))
    except Exception as e:
        if chat_id in active_games:
            del active_games[chat_id]
        print(f"Error sending nameguess photo: {e}")
        await message.answer("❌ Error initiating nameguess. Make sure the bot has permission to send photos.")

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

        reward = 100
        user.coins += reward
        await db.commit()

        del active_games[chat_id]

        text = (
            f"🎉 <b>TRIVIA CHAMPION!</b> 🎉\n"
            f"───────────────\n\n"
            f"<b>Question:</b>\n"
            f"{game['question']}\n\n"
            f"💡 Correct Answer: <b>{game['answer']}</b>\n"
            f"🏆 Winner: Trainer <b>{escape_md(user.nickname)}</b>\n"
            f"💰 Reward: <b>+{reward} coins</b>\n"
            f"Balance: 💰 <b>{user.coins} coins</b>.\n"
            f"───────────────"
        )
        
        msg = await callback.message.edit_text(text, reply_markup=None, parse_mode="HTML")
        await callback.answer("🎉 Correct answer!")
        asyncio.create_task(delete_message_after(msg, 60))
    else:
        await callback.answer("❌ Incorrect answer! You are locked out of this question.", show_alert=True)
        
        if callback.message.chat.type == "private":
            del active_games[chat_id]
            msg = await callback.message.edit_text(
                f"❓ <b>TRIVIA OVER</b> ❓\n"
                f"───────────────\n\n"
                f"❌ You guessed incorrectly!\n\n"
                f"💡 Correct Answer: <b>{game['answer']}</b>\n"
                f"───────────────",
                reply_markup=None,
                parse_mode="HTML"
            )
            asyncio.create_task(delete_message_after(msg, 60))

@router.message(Command("streak"))
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
    from utils.formatters import escape_md
    
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
        f" 🔥 **Daily Streak — {escape_md(user.nickname)}**\n\n"
        f"💧 **Status**: `{status_str}`\n"
        f"🎁 **Current**: `{current_days} days`\n"
        f"🏆 **Best**: `{best_days} days`\n"
        f"🏆 **Rank**: `{rank_str}`\n"
        f"🎁 **Progress**: `[{bar_chars}] {capped_count}/3`\n\n"
        f"👉 *Catch 3 Pokémon every day to keep your streak!*"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(Command("streaklb"))
@router.message(Command("slb"))
async def cmd_streak_leaderboard(message: Message, db: AsyncSession):
    from utils.streak import get_top_streaks
    from utils.formatters import escape_md
    
    top_users = await get_top_streaks(10)
    
    if not top_users:
        await message.answer("🏆 **STREAK LEADERBOARD** 🏆\n───────────────\n\n• *No active streaks recorded yet.*")
        return
        
    # Query nicknames and usernames for the top users
    uids = [uid for uid, _ in top_users]
    u_stmt = select(User).where(User.id.in_(uids))
    u_res = await db.execute(u_stmt)
    users_dict = {u.id: u for u in u_res.scalars().all()}
    
    rows = []
    for idx, (uid, uinfo) in enumerate(top_users):
        rank_prefix = "🥇" if idx == 0 else "🥈" if idx == 1 else "🥉" if idx == 2 else f"{idx + 1}."
        user = users_dict.get(uid)
        nickname = user.nickname if user else f"Trainer_{uid}"
        username_str = f" (@{escape_md(user.username)})" if user and user.username else ""
        
        best = uinfo.get("best_streak", 0)
        curr = uinfo.get("current_streak", 0)
        rows.append(f"{rank_prefix} **{escape_md(nickname)}**{username_str} • Best: `{best}d` (Current: `{curr}d`)")
        
    leaderboard_card = (
        f"🔥 **DAILY STREAK LEADERBOARD** 🔥\n"
        f"───────────────\n\n"
        f"{'\n'.join(rows)}\n\n"
        f"───────────────"
    )
    await message.answer(leaderboard_card, parse_mode="Markdown")

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
    from utils.formatters import escape_md
    from keyboards.inline import get_back_to_hub_keyboard
    
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
        f" 🔥 **Daily Streak — {escape_md(user.nickname)}**\n\n"
        f"💧 **Status**: `{status_str}`\n"
        f"🎁 **Current**: `{current_days} days`\n"
        f"🏆 **Best**: `{best_days} days`\n"
        f"🏆 **Rank**: `{rank_str}`\n"
        f"🎁 **Progress**: `[{bar_chars}] {capped_count}/3`\n\n"
        f"👉 *Catch 3 Pokémon every day to keep your streak!*"
    )
    await callback.message.edit_text(text, reply_markup=get_back_to_hub_keyboard(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "dm_leaderboard")
async def cb_dm_leaderboard(callback: CallbackQuery):
    text = (
        "\ud83d\udcca **LEADERBOARD**\n"
        "\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\n\n"
        "View rankings across all trainers!\n\n"
        "\ud83d\udc49 **Commands:**\n"
        "\u2022 `/leaderboard` or `/lb` \u2014 Top trainers by coins\n"
        "\u2022 `/streaklb` or `/slb` \u2014 Top streak holders\n"
    )
    await callback.message.edit_text(text, reply_markup=get_back_to_hub_keyboard(), parse_mode="Markdown")
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
    await callback.message.edit_text(text, reply_markup=get_back_to_hub_keyboard(), parse_mode="Markdown")
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
    await callback.message.edit_text(text, reply_markup=get_back_to_hub_keyboard(), parse_mode="Markdown")
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
    await callback.message.edit_text(text, reply_markup=get_back_to_hub_keyboard(), parse_mode="Markdown")
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
    await callback.message.edit_text(text, reply_markup=get_back_to_hub_keyboard(), parse_mode="Markdown")
    await callback.answer()
