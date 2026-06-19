import json
import random
from typing import Optional
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import config
from database.models import User, UserMonster, Battle
from keyboards.inline import get_battle_keyboard, get_duel_invite_keyboard, get_main_menu_keyboard
from services.battle_engine import BattleEngine
from services.quest_system import QuestSystem
from services.spawn_system import SpawnSystem
from utils.formatters import get_hp_bar, format_card_title

router = Router()
spawn_system = SpawnSystem()
quest_system = QuestSystem()

async def get_healthy_monster(db: AsyncSession, user_id: int) -> Optional[UserMonster]:
    """Helper to query the first healthy monster in a user's active squad."""
    stmt = select(UserMonster).where(
        UserMonster.user_id == user_id,
        UserMonster.is_in_team == True
    ).order_by(UserMonster.team_slot)
    res = await db.execute(stmt)
    squad = res.scalars().all()
    
    for mon in squad:
        if mon.current_hp > 0:
            return mon
    return None

async def reward_victory_pve(db: AsyncSession, user: User, player_mon: UserMonster, enemy_mon_level: int) -> str:
    """Grants XP and Coins for a PvE win, checking for monster level ups."""
    coins_reward = random.randint(50, 120)
    user.coins += coins_reward
    
    # Calculate monster XP reward
    xp_reward = int(enemy_mon_level * 15)
    player_mon.xp += xp_reward
    
    # Level up checks: threshold = level * 60
    level_up = False
    old_lvl = player_mon.level
    while player_mon.xp >= (player_mon.level * 60):
        player_mon.xp -= (player_mon.level * 60)
        player_mon.level += 1
        level_up = True

    msg = f"🏆 **Victory!** 🏆\n\n"
    msg += f"• You earned: 🪙 **{coins_reward} Coins**\n"
    msg += f"• **{player_mon.name}** gained: 📈 **{xp_reward} XP**\n"
    
    if level_up:
        msg += f"🎉 **LEVEL UP!** {player_mon.name} reached Level **{player_mon.level}**! (HP fully restored)\n"
        # Recover HP to new max HP
        monster_spec = spawn_system.monsters_db.get(player_mon.monster_id)
        if monster_spec:
            base_hp = monster_spec["base_stats"]["hp"]
            max_hp = ((2 * base_hp + player_mon.hp_iv) * player_mon.level) // 100 + player_mon.level + 10
            player_mon.current_hp = max_hp
            
            # Check if monster can evolve by level
            next_evo = monster_spec.get("next_evolution")
            evo_level = monster_spec.get("evolution_level")
            if next_evo and evo_level and player_mon.level >= evo_level:
                msg += f"✨ **{player_mon.name}** is ready to evolve! Visit **My Bag** -> **Stones/Use Items** to evolve them!\n"

    # Track Quest Battle Win
    completed_quests = await quest_system.track_progress(db, user.id, "battle_win")
    if completed_quests:
        msg += "\n" + "\n".join([f"🎉 **Quest Completed!** _{name}_" for name in completed_quests])

    return msg

