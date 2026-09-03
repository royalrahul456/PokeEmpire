import json
import random
import asyncio
from typing import Optional, Dict, Any, List

from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, desc, func

import config
from database.models import User, UserPokemon, PvpBattle, Pokemon
from utils.formatters import escape_md, get_rarity_emoji

router = Router()

def get_pokemon_moves(pokemon_name: str) -> list:
    name = pokemon_name.lower()
    if any(x in name for x in ["char", "fire", "burn", "flare", "growlithe", "moltres"]):
        return [
            {"name": "Flamethrower", "power": 90, "accuracy": 1.0},
            {"name": "Fire Blast", "power": 110, "accuracy": 0.85},
            {"name": "Dragon Claw", "power": 80, "accuracy": 1.0},
            {"name": "Slash", "power": 70, "accuracy": 1.0}
        ]
    elif any(x in name for x in ["squirt", "water", "aqua", "hydro", "blastoise", "gyarados"]):
        return [
            {"name": "Hydro Pump", "power": 110, "accuracy": 0.85},
            {"name": "Surf", "power": 90, "accuracy": 1.0},
            {"name": "Ice Beam", "power": 90, "accuracy": 1.0},
            {"name": "Skull Bash", "power": 100, "accuracy": 1.0}
        ]
    elif any(x in name for x in ["bulb", "saur", "grass", "vine", "leaf", "oddish"]):
        return [
            {"name": "Solar Beam", "power": 120, "accuracy": 1.0},
            {"name": "Razor Leaf", "power": 55, "accuracy": 0.95},
            {"name": "Sludge Bomb", "power": 90, "accuracy": 1.0},
            {"name": "Body Slam", "power": 85, "accuracy": 1.0}
        ]
    elif any(x in name for x in ["pika", "electric", "spark", "thunder", "zapdos"]):
        return [
            {"name": "Thunderbolt", "power": 90, "accuracy": 1.0},
            {"name": "Thunder", "power": 110, "accuracy": 0.7},
            {"name": "Iron Tail", "power": 100, "accuracy": 0.75},
            {"name": "Quick Attack", "power": 40, "accuracy": 1.0}
        ]
    elif any(x in name for x in ["gengar", "ghost", "shadow", "gastly"]):
        return [
            {"name": "Shadow Ball", "power": 80, "accuracy": 1.0},
            {"name": "Dark Pulse", "power": 80, "accuracy": 1.0},
            {"name": "Psychic", "power": 90, "accuracy": 1.0},
            {"name": "Sludge Wave", "power": 95, "accuracy": 1.0}
        ]
    else:
        return [
            {"name": "Hyper Beam", "power": 150, "accuracy": 0.9},
            {"name": "Double Edge", "power": 120, "accuracy": 1.0},
            {"name": "Swift", "power": 60, "accuracy": 1.0},
            {"name": "Tackle", "power": 40, "accuracy": 1.0}
        ]

def get_hp_bar_battle(current: int, max_hp: int, length: int = 10) -> str:
    if max_hp <= 0:
        return "░" * length
    
    percent = max(0.0, min(1.0, current / max_hp))
    filled_len = int(round(length * percent))
    if current > 0 and filled_len == 0:
        filled_len = 1
    elif current <= 0:
        filled_len = 0
        
    bar = "█" * filled_len + "░" * (length - filled_len)
    
    color_emoji = "🟢"
    if percent <= 0.2:
        color_emoji = "🔴"
    elif percent <= 0.5:
        color_emoji = "🟡"
        
    return f"`[{bar}]` {color_emoji} **{current}/{max_hp}**"

