import html
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import User, TransactionHistory

def get_xp_required_for_next_level(level: int) -> int:
    """Calculates EXP needed to advance from `level` to `level + 1`."""
    return max(100, level * 200)

def get_trainer_title(level: int) -> str:
    """Returns the official Trainer Title based on Level."""
    if level < 11:
        return "🥉 Novice Trainer"
    elif level < 26:
        return "🥈 Rookie Trainer"
    elif level < 51:
        return "🥇 Ace Trainer"
    elif level < 76:
        return "💎 Master Trainer"
    elif level < 100:
        return "🔮 Grandmaster"
    else:
        return "👑 Legendary Champion"

async def add_trainer_xp(user: User, xp_amount: int, db: AsyncSession, bot=None, chat_id: int = None) -> dict:
    """Adds EXP to user, handles level up(s), awards bonus coins, and optionally notifies chat."""
    if not user or xp_amount <= 0:
        return {"leveled_up": False, "levels_gained": 0}

    user.trainer_xp = (user.trainer_xp or 0) + xp_amount
    levels_gained = 0

    while True:
        req_xp = get_xp_required_for_next_level(user.trainer_level)
        if user.trainer_xp >= req_xp and user.trainer_level < 100:
            user.trainer_xp -= req_xp
            user.trainer_level += 1
            levels_gained += 1
            # Level-up bonus coins (level * 250 coins)
            bonus_coins = user.trainer_level * 250
            user.coins += bonus_coins
            
            # Log level-up transaction
            await log_transaction(
                user_id=user.id,
                amount=bonus_coins,
                category="LEVEL_UP",
                description=f"Reached Trainer Level {user.trainer_level} bonus",
                db=db
            )
        else:
            break

    if levels_gained > 0 and bot and chat_id:
        try:
            name = html.escape(user.nickname or user.username or f"Trainer {user.id}")
            title = get_trainer_title(user.trainer_level)
            bonus_coins = levels_gained * user.trainer_level * 250
            req_xp = get_xp_required_for_next_level(user.trainer_level)
            pct = min(100, int(((user.trainer_xp or 0) / req_xp) * 100)) if req_xp > 0 else 0
            filled = pct // 10
            xp_bar = "█" * filled + "░" * (10 - filled)

            text = (
                f"🎉 <b>TRAINER LEVEL UP!</b> 🎉\n"
                f"◈ ────────────────── ◈\n"
                f"👤 <b>{name}</b> leveled up to <b>Level {user.trainer_level}</b>!\n"
                f"🏷️ <b>Title:</b> {title}\n"
                f"⚡ <b>Next Level EXP:</b> [{xp_bar}] {pct}%\n"
                f"🎁 <b>Level Up Bonus:</b> 💰 <code>+{bonus_coins:,} coins</code>\n"
                f"◈ ────────────────── ◈\n"
                f"🔥 <i>Keep catching and battling to reach Level 100!</i>"
            )
            await bot.send_message(chat_id, text, parse_mode="HTML")
        except Exception as e:
            print(f"Error sending level up notification: {e}")

    return {
        "leveled_up": levels_gained > 0,
        "levels_gained": levels_gained,
        "new_level": user.trainer_level
    }

async def log_transaction(user_id: int, amount: int, category: str, description: str, db: AsyncSession):
    """Records a financial/coin transaction into transaction_history."""
    try:
        tx = TransactionHistory(
            user_id=user_id,
            amount=amount,
            category=category,
            description=description[:250]
        )
        db.add(tx)
    except Exception as e:
        print(f"Error logging transaction: {e}")