@router.message(Command("battlebot"))
async def cmd_battle_bot(message: Message, db: AsyncSession):
    user_id = message.from_user.id
    
    # Check registration
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        await message.answer("⚠️ You must register first with /start")
        return

    # Check healthy active monster
    player_mon = await get_healthy_monster(db, user_id)
    if not player_mon:
        await message.answer("⚠️ You have no healthy monsters in your active team! Heal them or set team in /bag first.")
        return

    # Generate Bot opponent monster
    # Levels will scale similarly to player's monster
    bot_level = max(1, player_mon.level + random.randint(-2, 2))
    
    # Pick a random monster species
    bot_species_id = random.choice(list(spawn_system.monsters_db.keys()))
    bot_spec = spawn_system.monsters_db[bot_species_id]
    
    bot_hp_iv = random.randint(5, 25)
    bot_atk_iv = random.randint(5, 25)
    bot_def_iv = random.randint(5, 25)
    bot_spd_iv = random.randint(5, 25)
    bot_sp_atk_iv = random.randint(5, 25)
    bot_sp_def_iv = random.randint(5, 25)

    bot_base_hp = bot_spec["base_stats"]["hp"]
    bot_max_hp = ((2 * bot_base_hp + bot_hp_iv) * bot_level) // 100 + bot_level + 10

    # Load stats for player's monster
    p_spec = spawn_system.monsters_db[player_mon.monster_id]
    p_base_stats = p_spec["base_stats"]
    p_ivs = {"hp": player_mon.hp_iv, "atk": player_mon.atk_iv, "def": player_mon.def_iv, "spd": player_mon.spd_iv, "sp_atk": player_mon.sp_atk_iv, "sp_def": player_mon.sp_def_iv}
    p_stats = SpawnSystem.calculate_stats(p_base_stats, p_ivs, player_mon.level)
    
    # Load stats for bot monster
    bot_base_stats = bot_spec["base_stats"]
    bot_ivs = {"hp": bot_hp_iv, "atk": bot_atk_iv, "def": bot_def_iv, "spd": bot_spd_iv, "sp_atk": bot_sp_atk_iv, "sp_def": bot_sp_def_iv}
    bot_stats = SpawnSystem.calculate_stats(bot_base_stats, bot_ivs, bot_level)

    # Initialize battle state structures
    p1_state = {
        "user_id": user_id,
        "name": player_mon.name,
        "monster_db_id": player_mon.id,
        "types": p_spec["types"],
        "level": player_mon.level,
        "current_hp": player_mon.current_hp,
        "max_hp": p_stats["hp"],
        "atk": p_stats["atk"],
        "def": p_stats["def"],
        "spd": p_stats["spd"],
        "sp_atk": p_stats["sp_atk"],
        "sp_def": p_stats["sp_def"],
        "status": None,
        "is_shiny": player_mon.is_shiny,
        "is_guarding": False,
        "atk_mult": 1.0,
        "def_mult": 1.0,
        "sp_atk_mult": 1.0,
        "sp_def_mult": 1.0
    }

    p2_state = {
        "user_id": 0,  # 0 indicates Bot
        "name": f"Wild {bot_spec['name']}",
        "monster_db_id": None,
        "types": bot_spec["types"],
        "level": bot_level,
        "current_hp": bot_max_hp,
        "max_hp": bot_max_hp,
        "atk": bot_stats["atk"],
        "def": bot_stats["def"],
        "spd": bot_stats["spd"],
        "sp_atk": bot_stats["sp_atk"],
        "sp_def": bot_stats["sp_def"],
        "status": None,
        "is_shiny": False,
        "is_guarding": False,
        "atk_mult": 1.0,
        "def_mult": 1.0,
        "sp_atk_mult": 1.0,
        "sp_def_mult": 1.0
    }

    # Determine initiative turn
    p_speed = p1_state["spd"]
    b_speed = p2_state["spd"]
    # 50% speed reduction if paralyzed
    if p1_state["status"] == "PARALYZED": p_speed *= 0.5
    if p2_state["status"] == "PARALYZED": b_speed *= 0.5

    active_turn_user_id = user_id if p_speed >= b_speed else 0

    battle_data = {
        "p1": p1_state,
        "p2": p2_state,
        "active_id": active_turn_user_id,
        "logs": ["⚔️ Battle Started! Choose your action:"]
    }

    # If Bot is faster, it attacks first immediately
    if active_turn_user_id == 0:
        bot_move = random.choice(["Strike", "Special", "Guard", "Debuff"])
        bot_log = BattleEngine.execute_move(bot_move, battle_data["p2"], battle_data["p1"])
        battle_data["logs"].append(bot_log)
        
        # Apply end of round status if any
        status_log = BattleEngine.apply_end_of_round_status(battle_data["p1"])
        if status_log:
            battle_data["logs"].append(status_log)
            
        # Switch turn back to player
        battle_data["active_id"] = user_id

    # Create Battle record in Database
    new_battle = Battle(
        battle_type="PvE",
        player1_id=user_id,
        player2_id=0,
        battle_state=json.dumps(battle_data),
        is_finished=False
    )
    db.add(new_battle)
    await db.commit()

    # Form text and display
    hp_bar_p1 = get_hp_bar(battle_data["p1"]["current_hp"], battle_data["p1"]["max_hp"])
    hp_bar_p2 = get_hp_bar(battle_data["p2"]["current_hp"], battle_data["p2"]["max_hp"])
    
    text = (
        f"⚔️ **PvE Training Battle** ⚔️\n\n"
        f"🔴 **{battle_data['p1']['name']}** (Lvl {battle_data['p1']['level']})\n"
        f"{hp_bar_p1}\n\n"
        f"🔵 **{battle_data['p2']['name']}** (Lvl {battle_data['p2']['level']})\n"
        f"{hp_bar_p2}\n\n"
        f"**LOGS**:\n" + "\n".join(battle_data["logs"][-3:]) + "\n\n"
        f"Make your move:"
    )

    await message.answer(text, reply_markup=get_battle_keyboard(new_battle.id), parse_mode="Markdown")

