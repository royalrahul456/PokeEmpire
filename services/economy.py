import os
import random
import json
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import config
from database.models import User, Inventory

class EconomySystem:
    def __init__(self):
        self.items_db: Dict[str, Any] = {}
        self.load_items()

    def load_items(self):
        items_file = os.path.join(config.DATA_DIR, "items.json")
        try:
            with open(items_file, "r") as f:
                self.items_db = json.load(f)
        except Exception as e:
            print(f"Error loading items.json: {e}")
            self.items_db = {}

    def get_item_data(self, item_id: str) -> Optional[Dict[str, Any]]:
        return self.items_db.get(item_id)

    @staticmethod
    def xp_to_next_level(level: int) -> int:
        """Determines the XP threshold needed to reach the next trainer level."""
        return level * 150

    @classmethod
    def check_trainer_level_up(cls, user: User) -> Tuple[bool, int]:
        """Checks if the user has accumulated enough XP to level up.
        Repeats check in case they gain multiple levels at once.
        """
        leveled_up = False
        gem_reward = 0
        while user.xp >= cls.xp_to_next_level(user.level):
            user.xp -= cls.xp_to_next_level(user.level)
            user.level += 1
            leveled_up = True
            # Level-up bonus gems: 2 * new_level
            gem_reward += user.level * 2
            
        if leveled_up:
            user.gems += gem_reward
            
        return leveled_up, gem_reward

    async def claim_daily(self, db: AsyncSession, user: User) -> Tuple[bool, str]:
        """Processes the daily reward claim for a user, calculating streaks and bonuses."""
        now = datetime.now()
        
        # Check cooldown
        if user.daily_cooldown and user.daily_cooldown > now:
            time_left = user.daily_cooldown - now
            hours, remainder = divmod(time_left.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            return False, f"⏳ You have already claimed your daily reward! Try again in {hours}h {minutes}m."

        # Check login streak continuity (within 48 hours since last_active/claim)
        # If last daily claim is more than 48 hours ago, reset streak to 0
        if user.daily_cooldown:
            last_claim_allowed_window = user.daily_cooldown + timedelta(days=1)  # 48 hrs since last active claim date
            if now > last_claim_allowed_window:
                user.login_streak = 0

        # Increment streak (capped at 7)
        user.login_streak = min(user.login_streak + 1, 7)
        
        # Calculate rewards
        coin_reward = config.DAILY_REWARD_COINS + (50 * user.login_streak)
        gem_reward = config.DAILY_REWARD_GEMS + (1 * user.login_streak)

        # Grant rewards
        user.coins += coin_reward
        user.gems += gem_reward
        user.daily_cooldown = now + timedelta(days=1)
        
        await db.commit()

        streak_icons = "🔥" * user.login_streak
        return True, (
            f"📅 **Daily Reward Claimed!** {streak_icons}\n"
            f"• Streak: **Day {user.login_streak}/7**\n"
            f"• Reward: 🪙 **{coin_reward} Coins** | 💎 **{gem_reward} Gems**"
        )

    async def execute_work(self, db: AsyncSession, user: User) -> Tuple[bool, str]:
        """Allows users to earn coins and XP via random job activities on a cooldown."""
        now = datetime.now()
        
        # Check work cooldown
        if user.work_cooldown and user.work_cooldown > now:
            time_left = user.work_cooldown - now
            minutes, seconds = divmod(time_left.seconds, 60)
            return False, f"⏳ You are exhausted from work! Please rest for another {minutes}m {seconds}s."

        # Work activities
        jobs = [
            ("helped Nurse Joy at the Pokémon Center", 70, 140, 10, 20),
            ("assisted Professor Oak in cleaning the lab", 80, 150, 12, 22),
            ("patrolled the city to clear out wild Rattata infestations", 90, 160, 15, 25),
            ("mined in Mt. Moon searching for Moon Stones", 60, 180, 8, 18),
            ("guided trainers through the Viridian Forest", 75, 145, 11, 21)
        ]
        
        job_desc, min_coins, max_coins, min_xp, max_xp = random.choice(jobs)
        coins_earned = random.randint(min_coins, max_coins)
        xp_earned = random.randint(min_xp, max_xp)

        # Apply rewards
        user.coins += coins_earned
        user.xp += xp_earned
        user.work_cooldown = now + timedelta(seconds=config.WORK_COOLDOWN)

        # Check level up
        leveled_up, gems_awarded = self.check_trainer_level_up(user)
        
        await db.commit()

        msg = f"💼 You **{job_desc}**!\n• Earned: 🪙 **{coins_earned} Coins** and 📈 **{xp_earned} XP**."
        if leveled_up:
            msg += f"\n\n🎉 **LEVEL UP!** You reached Trainer Level **{user.level}**! rewarded 💎 **{gems_awarded} Gems**."
            
        return True, msg

    async def buy_item(self, db: AsyncSession, user: User, item_id: str, quantity: int) -> Tuple[bool, str]:
        """Processes item purchases from the shop, charging user and updating inventory."""
        if quantity <= 0:
            return False, "⚠️ Invalid quantity requested."

        item_data = self.get_item_data(item_id)
        if not item_data:
            return False, "⚠️ Item species not found in database."

        cost = item_data["buy_price"] * quantity
        if user.coins < cost:
            return False, f"❌ Insufficient funds! You need 🪙 **{cost} Coins** but only have 🪙 **{user.coins}**."

        # Charge user
        user.coins -= cost

        # Add item to inventory
        stmt = select(Inventory).where(
            Inventory.user_id == user.id,
            Inventory.item_id == item_id
        )
        result = await db.execute(stmt)
        inv_item = result.scalar_one_or_none()

        if inv_item:
            inv_item.quantity += quantity
        else:
            new_item = Inventory(user_id=user.id, item_id=item_id, quantity=quantity)
            db.add(new_item)

        await db.commit()
        return True, f"🛍️ Successfully purchased **{quantity}x {item_data['name']}** for 🪙 **{cost} Coins**!"
