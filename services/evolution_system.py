import json
import os
from typing import Dict, Any, Tuple, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import config
from database.models import User, UserPokemon, Pokemon

class EvolutionSystem:
    def __init__(self):
        self.monsters_db: Dict[str, Any] = {}
        self.load_monsters()

    def load_monsters(self):
        monsters_file = os.path.join(config.DATA_DIR, "monsters.json")
        try:
            with open(monsters_file, "r") as f:
                self.monsters_db = json.load(f)
        except Exception as e:
            print(f"Error loading monsters.json: {e}")
            self.monsters_db = {}

    def get_monster_data(self, monster_id: str) -> Optional[Dict[str, Any]]:
        return self.monsters_db.get(monster_id)

    def can_evolve(self, user_monster: UserMonster, has_stone: bool = False) -> Tuple[bool, str]:
        """Checks if a user monster meets the requirements to evolve.
        Returns (bool_can_evolve, reason_string).
        """
        monster_data = self.get_monster_data(user_monster.monster_id)
        if not monster_data:
            return False, "Monster data not found in database."

        next_evo = monster_data.get("next_evolution")
        if not next_evo:
            return False, f"👑 {user_monster.name} is already at its final evolution!"

        evo_level = monster_data.get("evolution_level")
        evo_item = monster_data.get("evolution_item")

        # Case 1: Evolves by item
        if evo_item:
            if not has_stone:
                item_name = evo_item.replace("_", " ").title()
                return False, f"💎 {user_monster.name} requires a {item_name} to evolve. Use it via the bag/item menu!"
            return True, "Ready to evolve using stone!"

        # Case 2: Evolves by level
        if evo_level:
            if user_monster.level < evo_level:
                return False, f"📈 {user_monster.name} needs to reach Level {evo_level} to evolve (Current: Lvl {user_monster.level})."
            return True, "Ready to evolve!"

        return False, "Unknown evolution requirements."

    async def evolve_monster(self, db: AsyncSession, user_monster: UserMonster, stone_id: Optional[str] = None) -> Tuple[bool, str]:
        """Attempts to evolve the monster in the database. Consumes stone if required."""
        monster_data = self.get_monster_data(user_monster.monster_id)
        if not monster_data:
            return False, "Monster species not found."

        next_evo_id = monster_data.get("next_evolution")
        if not next_evo_id:
            return False, "Already fully evolved."

        next_monster_data = self.get_monster_data(next_evo_id)
        if not next_monster_data:
            return False, "Evolution destination data not found."

        evo_item = monster_data.get("evolution_item")
        
        # Check stone item if needed
        if evo_item:
            if stone_id != evo_item:
                return False, f"Incorrect item. This monster requires {evo_item.replace('_', ' ').title()}."

            # Query and decrement stone
            stmt = select(Inventory).where(
                Inventory.user_id == user_monster.user_id,
                Inventory.item_id == evo_item
            )
            result = await db.execute(stmt)
            inv_item = result.scalar_one_or_none()

            if not inv_item or inv_item.quantity <= 0:
                return False, "You do not own the required evolution stone."
            
            # Consume stone
            inv_item.quantity -= 1

        # Perform the evolution change
        old_name = user_monster.name
        old_species_name = monster_data.get("name")
        new_species_name = next_monster_data.get("name")

        # If name is default, change nickname to new species name. Otherwise keep the user's custom nickname.
        if old_name == old_species_name:
            user_monster.name = new_species_name
        
        # Update monster_id
        user_monster.monster_id = next_evo_id
        
        await db.commit()
        return True, f"✨ Congratulations! Your {old_name} has evolved into {user_monster.name}! ✨"