@router.callback_query(F.data.startswith("bat_move_"))
async def callback_battle_move(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id
    parts = callback.data.split("_")
    battle_id = int(parts[2])
    move_choice = parts[3]

    # Query battle record
    stmt = select(Battle).where(Battle.id == battle_id)
    res = await db.execute(stmt)
    battle = res.scalar_one_or_none()

    if not battle or battle.is_finished:
        await callback.answer("⚠️ This battle has already concluded.", show_alert=True)
        return

    battle_data = json.loads(battle.battle_state)
    
    # Verify active player
    if battle_data["active_id"] != user_id:
        await callback.answer("⚠️ It's not your turn!", show_alert=True)
        return

    is_pve = (battle_data["p2"]["user_id"] == 0)
    logs = []

    # 1. PvE Battle Resolution
    if is_pve:
        # Player attacks Bot
        player_move_log = BattleEngine.execute_move(move_choice, battle_data["p1"], battle_data["p2"])
        logs.append(player_move_log)

        # Check if Bot fainted
        if battle_data["p2"]["current_hp"] <= 0:
            battle.is_finished = True
            battle.winner_id = user_id
            
            user_stmt = select(User).where(User.id == user_id)
            user_res = await db.execute(user_stmt)
            user_obj = user_res.scalar_one()
            
            mon_stmt = select(UserMonster).where(UserMonster.id == battle_data["p1"]["monster_db_id"])
            mon_res = await db.execute(mon_stmt)
            mon_obj = mon_res.scalar_one()
            
            mon_obj.current_hp = battle_data["p1"]["current_hp"]
            rewards_msg = await reward_victory_pve(db, user_obj, mon_obj, battle_data["p2"]["level"])
            await db.commit()
            
            hp_bar_p1 = get_hp_bar(battle_data["p1"]["current_hp"], battle_data["p1"]["max_hp"])
            text = (
                f"⚔️ **Battle Concluded!** ⚔️\n\n"
                f"🔴 **{battle_data['p1']['name']}**: {hp_bar_p1}\n"
                f"🔵 **{battle_data['p2']['name']}**: Fainted 💀\n\n"
                f"**LOGS**:\n" + "\n".join(logs) + "\n\n" + rewards_msg
            )
            await callback.message.edit_text(text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")
            await callback.answer("Victory!")
            return

        # Bot attacks Player
        bot_choices = ["Strike", "Special"]
        if battle_data["p1"]["status"] is None:
            bot_choices.append("Debuff")
        if not battle_data["p2"]["is_guarding"]:
            bot_choices.append("Guard")

        bot_move = random.choice(bot_choices)
        bot_move_log = BattleEngine.execute_move(bot_move, battle_data["p2"], battle_data["p1"])
        logs.append(bot_move_log)

        # Apply end of round status
        p1_status_log = BattleEngine.apply_end_of_round_status(battle_data["p1"])
        p2_status_log = BattleEngine.apply_end_of_round_status(battle_data["p2"])
        if p1_status_log: logs.append(p1_status_log)
        if p2_status_log: logs.append(p2_status_log)

        # Check if Player fainted
        if battle_data["p1"]["current_hp"] <= 0:
            battle.is_finished = True
            battle.winner_id = 0
            
            mon_stmt = select(UserMonster).where(UserMonster.id == battle_data["p1"]["monster_db_id"])
            mon_res = await db.execute(mon_stmt)
            mon_obj = mon_res.scalar_one()
            mon_obj.current_hp = 0
            await db.commit()
            
            text = (
                f"💀 **Defeat!** 💀\n\n"
                f"🔴 **{battle_data['p1']['name']}**: Fainted 💀\n"
                f"🔵 **{battle_data['p2']['name']}**: {get_hp_bar(battle_data['p2']['current_hp'], battle_data['p2']['max_hp'])}\n\n"
                f"**LOGS**:\n" + "\n".join(logs) + "\n\n"
                f"Your monster fainted! Heal it in **My Bag**."
            )
            await callback.message.edit_text(text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")
            await callback.answer("Defeat.")
            return

        # Update PvE State
        battle_data["logs"].extend(logs)
        battle.battle_state = json.dumps(battle_data)
        
        # Save HP
        mon_stmt = select(UserMonster).where(UserMonster.id == battle_data["p1"]["monster_db_id"])
        mon_res = await db.execute(mon_stmt)
        mon_obj = mon_res.scalar_one()
        mon_obj.current_hp = battle_data["p1"]["current_hp"]
        await db.commit()

        hp_bar_p1 = get_hp_bar(battle_data["p1"]["current_hp"], battle_data["p1"]["max_hp"])
        hp_bar_p2 = get_hp_bar(battle_data["p2"]["current_hp"], battle_data["p2"]["max_hp"])
        text = (
            f"⚔️ **PvE Training Battle** ⚔️\n\n"
            f"🔴 **{battle_data['p1']['name']}** (Lvl {battle_data['p1']['level']})\n"
            f"{hp_bar_p1}\n\n"
            f"🔵 **{battle_data['p2']['name']}** (Lvl {battle_data['p2']['level']})\n"
            f"{hp_bar_p2}\n\n"
            f"**LOGS**:\n" + "\n".join(battle_data["logs"][-3:]) + "\n\n"
            f"Make your move:"
        )
        await callback.message.edit_text(text, reply_markup=get_battle_keyboard(battle.id), parse_mode="Markdown")
        await callback.answer()

    # 2. PvP Battle Resolution
    else:
        # Determine who is attacker and defender
        if user_id == battle_data["p1"]["user_id"]:
            attacker = battle_data["p1"]
            defender = battle_data["p2"]
            next_active_id = battle_data["p2"]["user_id"]
        else:
            attacker = battle_data["p2"]
            defender = battle_data["p1"]
            next_active_id = battle_data["p1"]["user_id"]

        move_log = BattleEngine.execute_move(move_choice, attacker, defender)
        logs.append(move_log)

        # Apply end of turn status damage to the attacker
        status_log = BattleEngine.apply_end_of_round_status(attacker)
        if status_log:
            logs.append(status_log)

        # Check if defender fainted
        if defender["current_hp"] <= 0:
            battle.is_finished = True
            battle.winner_id = user_id

            # Save HPs to database
            p1_mon_stmt = select(UserMonster).where(UserMonster.id == battle_data["p1"]["monster_db_id"])
            p1_mon_res = await db.execute(p1_mon_stmt)
            p1_mon = p1_mon_res.scalar_one()
            p1_mon.current_hp = max(0, battle_data["p1"]["current_hp"])

            p2_mon_stmt = select(UserMonster).where(UserMonster.id == battle_data["p2"]["monster_db_id"])
            p2_mon_res = await db.execute(p2_mon_stmt)
            p2_mon = p2_mon_res.scalar_one()
            p2_mon.current_hp = max(0, battle_data["p2"]["current_hp"])

            # Reward winner and loser
            winner_user_stmt = select(User).where(User.id == user_id)
            winner_user_res = await db.execute(winner_user_stmt)
            winner_user = winner_user_res.scalar_one()
            winner_user.coins += 200

            loser_user_id = battle_data["p2"]["user_id"] if user_id == battle_data["p1"]["user_id"] else battle_data["p1"]["user_id"]
            loser_user_stmt = select(User).where(User.id == loser_user_id)
            loser_user_res = await db.execute(loser_user_stmt)
            loser_user = loser_user_res.scalar_one()
            loser_user.coins += 50

            # Award XP to winner's monster
            winner_mon = p1_mon if user_id == battle_data["p1"]["user_id"] else p2_mon
            xp_reward = int(defender["level"] * 20)
            winner_mon.xp += xp_reward
            
            # Level up check
            level_up = False
            while winner_mon.xp >= (winner_mon.level * 60):
                winner_mon.xp -= (winner_mon.level * 60)
                winner_mon.level += 1
                level_up = True
                # Recover HP
                mon_spec = spawn_system.monsters_db.get(winner_mon.monster_id)
                if mon_spec:
                    base_hp = mon_spec["base_stats"]["hp"]
                    winner_mon.current_hp = ((2 * base_hp + winner_mon.hp_iv) * winner_mon.level) // 100 + winner_mon.level + 10

            await db.commit()

            winner_name = attacker["name"]
            loser_name = defender["name"]
            
            win_msg = (
                f"🏆 **Duel Concluded! {winner_name} wins!** 🏆\n\n"
                f"• **{winner_name}** earned: 🪙 **200 Coins**\n"
                f"• **{loser_name}** earned: 🪙 **50 Coins**\n"
                f"• Winner's Monster gained: 📈 **{xp_reward} XP**\n"
            )
            if level_up:
                win_msg += f"🎉 **LEVEL UP!** Winner's monster reached Level **{winner_mon.level}**!\n"

            text = (
                f"⚔️ **PvP Duel Battle** ⚔️\n\n"
                f"🔴 **{battle_data['p1']['name']}**: {get_hp_bar(battle_data['p1']['current_hp'], battle_data['p1']['max_hp'])}\n"
                f"🔵 **{battle_data['p2']['name']}**: {get_hp_bar(battle_data['p2']['current_hp'], battle_data['p2']['max_hp'])}\n\n"
                f"**LOGS**:\n" + "\n".join(logs) + "\n\n" + win_msg
            )
            await callback.message.edit_text(text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")
            await callback.answer("PvP Duel Concluded!")
            return

        # Check if attacker fainted from self status damage
        if attacker["current_hp"] <= 0:
            battle.is_finished = True
            battle.winner_id = next_active_id

            # Save HPs to database
            p1_mon_stmt = select(UserMonster).where(UserMonster.id == battle_data["p1"]["monster_db_id"])
            p1_mon_res = await db.execute(p1_mon_stmt)
            p1_mon = p1_mon_res.scalar_one()
            p1_mon.current_hp = max(0, battle_data["p1"]["current_hp"])

            p2_mon_stmt = select(UserMonster).where(UserMonster.id == battle_data["p2"]["monster_db_id"])
            p2_mon_res = await db.execute(p2_mon_stmt)
            p2_mon = p2_mon_res.scalar_one()
            p2_mon.current_hp = max(0, battle_data["p2"]["current_hp"])

            await db.commit()

            text = (
                f"⚔️ **PvP Duel Battle** ⚔️\n\n"
                f"🔴 **{battle_data['p1']['name']}**: {get_hp_bar(battle_data['p1']['current_hp'], battle_data['p1']['max_hp'])}\n"
                f"🔵 **{battle_data['p2']['name']}**: {get_hp_bar(battle_data['p2']['current_hp'], battle_data['p2']['max_hp'])}\n\n"
                f"**LOGS**:\n" + "\n".join(logs) + "\n\n"
                f"💀 **{attacker['name']}** fainted from status damage! **{defender['name']}** wins the duel!"
            )
            await callback.message.edit_text(text, reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")
            await callback.answer("PvP Duel Concluded!")
            return

        # Update PvP state
        battle_data["logs"].extend(logs)
        battle_data["active_id"] = next_active_id
        battle.battle_state = json.dumps(battle_data)

        # Save current HP for both players
        p1_mon_stmt = select(UserMonster).where(UserMonster.id == battle_data["p1"]["monster_db_id"])
        p1_mon_res = await db.execute(p1_mon_stmt)
        p1_mon = p1_mon_res.scalar_one()
        p1_mon.current_hp = battle_data["p1"]["current_hp"]

        p2_mon_stmt = select(UserMonster).where(UserMonster.id == battle_data["p2"]["monster_db_id"])
        p2_mon_res = await db.execute(p2_mon_stmt)
        p2_mon = p2_mon_res.scalar_one()
        p2_mon.current_hp = battle_data["p2"]["current_hp"]

        await db.commit()

        # Redraw
        hp_bar_p1 = get_hp_bar(battle_data["p1"]["current_hp"], battle_data["p1"]["max_hp"])
        hp_bar_p2 = get_hp_bar(battle_data["p2"]["current_hp"], battle_data["p2"]["max_hp"])
        next_active_name = battle_data["p1"]["name"] if next_active_id == battle_data["p1"]["user_id"] else battle_data["p2"]["name"]

        text = (
            f"⚔️ **PVP DUEL BATTLE** ⚔️\n\n"
            f"🔴 **{battle_data['p1']['name']}** (Lvl {battle_data['p1']['level']}):\n{hp_bar_p1}\n\n"
            f"🔵 **{battle_data['p2']['name']}** (Lvl {battle_data['p2']['level']}):\n{hp_bar_p2}\n\n"
            f"**LOGS**:\n" + "\n".join(battle_data["logs"][-3:]) + "\n\n"
            f"👉 **It is {next_active_name}'s turn!** Choose your move:"
        )

        await callback.message.edit_text(text, reply_markup=get_battle_keyboard(battle.id), parse_mode="Markdown")
        await callback.answer()


@router.callback_query(F.data.startswith("bat_run_"))
async def callback_battle_flee(callback: CallbackQuery, db: AsyncSession):
    battle_id = int(callback.data.split("_")[2])
    stmt = select(Battle).where(Battle.id == battle_id)
    res = await db.execute(stmt)
    battle = res.scalar_one_or_none()

    if battle and not battle.is_finished:
        battle.is_finished = True
        battle_data = json.loads(battle.battle_state)
        
        # Persist HP as is
        mon_stmt = select(UserMonster).where(UserMonster.id == battle_data["p1"]["monster_db_id"])
        mon_res = await db.execute(mon_stmt)
        mon_obj = mon_res.scalar_one_or_none()
        if mon_obj:
            mon_obj.current_hp = battle_data["p1"]["current_hp"]
            
        await db.commit()

    await callback.message.edit_text("🏳️ You surrendered from the battle. You earned no rewards.", reply_markup=get_main_menu_keyboard(), parse_mode="Markdown")
    await callback.answer("Surrendered.")

# ==================== PVP CHALLENGE SYSTEM ====================
@router.message(Command("duel"))
async def cmd_duel(message: Message, db: AsyncSession):
    challenger_id = message.from_user.id
    
    # Need user mention or username to challenge
    if not message.text or len(message.text.split()) < 2:
        await message.answer("⚠️ Format: `/duel @username` (challenge another player in this group)")
        return

    target_mention = message.text.split()[1]
    if not target_mention.startswith("@"):
        await message.answer("⚠️ You must mention the target user starting with @ (e.g. `/duel @username`).")
        return
        
    target_username = target_mention.replace("@", "")

    # Look up target user in DB
    target_stmt = select(User).where(User.username == target_username)
    target_res = await db.execute(target_stmt)
    target_user = target_res.scalar_one_or_none()

    if not target_user:
        await message.answer(f"❌ Trainer {target_mention} is not registered in PokeEmpire. Ask them to run /start first!")
        return

    if target_user.id == challenger_id:
        await message.answer("❌ You cannot duel yourself!")
        return

    # Verify challenger has healthy monster
    challenger_mon = await get_healthy_monster(db, challenger_id)
    if not challenger_mon:
        await message.answer("⚠️ You don't have a healthy monster equipped! Heal them in /bag first.")
        return

    # Verify target has healthy monster
    target_mon = await get_healthy_monster(db, target_user.id)
    if not target_mon:
        await message.answer(f"⚠️ {target_user.nickname} does not have any healthy monsters equipped on their squad.")
        return

    text = (
        f"⚔️ **PVP DUEL CHALLENGE** ⚔️\n"
        f"Trainer **{message.from_user.first_name}** has challenged Trainer **{target_user.nickname}** to a duel!\n\n"
        f"Active Monster matchups:\n"
        f"🔴 **{challenger_mon.name}** (Lvl {challenger_mon.level}) vs 🔵 **{target_mon.name}** (Lvl {target_mon.level})\n\n"
        f"Accept the invitation below:"
    )

    await message.answer(text, reply_markup=get_duel_invite_keyboard(challenger_id), parse_mode="Markdown")

@router.callback_query(F.data.startswith("pvp_accept_"))
async def callback_pvp_accept(callback: CallbackQuery, db: AsyncSession):
    challenger_id = int(callback.data.split("_")[2])
    receiver_id = callback.from_user.id

    if challenger_id == receiver_id:
        await callback.answer("⚠️ You cannot accept your own challenge!", show_alert=True)
        return

    # Query player entities
    c_stmt = select(User).where(User.id == challenger_id)
    c_res = await db.execute(c_stmt)
    challenger = c_res.scalar_one_or_none()

    r_stmt = select(User).where(User.id == receiver_id)
    r_res = await db.execute(r_stmt)
    receiver = r_res.scalar_one_or_none()

    if not challenger or not receiver:
        await callback.answer("⚠️ Challenger session not found.", show_alert=True)
        return

    # Fetch active healthy monsters
    c_mon = await get_healthy_monster(db, challenger_id)
    r_mon = await get_healthy_monster(db, receiver_id)

    if not c_mon or not r_mon:
        await callback.answer("⚠️ Either you or the challenger does not have healthy monsters equipped.", show_alert=True)
        return

    # Load specs
    c_spec = spawn_system.monsters_db[c_mon.monster_id]
    r_spec = spawn_system.monsters_db[r_mon.monster_id]

    c_stats = SpawnSystem.calculate_stats(c_spec["base_stats"], {"hp": c_mon.hp_iv, "atk": c_mon.atk_iv, "def": c_mon.def_iv, "spd": c_mon.spd_iv, "sp_atk": c_mon.sp_atk_iv, "sp_def": c_mon.sp_def_iv}, c_mon.level)
    r_stats = SpawnSystem.calculate_stats(r_spec["base_stats"], {"hp": r_mon.hp_iv, "atk": r_mon.atk_iv, "def": r_mon.def_iv, "spd": r_mon.spd_iv, "sp_atk": r_mon.sp_atk_iv, "sp_def": r_mon.sp_def_iv}, r_mon.level)

    p1_state = {
        "user_id": challenger_id,
        "name": challenger.nickname,
        "monster_db_id": c_mon.id,
        "types": c_spec["types"],
        "level": c_mon.level,
        "current_hp": c_mon.current_hp,
        "max_hp": c_stats["hp"],
        "atk": c_stats["atk"],
        "def": c_stats["def"],
        "spd": c_stats["spd"],
        "sp_atk": c_stats["sp_atk"],
        "sp_def": c_stats["sp_def"],
        "status": None,
        "is_shiny": c_mon.is_shiny,
        "is_guarding": False,
        "atk_mult": 1.0,
        "def_mult": 1.0,
        "sp_atk_mult": 1.0,
        "sp_def_mult": 1.0
    }

    p2_state = {
        "user_id": receiver_id,
        "name": receiver.nickname,
        "monster_db_id": r_mon.id,
        "types": r_spec["types"],
        "level": r_mon.level,
        "current_hp": r_mon.current_hp,
        "max_hp": r_stats["hp"],
        "atk": r_stats["atk"],
        "def": r_stats["def"],
        "spd": r_stats["spd"],
        "sp_atk": r_stats["sp_atk"],
        "sp_def": r_stats["sp_def"],
        "status": None,
        "is_shiny": r_mon.is_shiny,
        "is_guarding": False,
        "atk_mult": 1.0,
        "def_mult": 1.0,
        "sp_atk_mult": 1.0,
        "sp_def_mult": 1.0
    }

    # Decide initiative speed
    c_spd = p1_state["spd"]
    r_spd = p2_state["spd"]
    active_turn_user_id = challenger_id if c_spd >= r_spd else receiver_id

    battle_data = {
        "p1": p1_state,
        "p2": p2_state,
        "active_id": active_turn_user_id,
        "logs": ["⚔️ PvP Duel Initiated! Let combat begin!"]
    }

    new_battle = Battle(
        battle_type="PvP",
        player1_id=challenger_id,
        player2_id=receiver_id,
        battle_state=json.dumps(battle_data),
        is_finished=False
    )
    db.add(new_battle)
    await db.commit()

    # Redraw PvP screen
    hp_bar_p1 = get_hp_bar(battle_data["p1"]["current_hp"], battle_data["p1"]["max_hp"])
    hp_bar_p2 = get_hp_bar(battle_data["p2"]["current_hp"], battle_data["p2"]["max_hp"])
    active_name = challenger.nickname if active_turn_user_id == challenger_id else receiver.nickname

    text = (
        f"⚔️ **PVP DUEL BATTLE** ⚔️\n\n"
        f"🔴 **{battle_data['p1']['name']}** ({battle_data['p1']['level']}):\n{hp_bar_p1}\n\n"
        f"🔵 **{battle_data['p2']['name']}** ({battle_data['p2']['level']}):\n{hp_bar_p2}\n\n"
        f"👉 **It is {active_name}'s turn!** Choose your move:"
    )

    await callback.message.edit_text(text, reply_markup=get_battle_keyboard(new_battle.id), parse_mode="Markdown")
    await callback.answer("Duel accepted!")
