import random
import json
from typing import Dict, Any, List, Tuple

# Type Matchup Chart: Attacker -> Defending Type -> Multiplier
TYPE_CHART = {
    "Normal": {"Ghost": 0.0},
    "Fire": {"Grass": 2.0, "Bug": 2.0, "Fire": 0.5, "Water": 0.5, "Rock": 0.5, "Dragon": 0.5},
    "Water": {"Fire": 2.0, "Ground": 2.0, "Rock": 2.0, "Water": 0.5, "Grass": 0.5, "Dragon": 0.5},
    "Electric": {"Water": 2.0, "Flying": 2.0, "Electric": 0.5, "Grass": 0.5, "Ground": 0.0},
    "Grass": {"Water": 2.0, "Ground": 2.0, "Rock": 2.0, "Fire": 0.5, "Grass": 0.5, "Poison": 0.5, "Flying": 0.5, "Bug": 0.5, "Dragon": 0.5},
    "Poison": {"Grass": 2.0, "Poison": 0.5, "Ground": 0.5, "Rock": 0.5, "Ghost": 0.5, "Steel": 0.0},
    "Flying": {"Grass": 2.0, "Fighting": 2.0, "Bug": 2.0, "Electric": 0.5, "Rock": 0.5, "Steel": 0.5},
    "Psychic": {"Fighting": 2.0, "Poison": 2.0, "Psychic": 0.5, "Steel": 0.5, "Dark": 0.0},
    "Bug": {"Grass": 2.0, "Psychic": 2.0, "Dark": 2.0, "Fire": 0.5, "Fighting": 0.5, "Poison": 0.5, "Flying": 0.5, "Ghost": 0.5, "Steel": 0.5},
    "Ghost": {"Normal": 0.0, "Psychic": 2.0, "Ghost": 2.0, "Dark": 0.5}
}

