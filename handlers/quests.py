import html
from datetime import datetime
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, TrainerQuest
from utils.trainer_level import add_trainer_xp, log_transaction

router = Router()

QUEST_DEFINITIONS = {
    "daily_catch": {
        "title": "🎣 Catch 3 Wild Pokémon",
        "target": 3,
        "period": "daily",
        "reward_coins": 500,
        "reward_xp": 200
    },
    "daily_chat": {
        "title": "💬 Send 20 Group Messages",
        "target": 20,
        "period": "daily",
        "reward_coins": 300,
        "reward_xp": 100
    },
    "daily_game": {
        "title": "🎮 Play/Win 1 Game or PvP Duel",
        "target": 1,
        "period": "daily",
        "reward_coins": 750,
        "reward_xp": 300
    },
    "weekly_catch": {
        "title": "🏆 Catch 20 Wild Pokémon",
        "target": 20,
        "period": "weekly",
        "reward_coins": 3000,
        "reward_xp": 1000
    },
    "weekly_auction": {
        "title": "🏷️ Place 2 Auction Bids",
        "target": 2,
        "period": "weekly",
        "reward_coins": 2000,
        "reward_xp": 500
    }
}

def check_and_reset_quest(quest: TrainerQuest) -> bool:
    """Resets daily or weekly quest if it was created/last reset before the current period."""
    if not quest or not quest.created_at:
        return False
    now = datetime.utcnow()
    need_reset = False
    
    if quest.period == "daily":
        if quest.created_at.date() < now.date():
            need_reset = True
    elif quest.period == "weekly":
        if quest.created_at.isocalendar()[:2] < now.isocalendar()[:2]:
            need_reset = True
            
    if need_reset:
        quest.progress = 0
        quest.is_claimed = False
        quest.created_at = now
        return True
    return False

async def update_quest_progress(user_id: int, quest_key: str, increment: int, db: AsyncSession):
    """Increments progress for a specific quest key for user_id."""
    if quest_key not in QUEST_DEFINITIONS:
        return
    q_def = QUEST_DEFINITIONS[quest_key]
    
    stmt = select(TrainerQuest).where(
        TrainerQuest.user_id == user_id,
        TrainerQuest.quest_key == quest_key
    )
    res = await db.execute(stmt)
    quest = res.scalar_one_or_none()
    
    if not quest:
        quest = TrainerQuest(
            user_id=user_id,
            quest_key=quest_key,
            progress=increment,
            target=q_def["target"],
            period=q_def["period"],
            is_claimed=False,
            created_at=datetime.utcnow()
        )
        db.add(quest)
    else:
        check_and_reset_quest(quest)
        if not quest.is_claimed and quest.progress < quest.target:
            quest.progress = min(quest.target, quest.progress + increment)
            
    await db.commit()

async def build_quests_payload(user_id: int, db: AsyncSession):
    """Builds the Style 2 Cyber Gold Card payload for user's quests."""
    # Ensure default quest records exist for user
    for qk, qdef in QUEST_DEFINITIONS.items():
        stmt = select(TrainerQuest).where(
            TrainerQuest.user_id == user_id,
            TrainerQuest.quest_key == qk
        )
        res = await db.execute(stmt)
        q_item = res.scalar_one_or_none()
        if not q_item:
            db.add(TrainerQuest(
                user_id=user_id,
                quest_key=qk,
                progress=0,
                target=qdef["target"],
                period=qdef["period"],
                is_claimed=False,
                created_at=datetime.utcnow()
            ))
        else:
            check_and_reset_quest(q_item)
    await db.commit()

    stmt = select(TrainerQuest).where(TrainerQuest.user_id == user_id)
    res = await db.execute(stmt)
    user_quests = {q.quest_key: q for q in res.scalars().all()}

    builder = InlineKeyboardBuilder()
    lines = []

    for qk, qdef in QUEST_DEFINITIONS.items():
        q_rec = user_quests.get(qk)
        prog = q_rec.progress if q_rec else 0
        target = qdef["target"]
        claimed = q_rec.is_claimed if q_rec else False

        pct = min(100, int((prog / target) * 100)) if target > 0 else 0
        filled = pct // 10
        bar = "█" * filled + "░" * (10 - filled)

        status_str = "✅ Claimed" if claimed else ("🎁 Ready to Claim!" if prog >= target else f"<code>{prog}/{target}</code>")
        lines.append(f"✦ <b>{qdef['title']}</b>")
        lines.append(f"   [{bar}] {pct}% • {status_str}")
        lines.append(f"   <i>Reward:</i> 💰 {qdef['reward_coins']:,} coins | ⚡ {qdef['reward_xp']} XP\n")

        if not claimed and prog >= target:
            builder.row(InlineKeyboardButton(
                text=f"🎁 Claim {qdef['title'][:18]}...",
                callback_data=f"claim_quest_{qk}"
            ))

    lines_body = "\n".join(lines)
    text = (
        f"⚡ <b>TRAINER QUEST CENTER</b> ⚡\n"
        f"◈ ────────────────── ◈\n"
        f"📜 <b>Daily & Weekly Bounties</b>\n\n"
        f"{lines_body}\n"
        f"◈ ────────────────── ◈\n"
        f"💡 Complete bounties to earn Coins & Trainer EXP!"
    )

    builder.row(InlineKeyboardButton(text="🔄 Refresh Quests", callback_data="refresh_quests"))
    return text, builder.as_markup()

@router.message(Command("quests", "bounties", "quest"))
async def cmd_quests(message: Message, db: AsyncSession):
    text, kb = await build_quests_payload(message.from_user.id, db)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")

@router.callback_query(F.data == "refresh_quests")
async def cb_refresh_quests(callback: CallbackQuery, db: AsyncSession):
    text, kb = await build_quests_payload(callback.from_user.id, db)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("claim_quest_"))
async def cb_claim_quest(callback: CallbackQuery, db: AsyncSession):
    quest_key = callback.data.replace("claim_quest_", "")
    user_id = callback.from_user.id

    if quest_key not in QUEST_DEFINITIONS:
        await callback.answer("⚠️ Unknown quest.", show_alert=True)
        return

    qdef = QUEST_DEFINITIONS[quest_key]
    stmt = select(TrainerQuest).where(
        TrainerQuest.user_id == user_id,
        TrainerQuest.quest_key == quest_key
    )
    res = await db.execute(stmt)
    quest = res.scalar_one_or_none()

    if not quest or quest.progress < quest.target:
        await callback.answer("⚠️ Quest requirement not completed yet!", show_alert=True)
        return

    if quest.is_claimed:
        await callback.answer("⚠️ Reward already claimed!", show_alert=True)
        return

    # Mark claimed
    quest.is_claimed = True
    
    # Award coins & XP
    u_stmt = select(User).where(User.id == user_id)
    u_res = await db.execute(u_stmt)
    user = u_res.scalar_one_or_none()

    if user:
        user.coins += qdef["reward_coins"]
        await log_transaction(
            user_id=user_id,
            amount=qdef["reward_coins"],
            category="QUEST_REWARD",
            description=f"Completed Quest: {qdef['title']}",
            db=db
        )
        await add_trainer_xp(user, qdef["reward_xp"], db, callback.bot, callback.message.chat.id)

    await db.commit()
    await callback.answer(f"🎉 Claimed +{qdef['reward_coins']:,} coins and +{qdef['reward_xp']} XP!", show_alert=True)

    text, kb = await build_quests_payload(user_id, db)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