@router.message(Command("battle"))
@router.message(Command("duel"))
async def cmd_battle(message: Message, db: AsyncSession):
    if message.chat.type == "private":
        await message.answer("⚠️ PvP Battles can only be started in group chats.")
        return

    parts = message.text.split()
    if len(parts) < 3:
        await message.answer(
            "⚠️ **Format**: `/battle <bet_amount/nocoin> <@username>`\n"
            "(e.g., `/battle 1000 @opponent` or `/battle nocoin @opponent`)"
        )
        return

    # Flexible arg parsing
    bet = 0
    opponent_username = ""
    
    if parts[1].startswith("@"):
        opponent_username = parts[1]
        bet_part = parts[2]
    else:
        bet_part = parts[1]
        opponent_username = parts[2]
        
    opponent_username = opponent_username.replace("@", "").strip()
    
    # Parse bet_part
    if bet_part.isdigit():
        bet = int(bet_part)
    elif bet_part.lower() in ["nocoin", "friendly", "0", "free", "no"]:
        bet = 0
    else:
        await message.answer("⚠️ Invalid bet amount. Use a positive number or `nocoin`.")
        return

    # Check for active battle involvements
    active_stmt = select(PvpBattle).where(
        (PvpBattle.challenger_id == message.from_user.id) | (PvpBattle.opponent_id == message.from_user.id)
    ).where(PvpBattle.status.in_(["WAITING", "DRAFTING", "SIMULATING"]))
    active_res = await db.execute(active_stmt)
    if active_res.scalars().first():
        await message.answer("⚠️ You are already involved in an active battle challenge, draft, or simulation!")
        return

    # Check challenger registration & coins
    challenger_stmt = select(User).where(User.id == message.from_user.id)
    challenger_res = await db.execute(challenger_stmt)
    challenger = challenger_res.scalar_one_or_none()
    if not challenger:
        await message.answer("⚠️ You must register first with /start")
        return
        
    if challenger.coins < bet:
        await message.answer(f"❌ You do not have enough coins! You only have 🪙 **{challenger.coins} Coins**.")
        return

    # Look up opponent
    opponent_stmt = select(User).where(User.username.ilike(opponent_username))
    opponent_res = await db.execute(opponent_stmt)
    opponent = opponent_res.scalar_one_or_none()
    if not opponent:
        await message.answer(f"❌ Trainer **@{opponent_username}** not found in database. Make sure they have registered with /start.")
        return
        
    if opponent.id == challenger.id:
        await message.answer("❌ You cannot battle yourself!")
        return
        
    if opponent.coins < bet:
        await message.answer(f"❌ Opponent **@{opponent_username}** does not have enough coins to cover this bet! (Required: 🪙 **{bet}**)")
        return

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⚔️ Accept 3v3", callback_data=f"pvp_accept_3_{challenger.id}_{opponent.id}_{bet}"),
            InlineKeyboardButton(text="⚔️ Accept 6v6", callback_data=f"pvp_accept_6_{challenger.id}_{opponent.id}_{bet}")
        ],
        [
            InlineKeyboardButton(text="❌ Decline", callback_data=f"pvp_decline_{challenger.id}_{opponent.id}")
        ]
    ])
    
    wager_str = f"🪙 `{bet:,} Coins`" if bet > 0 else "`None (Friendly)`"
    text = (
        f"⚔️ **PVP BATTLE CHALLENGE** ⚔️\n"
        f"───────────────\n"
        f"👤 **Challenger**: {escape_md(challenger.nickname or message.from_user.first_name)} (@{escape_md(challenger.username)})\n"
        f"👤 **Opponent**: {escape_md(opponent.nickname or opponent_username)} (@{escape_md(opponent.username)})\n"
        f"💰 **Wager**: {wager_str}\n"
        f"───────────────\n"
        f"@{opponent.username}, do you accept this challenge?"
    )
    
    await message.answer(text, reply_markup=kb, parse_mode="Markdown")