class BattleEngine:
    @staticmethod
    def get_type_multiplier(attack_types: List[str], defend_types: List[str]) -> float:
        """Calculates elemental multiplier based on attacking and defending types."""
        multiplier = 1.0
        for a_type in attack_types:
            for d_type in defend_types:
                chart = TYPE_CHART.get(a_type, {})
                mult = chart.get(d_type, 1.0)
                multiplier *= mult
        return multiplier

    @classmethod
    def calculate_damage(
        cls,
        level: int,
        power: int,
        attacker_stat: int,
        defender_stat: int,
        attack_types: List[str],
        defend_types: List[str],
        is_special: bool = False,
        is_burned: bool = False
    ) -> Tuple[int, bool, float]:
        """Runs the standard Pokemon-inspired damage formula with crits, variance, and types."""
        # 1. Base Damage Formula
        # Damage = (((2 * Level / 5 + 2) * Stat_Attacker * Power / Stat_Defender) / 50) + 2
        base_dmg = (((2 * level / 5 + 2) * attacker_stat * power / max(defender_stat, 1)) / 50) + 2

        # 2. Burn Penalty (Halves physical attack damage)
        if is_burned and not is_special:
            base_dmg *= 0.5

        # 3. Critical Hit Roll (10% chance)
        is_crit = random.random() < 0.10
        crit_multiplier = 1.5 if is_crit else 1.0
        
        # 4. Type Matchups
        type_multiplier = cls.get_type_multiplier(attack_types, defend_types)
        
        # 5. Random Variance (85% to 115%)
        variance = random.uniform(0.85, 1.15)
        
        final_damage = int(base_dmg * crit_multiplier * type_multiplier * variance)
        return max(final_damage, 1), is_crit, type_multiplier

    @classmethod
    def execute_move(cls, move_name: str, attacker: Dict[str, Any], defender: Dict[str, Any]) -> str:
        """Executes a move choice, updates defender state, and returns a log sentence."""
        
        # Paralysis turn check: 25% chance to be fully paralyzed
        if attacker.get("status") == "PARALYZED" and random.random() < 0.25:
            return f"⚡ {attacker['name']} is paralyzed and cannot move!"

        log = ""
        # Read stats
        lvl = attacker["level"]
        types_atk = attacker["types"]
        types_def = defender["types"]

        # Base Stats modified by active buffs/debuffs
        atk = int(attacker["atk"] * attacker.get("atk_mult", 1.0))
        sp_atk = int(attacker["sp_atk"] * attacker.get("sp_atk_mult", 1.0))
        
        # Defender stats modified by active buffs/debuffs
        defense = int(defender["def"] * defender.get("def_mult", 1.0))
        sp_def = int(defender["sp_def"] * defender.get("sp_def_mult", 1.0))

        # Check Guard status: if defender is guarding, increase their defensive stat temporarily
        if defender.get("is_guarding", False):
            defense = int(defense * 1.5)
            sp_def = int(sp_def * 1.5)

        # Clear guard status for the attacker at the start of their turn
        attacker["is_guarding"] = False

        if move_name == "Strike":
            # Physical attack (Strike / Tackle)
            power = 45
            accuracy = 0.95
            
            if random.random() > accuracy:
                return f"💨 {attacker['name']}'s Strike missed!"
                
            damage, is_crit, multiplier = cls.calculate_damage(
                level=lvl,
                power=power,
                attacker_stat=atk,
                defender_stat=defense,
                attack_types=["Normal"],
                defend_types=types_def,
                is_special=False,
                is_burned=(attacker.get("status") == "BURNED")
            )
            
            defender["current_hp"] = max(0, defender["current_hp"] - damage)
            log += f"⚔️ {attacker['name']} used Strike dealing {damage} HP damage!"
            if is_crit:
                log += " **Critical Hit!**"
            if multiplier > 1.0:
                log += " It's super effective!"
            elif 0.0 < multiplier < 1.0:
                log += " It's not very effective..."
            elif multiplier == 0.0:
                log += " It had no effect."

        elif move_name == "Special":
            # Elemental Blast (using primary monster element)
            power = 65
            accuracy = 0.90
            
            if random.random() > accuracy:
                return f"💨 {attacker['name']}'s Elemental Blast missed!"

            damage, is_crit, multiplier = cls.calculate_damage(
                level=lvl,
                power=power,
                attacker_stat=sp_atk,
                defender_stat=sp_def,
                attack_types=types_atk,
                defend_types=types_def,
                is_special=True
            )
            
            defender["current_hp"] = max(0, defender["current_hp"] - damage)
            log += f"🔮 {attacker['name']} unleashed Elemental Blast using {types_atk[0]} type, dealing {damage} HP damage!"
            if is_crit:
                log += " **Critical Hit!**"
            if multiplier > 1.0:
                log += " It's super effective!"
            elif 0.0 < multiplier < 1.0:
                log += " It's not very effective..."
            elif multiplier == 0.0:
                log += " It had no effect."

        elif move_name == "Guard":
            # Defensive guard
            attacker["is_guarding"] = True
            log += f"🛡️ {attacker['name']} took a defensive stance (Guard active, Def/SpDef +50% next turn)!"

        elif move_name == "Debuff":
            # Tries to inflict status based on types
            accuracy = 0.75
            if random.random() > accuracy:
                return f"💨 {attacker['name']} tried to place a status condition but missed!"

            if defender.get("status") is not None:
                return f"⚠️ {defender['name']} already has a status condition: {defender['status']}!"

            # Pick a status depending on attacker types
            primary_type = types_atk[0]
            inflicted = None
            if primary_type in ["Fire", "Normal"]:
                inflicted = "BURNED"
                defender["status"] = "BURNED"
                log += f"🔥 {attacker['name']} set {defender['name']} on fire! Inflicted BURNED."
            elif primary_type in ["Water", "Grass", "Poison", "Bug"]:
                inflicted = "POISONED"
                defender["status"] = "POISONED"
                log += f"🧪 {attacker['name']} poisoned {defender['name']}! Inflicted POISONED."
            elif primary_type in ["Electric", "Psychic", "Ghost"]:
                inflicted = "PARALYZED"
                defender["status"] = "PARALYZED"
                log += f"⚡ {attacker['name']} electrocuted {defender['name']}! Inflicted PARALYZED."

        return log

    @classmethod
    def apply_end_of_round_status(cls, entity: Dict[str, Any]) -> str:
        """Applies damage over time for Burned/Poisoned statuses. Returns log if applicable."""
        if entity["current_hp"] <= 0:
            return ""

        status = entity.get("status")
        if status == "POISONED":
            # 15% of max HP damage
            damage = max(1, int(entity["max_hp"] * 0.15))
            entity["current_hp"] = max(0, entity["current_hp"] - damage)
            return f"🧪 {entity['name']} suffers {damage} HP damage from poison!"
        elif status == "BURNED":
            # 10% of max HP damage
            damage = max(1, int(entity["max_hp"] * 0.10))
            entity["current_hp"] = max(0, entity["current_hp"] - damage)
            return f"🔥 {entity['name']} suffers {damage} HP damage from burns!"

        return ""
