import json
import random
import os
from datetime import datetime
from typing import Dict, Any, Optional
import config

# Rarity weight settings
RARITY_WEIGHTS = {
    "Common": 550,      # 55.0%
    "Uncommon": 250,    # 25.0%
    "Rare": 120,        # 12.0%
    "Epic": 60,         # 6.0%
    "Legendary": 18,    # 1.8%
    "Mythical": 2       # 0.2%
}

WEATHER_TYPES = ["Clear", "Sunny", "Rainy", "Thunderstorm", "Foggy"]

# Weather boost dictionary: boosts types by weather
WEATHER_BOOSTS = {
    "Sunny": ["Fire", "Grass", "Ground"],
    "Rainy": ["Water", "Bug"],
    "Thunderstorm": ["Electric", "Steel"],
    "Foggy": ["Ghost", "Dark", "Psychic"],
    "Clear": ["Normal", "Flying", "Fighting"]
}

class SpawnSystem:
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

    def get_current_weather(self) -> str:
        """Determines the current weather based on the current hour (deterministic but rotating)."""
        hour = datetime.now().hour
        # Seed random with the day and hour to keep weather consistent for everyone during that hour
        random_gen = random.Random(datetime.now().strftime("%Y-%m-%d") + f"-{hour}")
        return random_gen.choice(WEATHER_TYPES)

    def generate_encounter(self) -> Dict[str, Any]:
        """Generates a wild monster encounter, taking rarity weights and weather boosts into account."""
        if not self.monsters_db:
            raise ValueError("Monster database is empty.")

        # Determine weather
        weather = self.get_current_weather()
        boosted_types = WEATHER_BOOSTS.get(weather, [])

        # Build list of monsters grouped by rarity
        rarity_groups = {}
        for m_id, data in self.monsters_db.items():
            tier = data.get("tier", "Common")
            rarity_groups.setdefault(tier, []).append(m_id)

        # Select a tier using weights
        tiers = list(RARITY_WEIGHTS.keys())
        weights = [RARITY_WEIGHTS[t] for t in tiers]
        
        # Adjust weights slightly if weather boosts any monster in that tier
        adjusted_weights = []
        for i, tier in enumerate(tiers):
            weight = weights[i]
            # If a tier contains weather boosted monsters, slightly boost its chance
            contains_boosted = False
            for m_id in rarity_groups.get(tier, []):
                m_types = self.monsters_db[m_id].get("types", [])
                if any(t in boosted_types for t in m_types):
                    contains_boosted = True
                    break
            
            if contains_boosted:
                weight = int(weight * 1.2)  # 20% weight boost
            adjusted_weights.append(weight)

        selected_tier = random.choices(tiers, weights=adjusted_weights, k=1)[0]
        
        # Fallback in case a tier has no monsters
        while selected_tier not in rarity_groups or not rarity_groups[selected_tier]:
            selected_tier = random.choice(list(rarity_groups.keys()))

        # Select monster from the chosen tier
        monster_id = random.choice(rarity_groups[selected_tier])
        monster_data = self.monsters_db[monster_id]

        # Determine level (base: 1-20, weather boosted: +3 to levels)
        is_boosted = any(t in boosted_types for t in monster_data.get("types", []))
        min_lvl = 3 if is_boosted else 1
        max_lvl = 23 if is_boosted else 20
        level = random.randint(min_lvl, max_lvl)

        # Determine IVs (0 to 31). Weather boosted guarantees at least 10 IV in stats
        hp_iv = random.randint(10 if is_boosted else 0, 31)
        atk_iv = random.randint(10 if is_boosted else 0, 31)
        def_iv = random.randint(10 if is_boosted else 0, 31)
        spd_iv = random.randint(10 if is_boosted else 0, 31)
        sp_atk_iv = random.randint(10 if is_boosted else 0, 31)
        sp_def_iv = random.randint(10 if is_boosted else 0, 31)

        # Roll for shiny (disabled)
        is_shiny = False

        # Calculate HP with formula: ((2 * BaseHP + HP_IV) * Level) // 100 + Level + 10
        base_hp = monster_data["base_stats"]["hp"]
        max_hp = ((2 * base_hp + hp_iv) * level) // 100 + level + 10

        return {
            "monster_id": monster_id,
            "name": monster_data["name"],
            "tier": selected_tier,
            "types": monster_data["types"],
            "level": level,
            "hp_iv": hp_iv,
            "atk_iv": atk_iv,
            "def_iv": def_iv,
            "spd_iv": spd_iv,
            "sp_atk_iv": sp_atk_iv,
            "sp_def_iv": sp_def_iv,
            "max_hp": max_hp,
            "is_shiny": is_shiny,
            "is_boosted": is_boosted,
            "weather": weather
        }

    @staticmethod
    def calculate_stats(base_stats: Dict[str, int], ivs: Dict[str, int], level: int) -> Dict[str, int]:
        """Calculates standard combat stats for a given level and IV profile."""
        stats = {}
        # HP: ((2 * BaseHP + HP_IV) * Level) // 100 + Level + 10
        stats["hp"] = ((2 * base_stats["hp"] + ivs.get("hp", 0)) * level) // 100 + level + 10
        
        # Other stats: ((2 * BaseStat + Stat_IV) * Level) // 100 + 5
        for stat in ["atk", "def", "spd", "sp_atk", "sp_def"]:
            stats[stat] = ((2 * base_stats[stat] + ivs.get(stat, 0)) * level) // 100 + 5
            
        return stats