@router.callback_query(F.data.startswith("pvp_decline_"))
async def cb_pvp_decline(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    opponent_id = int(parts[3])
    
    if callback.from_user.id != opponent_id:
        await callback.answer("❌ You are not the challenged opponent!", show_alert=True)
        return
        
    await callback.message.edit_text("❌ Battle challenge was declined.", reply_markup=None)
    await callback.answer()

@router.callback_query(F.data.startswith("pvp_accept_"))
async def cb_pvp_accept(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    format_type = int(parts[2])
    challenger_id = int(parts[3])
    opponent_id = int(parts[4])
    bet = int(parts[5])
    
    if callback.from_user.id != opponent_id:
        await callback.answer("❌ You are not the challenged opponent!", show_alert=True)
        return
        
    # Re-verify coins
    c_stmt = select(User).where(User.id == challenger_id)
    c_res = await db.execute(c_stmt)
    challenger = c_res.scalar_one_or_none()
    
    o_stmt = select(User).where(User.id == opponent_id)
    o_res = await db.execute(o_stmt)
    opponent = o_res.scalar_one_or_none()
    
    if not challenger or not opponent:
        await callback.answer("⚠️ Player data not found.")
        return
        
    if challenger.coins < bet or opponent.coins < bet:
        await callback.message.edit_text("❌ Challenge cancelled: One of the players no longer has enough coins.", reply_markup=None)
        await callback.answer()
        return

    # Check Pokémon counts
    c_count = await db.scalar(select(func.count(UserPokemon.id)).where(UserPokemon.user_id == challenger_id))
    o_count = await db.scalar(select(func.count(UserPokemon.id)).where(UserPokemon.user_id == opponent_id))
    
    if c_count < format_type:
        await callback.message.edit_text(
            f"❌ Challenge cancelled: {escape_md(challenger.nickname or 'Challenger')} does not own at least {format_type} Pokémon.",
            reply_markup=None
        )
        await callback.answer()
        return
        
    if o_count < format_type:
        await callback.message.edit_text(
            f"❌ Challenge cancelled: {escape_md(opponent.nickname or 'Opponent')} does not own at least {format_type} Pokémon.",
            reply_markup=None
        )
        await callback.answer()
        return

    if bet > 0:
        challenger.coins -= bet
        opponent.coins -= bet
        from utils.trainer_level import log_transaction
        await log_transaction(challenger_id, -bet, "PVP_BET", f"PvP Battle Wager vs {opponent.nickname or opponent.id}", db)
        await log_transaction(opponent_id, -bet, "PVP_BET", f"PvP Battle Wager vs {challenger.nickname or challenger.id}", db)

    # Create PvpBattle record
    battle = PvpBattle(
        chat_id=callback.message.chat.id,
        message_id=callback.message.message_id,
        challenger_id=challenger_id,
        opponent_id=opponent_id,
        bet=bet,
        format_type=format_type,
        status="DRAFTING",
        draft_json=json.dumps({
            "challenger": {
                "drafted": [],
                "selecting_up_id": None
            },
            "opponent": {
                "drafted": [],
                "selecting_up_id": None
            }
        })
    )
    db.add(battle)
    await db.commit()
    
    await callback.message.edit_text(
        f"📝 **DRAFT STAGE ACTIVE** 📝\n"
        f"───────────────\n"
        f"Challenger and Opponent, please check your private DMs to draft your **{format_type}** Pokémon!",
        reply_markup=None
    )
    await callback.answer()
    
    # Send draft menus in DM
    await send_draft_menu(callback.bot, db, battle.id, challenger_id, page=1)
    await send_draft_menu(callback.bot, db, battle.id, opponent_id, page=1)

async def send_draft_menu(bot: Bot, db: AsyncSession, battle_id: int, user_id: int, page: int = 1, edit_message_id: Optional[int] = None):
    battle_stmt = select(PvpBattle).where(PvpBattle.id == battle_id)
    battle_res = await db.execute(battle_stmt)
    battle = battle_res.scalar_one_or_none()
    if not battle: return
        
    draft_data = json.loads(battle.draft_json)
    player_role = "challenger" if user_id == battle.challenger_id else "opponent"
    drafted_count = len(draft_data[player_role]["drafted"])
    
    poke_stmt = select(UserPokemon, Pokemon).join(Pokemon).where(UserPokemon.user_id == user_id).order_by(UserPokemon.caught_at.desc())
    poke_res = await db.execute(poke_stmt)
    user_pokes = poke_res.all()
    
    already_drafted_ids = [d["up_id"] for d in draft_data[player_role]["drafted"]]
    available_pokes = [t for t in user_pokes if t[0].id not in already_drafted_ids]
    
    total_avail = len(available_pokes)
    page_size = 5
    total_pages = max(1, (total_avail + page_size - 1) // page_size)
    
    if page < 1: page = 1
    if page > total_pages: page = total_pages
    
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_pokes = available_pokes[start_idx:end_idx]
    
    text = (
        f"📥 **PVP DRAFT SELECTION** ({drafted_count + 1}/{battle.format_type}) 📥\n"
        f"───────────────\n"
        f"Select Pokémon **#{drafted_count + 1}** for your team:\n"
    )
    
    kb_rows = []
    form_names_button = {
        0: "Standard",
        1: "AMV",
        2: "Dmax",
        3: "Gmax",
        4: "Z-Move",
        5: "Terastal"
    }
    
    for up, p in page_pokes:
        f_name = form_names_button.get(up.form_index, f"Form {up.form_index}")
        shiny_tag = "✨ " if up.is_shiny else ""
        button_text = f"{shiny_tag}{p.name.title()} ({f_name})"
        kb_rows.append([
            InlineKeyboardButton(
                text=button_text,
                callback_data=f"pvpdraft_sel_{battle_id}_{up.id}"
            )
        ])
        
    if total_pages > 1:
        prev_p = page - 1 if page > 1 else total_pages
        next_p = page + 1 if page < total_pages else 1
        kb_rows.append([
            InlineKeyboardButton(text="⬅️ Prev", callback_data=f"pvpdraft_page_{battle_id}_{prev_p}"),
            InlineKeyboardButton(text=f"{page}/{total_pages}", callback_data="pvpdraft_noop"),
            InlineKeyboardButton(text="Next ➡️", callback_data=f"pvpdraft_page_{battle_id}_{next_p}")
        ])
        
    reply_markup = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    
    if edit_message_id:
        try:
            await bot.edit_message_text(
                text=text,
                chat_id=user_id,
                message_id=edit_message_id,
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        except Exception:
            await bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        await bot.send_message(chat_id=user_id, text=text, reply_markup=reply_markup, parse_mode="Markdown")

@router.callback_query(F.data.startswith("pvpdraft_page_"))
async def cb_pvpdraft_page(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    battle_id = int(parts[2])
    page = int(parts[3])
    user_id = callback.from_user.id
    
    await send_draft_menu(callback.bot, db, battle_id, user_id, page=page, edit_message_id=callback.message.message_id)
    await callback.answer()

@router.callback_query(F.data.startswith("pvpdraft_sel_"))
async def cb_pvpdraft_sel(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    battle_id = int(parts[2])
    up_id = int(parts[3])
    user_id = callback.from_user.id
    
    battle_stmt = select(PvpBattle).where(PvpBattle.id == battle_id)
    battle_res = await db.execute(battle_stmt)
    battle = battle_res.scalar_one_or_none()
    if not battle or battle.status != "DRAFTING":
        await callback.answer("⚠️ Battle draft is no longer active.")
        return
        
    draft_data = json.loads(battle.draft_json)
    player_role = "challenger" if user_id == battle.challenger_id else "opponent"
    
    draft_data[player_role]["selecting_up_id"] = up_id
    battle.draft_json = json.dumps(draft_data)
    await db.commit()
    
    up_stmt = select(UserPokemon, Pokemon).join(Pokemon).where(UserPokemon.id == up_id)
    up_res = await db.execute(up_stmt)
    up_data = up_res.first()
    if not up_data:
        await callback.answer("⚠️ Pokémon not found.")
        return
        
    up, p = up_data
    
    moves = get_pokemon_moves(p.name)
    kb_rows = []
    for m in moves:
        kb_rows.append([
            InlineKeyboardButton(
                text=f"{m['name']} (Pwr: {m['power']})",
                callback_data=f"pvpdraft_mov_{battle_id}_{m['name']}"
            )
        ])
        
    reply_markup = InlineKeyboardMarkup(inline_keyboard=kb_rows)
    await callback.message.edit_text(
        text=f"⚔️ **SELECT MOVE** ⚔️\nSelect a primary move for your **{p.name.title()}**:",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("pvpdraft_mov_"))
async def cb_pvpdraft_mov(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    battle_id = int(parts[2])
    move_name = parts[3]
    user_id = callback.from_user.id
    
    battle_stmt = select(PvpBattle).where(PvpBattle.id == battle_id)
    battle_res = await db.execute(battle_stmt)
    battle = battle_res.scalar_one_or_none()
    if not battle or battle.status != "DRAFTING":
        await callback.answer("⚠️ Battle draft is no longer active.")
        return
        
    draft_data = json.loads(battle.draft_json)
    player_role = "challenger" if user_id == battle.challenger_id else "opponent"
    
    up_id = draft_data[player_role]["selecting_up_id"]
    if not up_id:
        await callback.answer("⚠️ No active Pokémon selection found.")
        return
        
    up_stmt = select(UserPokemon, Pokemon).join(Pokemon).where(UserPokemon.id == up_id)
    up_res = await db.execute(up_stmt)
    up_data = up_res.first()
    if not up_data:
        await callback.answer("⚠️ Pokémon details not found.")
        return
        
    up, p = up_data
    
    # Calculate stats
    from services.spawn_system import SpawnSystem
    spawn_sys = SpawnSystem()
    p_spec = spawn_sys.monsters_db.get(p.name.lower(), {
        "base_stats": {"hp": 60, "atk": 60, "def": 60, "spd": 60, "sp_atk": 60, "sp_def": 60}
    })
    
    ivs = {"hp": up.iv_hp, "atk": up.iv_atk, "def": up.iv_def, "spd": up.iv_spd}
    stats = SpawnSystem.calculate_stats(p_spec["base_stats"], ivs, up.level)
    max_hp = stats["hp"]
    
    drafted_poke = {
        "up_id": up.id,
        "pokemon_id": p.id,
        "name": p.name.title(),
        "move": move_name,
        "level": up.level,
        "hp": max_hp,
        "max_hp": max_hp,
        "atk": stats["atk"],
        "def": stats["def"],
        "spd": stats["spd"],
        "image_url": p.image_url
    }
    
    draft_data[player_role]["drafted"].append(drafted_poke)
    draft_data[player_role]["selecting_up_id"] = None
    battle.draft_json = json.dumps(draft_data)
    await db.commit()
    
    await callback.answer(f"Added {p.name.title()}!")
    
    if len(draft_data[player_role]["drafted"]) >= battle.format_type:
        await callback.message.edit_text(
            f"✅ **DRAFT COMPLETED!**\n"
            f"You have selected all **{battle.format_type}** Pokémon.\n"
            f"Waiting for your opponent to complete their draft...",
            reply_markup=None
        )
        
        opponent_role = "opponent" if player_role == "challenger" else "challenger"
        if len(draft_data[opponent_role]["drafted"]) >= battle.format_type:
            battle.status = "SIMULATING"
            await db.commit()
            
            asyncio.create_task(run_battle_simulation(callback.bot, battle.id))
    else:
        await send_draft_menu(callback.bot, db, battle_id, user_id, page=1, edit_message_id=callback.message.message_id)

async def run_battle_simulation(bot: Bot, battle_id: int):
    from database.database import SessionLocal
    async with SessionLocal() as db:
        battle_stmt = select(PvpBattle).where(PvpBattle.id == battle_id)
        battle_res = await db.execute(battle_stmt)
        battle = battle_res.scalar_one_or_none()
        if not battle: return
            
        draft_data = json.loads(battle.draft_json)
        challenger_id = battle.challenger_id
        opponent_id = battle.opponent_id
        chat_id = battle.chat_id
        message_id = battle.message_id
        bet = battle.bet
        format_type = battle.format_type
        
        c_stmt = select(User).where(User.id == challenger_id)
        c_res = await db.execute(c_stmt)
        challenger = c_res.scalar_one_or_none()
        
        o_stmt = select(User).where(User.id == opponent_id)
        o_res = await db.execute(o_stmt)
        opponent = o_res.scalar_one_or_none()
        
        c_name = escape_md(challenger.nickname or "Challenger")
        o_name = escape_md(opponent.nickname or "Opponent")
        
        if bet > 0:
            challenger.coins -= bet
            opponent.coins -= bet
            await db.commit()
            
        c_team = draft_data["challenger"]["drafted"]
        o_team = draft_data["opponent"]["drafted"]
        
        c_team_text = "\n".join([f"• {p['name']} (Move: {p['move']})" for p in c_team])
        o_team_text = "\n".join([f"• {p['name']} (Move: {p['move']})" for p in o_team])
        
        try:
            await bot.send_message(chat_id=challenger_id, text=f"📋 **OPPONENT'S TEAM:**\n{o_name} sent out:\n{o_team_text}")
        except Exception: pass
        try:
            await bot.send_message(chat_id=opponent_id, text=f"📋 **OPPONENT'S TEAM:**\n{c_name} sent out:\n{c_team_text}")
        except Exception: pass
        
        p1_idx = 0
        p2_idx = 0
        logs = ["Battle begins!"]
        round_num = 1
        
        while p1_idx < format_type and p2_idx < format_type:
            p1_mon = c_team[p1_idx]
            p2_mon = o_team[p2_idx]
            
            p1_first = True
            if p1_mon["spd"] > p2_mon["spd"]:
                p1_first = True
            elif p2_mon["spd"] > p1_mon["spd"]:
                p1_first = False
            else:
                p1_first = random.choice([True, False])
                
            async def execute_attack(attacker, defender):
                move_name = attacker["move"]
                move_spec = {"power": 80, "accuracy": 0.95}
                for m in get_pokemon_moves(attacker["name"]):
                    if m["name"] == move_name:
                        move_spec = m
                        break
                        
                if random.random() > move_spec["accuracy"]:
                    return f"💨 {attacker['name']} used **{move_name}** but missed!"
                    
                atk_stat = attacker["atk"]
                def_stat = defender["def"]
                level = attacker["level"]
                power = move_spec["power"]
                
                crit = random.random() < 0.0625
                crit_multiplier = 1.5 if crit else 1.0
                
                base_damage = (((2 * level / 5 + 2) * power * atk_stat / def_stat / 50) + 2)
                damage = int(base_damage * crit_multiplier * random.uniform(0.85, 1.0))
                damage = max(1, damage)
                
                defender["hp"] = max(0, defender["hp"] - damage)
                
                msg = f"⚔️ {attacker['name']} used **{move_name}**! Deals **{damage}** damage."
                if crit:
                    msg = f"💥 **Critical Hit!** {attacker['name']} used **{move_name}**! Deals **{damage}** damage."
                return msg
                
            if p1_first:
                log = await execute_attack(p1_mon, p2_mon)
                logs.append(log)
                if p2_mon["hp"] <= 0:
                    logs.append(f"💀 **{p2_mon['name']}** fainted!")
                    p2_idx += 1
                    if p2_idx < format_type:
                        logs.append(f"👉 {o_name} sent out **{o_team[p2_idx]['name']}**!")
                else:
                    log = await execute_attack(p2_mon, p1_mon)
                    logs.append(log)
                    if p1_mon["hp"] <= 0:
                        logs.append(f"💀 **{p1_mon['name']}** fainted!")
                        p1_idx += 1
                        if p1_idx < format_type:
                            logs.append(f"👉 {c_name} sent out **{c_team[p1_idx]['name']}**!")
            else:
                log = await execute_attack(p2_mon, p1_mon)
                logs.append(log)
                if p1_mon["hp"] <= 0:
                    logs.append(f"💀 **{p1_mon['name']}** fainted!")
                    p1_idx += 1
                    if p1_idx < format_type:
                        logs.append(f"👉 {c_name} sent out **{c_team[p1_idx]['name']}**!")
                else:
                    log = await execute_attack(p1_mon, p2_mon)
                    logs.append(log)
                    if p2_mon["hp"] <= 0:
                        logs.append(f"💀 **{p2_mon['name']}** fainted!")
                        p2_idx += 1
                        if p2_idx < format_type:
                            logs.append(f"👉 {o_name} sent out **{o_team[p2_idx]['name']}**!")
                            
            await render_battle_frame(bot, chat_id, message_id, c_name, o_name, c_team, o_team, p1_idx, p2_idx, logs, round_num)
            round_num += 1
            await asyncio.sleep(1.5)
            
        winner_id = challenger_id if p1_idx < format_type else opponent_id
        winner_name = c_name if winner_id == challenger_id else o_name
        winner_user = challenger if winner_id == challenger_id else opponent
        
        if bet > 0:
            pot = 2 * bet
            winner_user.coins += pot
            from utils.trainer_level import log_transaction
            await log_transaction(winner_id, pot, "PVP_WIN", f"Won PvP Battle Pot ({pot} coins)", db)
            await db.commit()
            win_msg = f"🏆 **{winner_name} wins the battle and takes the pot of 🪙 {pot:,} Coins!**"
        else:
            win_msg = f"🏆 **{winner_name} wins the friendly battle!**"
            
        logs.append(win_msg)
        await render_battle_frame(bot, chat_id, message_id, c_name, o_name, c_team, o_team, p1_idx, p2_idx, logs, round_num, finished=True)
        
        battle.status = "COMPLETED"
        await db.commit()

async def render_battle_frame(bot: Bot, chat_id: int, message_id: int, c_name: str, o_name: str, c_team: list, o_team: list, p1_idx: int, p2_idx: int, logs: list, round_num: int, finished: bool = False):
    format_type = len(c_team)
    
    c_active = c_team[min(p1_idx, format_type - 1)]
    o_active = o_team[min(p2_idx, format_type - 1)]
    
    c_hp_bar = get_hp_bar_battle(c_active["hp"], c_active["max_hp"])
    o_hp_bar = get_hp_bar_battle(o_active["hp"], o_active["max_hp"])
    
    c_active_status = "💀 Fainted" if p1_idx >= format_type else f"{c_active['name']}"
    o_active_status = "💀 Fainted" if p2_idx >= format_type else f"{o_active['name']}"
    
    c_dots = "".join(["🔴" if i < p1_idx else "🟢" for i in range(format_type)])
    o_dots = "".join(["🔴" if i < p2_idx else "🟢" for i in range(format_type)])
    
    scroll_logs = logs[-4:]
    log_text = "\n".join(scroll_logs)
    
    title = "⚔️ **PVP BATTLE IN PROGRESS** ⚔️" if not finished else "🏁 **PVP BATTLE FINISHED** 🏁"
    
    text = (
        f"{title}\n"
        f"───────────────\n"
        f"👤 **{c_name}** {c_dots}\n"
        f"⭐ Active: **{c_active_status}**\n"
        f"HP: {c_hp_bar}\n"
        f"───────────────\n"
        f"👤 **{o_name}** {o_dots}\n"
        f"⭐ Active: **{o_active_status}**\n"
        f"HP: {o_hp_bar}\n"
        f"───────────────\n"
        f"📜 **Battle Logs (Turn {round_num})**:\n"
        f"{log_text}\n"
        f"───────────────"
    )
    
    try:
        await bot.edit_message_text(
            text=text,
            chat_id=chat_id,
            message_id=message_id,
            parse_mode="Markdown"
        )
    except Exception:
        pass
