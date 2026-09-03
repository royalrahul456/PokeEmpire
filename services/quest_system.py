import json
import os
from datetime import datetime, timedelta
from typing import Dict, Any, List, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
import config
from database.models import User, TrainerQuest

class QuestSystem:
    def __init__(self):
        self.quests_db: Dict[str, Any] = {}
        self.load_quests()

    def load_quests(self):
        quests_file = os.path.join(config.DATA_DIR, "quests.json")
        try:
            with open(quests_file, "r") as f:
                self.quests_db = json.load(f)
        except Exception as e:
            print(f"Error loading quests.json: {e}")
            self.quests_db = {}

    def get_quest_template(self, quest_id: str) -> Optional[Dict[str, Any]]:
        return self.quests_db.get(quest_id)

    async def initialize_user_quests(self, db: AsyncSession, user_id: int):
        """Checks and refreshes daily and weekly quests based on time. Seeds story quests."""
        now = datetime.now()
        start_of_today = datetime(now.year, now.month, now.day)
        start_of_week = start_of_today - timedelta(days=now.weekday())

        # 1. Fetch current active quests for user
        stmt = select(UserQuest).where(UserQuest.user_id == user_id)
        result = await db.execute(stmt)
        user_quests = result.scalars().all()

        existing_quest_ids = {q.quest_id for q in user_quests}

        # Categories of quests to populate
        dailies_in_db = [q for q in user_quests if self.quests_db.get(q.quest_id, {}).get("type") == "daily"]
        weeklies_in_db = [q for q in user_quests if self.quests_db.get(q.quest_id, {}).get("type") == "weekly"]

        # Check Daily expiration: If the last update of dailies was before today, delete and reload
        needs_new_dailies = False
        if dailies_in_db:
            latest_daily = max(q.updated_at for q in dailies_in_db)
            if latest_daily < start_of_today:
                needs_new_dailies = True
        else:
            needs_new_dailies = True

        if needs_new_dailies:
            # Delete old daily user quests
            for q in dailies_in_db:
                await db.delete(q)
            # Add new dailies from template
            for q_id, q_data in self.quests_db.items():
                if q_data["type"] == "daily":
                    new_q = UserQuest(user_id=user_id, quest_id=q_id, progress=0)
                    db.add(new_q)

        # Check Weekly expiration: If last update of weeklies was before this week, delete and reload
        needs_new_weeklies = False
        if weeklies_in_db:
            latest_weekly = max(q.updated_at for q in weeklies_in_db)
            if latest_weekly < start_of_week:
                needs_new_weeklies = True
        else:
            needs_new_weeklies = True

        if needs_new_weeklies:
            # Delete old weekly user quests
            for q in weeklies_in_db:
                await db.delete(q)
            # Add new weeklies from template
            for q_id, q_data in self.quests_db.items():
                if q_data["type"] == "weekly":
                    new_q = UserQuest(user_id=user_id, quest_id=q_id, progress=0)
                    db.add(new_q)

        # Seed Story quests if they are not already in user_quests (story quests don't repeat)
        for q_id, q_data in self.quests_db.items():
            if q_data["type"] == "story" and q_id not in existing_quest_ids:
                new_q = UserQuest(user_id=user_id, quest_id=q_id, progress=0)
                db.add(new_q)

        await db.commit()

    async def track_progress(self, db: AsyncSession, user_id: int, target_type: str, amount: int = 1) -> List[str]:
        """Increments quest progression for a specific activity type. Returns names of completed quests."""
        # Make sure user quests are initialized first
        await self.initialize_user_quests(db, user_id)

        stmt = select(UserQuest).where(
            UserQuest.user_id == user_id,
            UserQuest.is_completed == False
        )
        result = await db.execute(stmt)
        active_quests = result.scalars().all()

        completed_quest_names = []

        for u_q in active_quests:
            q_template = self.get_quest_template(u_q.quest_id)
            if not q_template:
                continue

            if q_template.get("target_type") == target_type:
                u_q.progress += amount
                u_q.updated_at = datetime.now()
                
                target_amt = q_template.get("target_amount", 1)
                if u_q.progress >= target_amt:
                    u_q.progress = target_amt
                    u_q.is_completed = True
                    completed_quest_names.append(q_template.get("name", "Unknown Quest"))

        if completed_quest_names:
            await db.commit()

        return completed_quest_names

    async def claim_quest_reward(self, db: AsyncSession, user: User, user_quest_id: int) -> Tuple[bool, str]:
        """Claims rewards for a completed quest, crediting items and coins/gems."""
        stmt = select(UserQuest).where(
            UserQuest.id == user_quest_id,
            UserQuest.user_id == user.id
        )
        result = await db.execute(stmt)
        u_q = result.scalar_one_or_none()

        if not u_q:
            return False, "⚠️ Quest not found."
        
        if not u_q.is_completed:
            return False, "⚠️ This quest is not completed yet!"
            
        if u_q.is_claimed:
            return False, "⚠️ You have already claimed this quest's rewards."

        q_template = self.get_quest_template(u_q.quest_id)
        if not q_template:
            return False, "⚠️ Quest template not found."

        rewards = q_template.get("rewards", {})
        coins_reward = rewards.get("coins", 0)
        gems_reward = rewards.get("gems", 0)
        items_reward = rewards.get("items", {})

        # Credit currencies
        user.coins += coins_reward
        user.gems += gems_reward

        # Credit items
        rewarded_items_desc = []
        for item_id, qty in items_reward.items():
            item_stmt = select(Inventory).where(
                Inventory.user_id == user.id,
                Inventory.item_id == item_id
            )
            item_res = await db.execute(item_stmt)
            inv_item = item_res.scalar_one_or_none()

            if inv_item:
                inv_item.quantity += qty
            else:
                new_item = Inventory(user_id=user.id, item_id=item_id, quantity=qty)
                db.add(new_item)
            
            # Formatted item name
            item_name = item_id.replace("_", " ").title()
            rewarded_items_desc.append(f"📦 **{qty}x {item_name}**")

        # Mark claimed
        u_q.is_claimed = True
        u_q.updated_at = datetime.now()
        await db.commit()

        # Build reward summary
        summary = f"🎉 **Quest Reward Claimed!**\n• Earned: 🪙 **{coins_reward} Coins** | 💎 **{gems_reward} Gems**"
        if rewarded_items_desc:
            summary += "\n• Items: " + ", ".join(rewarded_items_desc)

        return True, summary
