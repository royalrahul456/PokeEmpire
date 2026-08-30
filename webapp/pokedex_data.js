// POKEEMPIRE V3 - Exact Bot Data Engine (from monsters.json, items.json, quests.json)

const MONSTERS_DB = {
  "bulbasaur": { id: 1, name: "Bulbasaur", tier: "Uncommon", types: ["Grass", "Poison"], hp: 45, atk: 49, def: 49, spd: 45, spAtk: 65, spDef: 65, evo: "Ivysaur (Lv. 16)" },
  "ivysaur": { id: 2, name: "Ivysaur", tier: "Rare", types: ["Grass", "Poison"], hp: 60, atk: 62, def: 63, spd: 60, spAtk: 80, spDef: 80, evo: "Venusaur (Lv. 32)" },
  "venusaur": { id: 3, name: "Venusaur", tier: "Epic", types: ["Grass", "Poison"], hp: 80, atk: 82, def: 83, spd: 80, spAtk: 100, spDef: 100, evo: "Final" },
  "charmander": { id: 4, name: "Charmander", tier: "Uncommon", types: ["Fire"], hp: 39, atk: 52, def: 43, spd: 65, spAtk: 60, spDef: 50, evo: "Charmeleon (Lv. 16)" },
  "charmeleon": { id: 5, name: "Charmeleon", tier: "Rare", types: ["Fire"], hp: 58, atk: 64, def: 58, spd: 80, spAtk: 80, spDef: 65, evo: "Charizard (Lv. 36)" },
  "charizard": { id: 6, name: "Charizard", tier: "Epic", types: ["Fire", "Flying"], hp: 78, atk: 84, def: 78, spd: 100, spAtk: 109, spDef: 85, evo: "Final" },
  "squirtle": { id: 7, name: "Squirtle", tier: "Uncommon", types: ["Water"], hp: 44, atk: 48, def: 65, spd: 43, spAtk: 50, spDef: 64, evo: "Wartortle (Lv. 16)" },
  "wartortle": { id: 8, name: "Wartortle", tier: "Rare", types: ["Water"], hp: 59, atk: 63, def: 80, spd: 58, spAtk: 65, spDef: 80, evo: "Blastoise (Lv. 36)" },
  "blastoise": { id: 9, name: "Blastoise", tier: "Epic", types: ["Water"], hp: 79, atk: 83, def: 100, spd: 78, spAtk: 85, spDef: 105, evo: "Final" },
  "caterpie": { id: 10, name: "Caterpie", tier: "Common", types: ["Bug"], hp: 45, atk: 30, def: 35, spd: 45, spAtk: 20, spDef: 20, evo: "Metapod (Lv. 7)" },
  "metapod": { id: 11, name: "Metapod", tier: "Common", types: ["Bug"], hp: 50, atk: 20, def: 55, spd: 30, spAtk: 25, spDef: 25, evo: "Butterfree (Lv. 10)" },
  "butterfree": { id: 12, name: "Butterfree", tier: "Uncommon", types: ["Bug", "Flying"], hp: 60, atk: 45, def: 50, spd: 70, spAtk: 90, spDef: 80, evo: "Final" },
  "rattata": { id: 19, name: "Rattata", tier: "Common", types: ["Normal"], hp: 30, atk: 56, def: 35, spd: 72, spAtk: 25, spDef: 35, evo: "Raticate (Lv. 20)" },
  "raticate": { id: 20, name: "Raticate", tier: "Uncommon", types: ["Normal"], hp: 55, atk: 81, def: 60, spd: 97, spAtk: 50, spDef: 70, evo: "Final" },
  "pikachu": { id: 25, name: "Pikachu", tier: "Rare", types: ["Electric"], hp: 35, atk: 55, def: 40, spd: 90, spAtk: 50, spDef: 50, evo: "Raichu (Thunder Stone)" },
  "raichu": { id: 26, name: "Raichu", tier: "Epic", types: ["Electric"], hp: 60, atk: 90, def: 55, spd: 110, spAtk: 90, spDef: 80, evo: "Final" },
  "gastly": { id: 92, name: "Gastly", tier: "Rare", types: ["Ghost", "Poison"], hp: 30, atk: 35, def: 30, spd: 80, spAtk: 100, spDef: 35, evo: "Haunter (Lv. 25)" },
  "haunter": { id: 93, name: "Haunter", tier: "Epic", types: ["Ghost", "Poison"], hp: 45, atk: 50, def: 45, spd: 95, spAtk: 115, spDef: 55, evo: "Gengar (Lv. 40)" },
  "gengar": { id: 94, name: "Gengar", tier: "Epic", types: ["Ghost", "Poison"], hp: 60, atk: 65, def: 60, spd: 110, spAtk: 130, spDef: 75, evo: "Final" },
  "eevee": { id: 133, name: "Eevee", tier: "Rare", types: ["Normal"], hp: 55, atk: 55, def: 50, spd: 55, spAtk: 45, spDef: 65, evo: "Vaporeon / Jolteon / Flareon" },
  "flareon": { id: 136, name: "Flareon", tier: "Epic", types: ["Fire"], hp: 65, atk: 130, def: 60, spd: 65, spAtk: 95, spDef: 110, evo: "Final" },
  "vaporeon": { id: 134, name: "Vaporeon", tier: "Epic", types: ["Water"], hp: 130, atk: 65, def: 60, spd: 65, spAtk: 110, spDef: 95, evo: "Final" },
  "jolteon": { id: 135, name: "Jolteon", tier: "Epic", types: ["Electric"], hp: 65, atk: 65, def: 60, spd: 130, spAtk: 110, spDef: 95, evo: "Final" },
  "mewtwo": { id: 150, name: "Mewtwo", tier: "Legendary", types: ["Psychic"], hp: 106, atk: 110, def: 90, spd: 130, spAtk: 154, spDef: 90, evo: "Final" },
  "mew": { id: 151, name: "Mew", tier: "Mythical", types: ["Psychic"], hp: 100, atk: 100, def: 100, spd: 100, spAtk: 100, spDef: 100, evo: "Final" }
};

const ITEMS_DB = [
  { key: "ball_basic", name: "Basic Ball", desc: "Standard device for catching wild monsters.", category: "ball", price: 100, icon: "🔴" },
  { key: "ball_great", name: "Great Ball", desc: "High-performance ball with improved catch rate.", category: "ball", price: 300, icon: "🔵" },
  { key: "ball_ultra", name: "Ultra Ball", desc: "Ultra-performance ball for easy catching.", category: "ball", price: 800, icon: "🟡" },
  { key: "ball_master", name: "Master Ball", desc: "Catch any wild monster without fail.", category: "ball", price: 10000, icon: "🟣" },
  { key: "potion_basic", name: "Potion", desc: "Restores 50 HP of a monster.", category: "potion", price: 150, icon: "🧪" },
  { key: "potion_hyper", name: "Hyper Potion", desc: "Restores 200 HP of a monster.", category: "potion", price: 500, icon: "🥤" },
  { key: "revive_basic", name: "Revive", desc: "Revives fainted monster to 50% HP.", category: "revive", price: 800, icon: "💎" },
  { key: "thunder_stone", name: "Thunder Stone", desc: "Evolves Electric monsters.", category: "stone", price: 2000, icon: "⚡" },
  { key: "water_stone", name: "Water Stone", desc: "Evolves Water monsters.", category: "stone", price: 2000, icon: "💧" },
  { key: "fire_stone", name: "Fire Stone", desc: "Evolves Fire monsters.", category: "stone", price: 2000, icon: "🔥" },
  { key: "rare_candy", name: "Rare Candy", desc: "Boosts monster level by 1.", category: "xp", price: 3000, icon: "🍬" }
];

const QUESTS_DB = [
  { key: "quest_daily_catch", name: "Daily Collector", desc: "Catch 3 wild monsters today.", type: "daily", target: 3, rewardCoins: 200, rewardGems: 2, item: "2x Basic Ball" },
  { key: "quest_daily_battle", name: "Daily Challenger", desc: "Win 2 PvE bot battles today.", type: "daily", target: 2, rewardCoins: 300, rewardGems: 3, item: "1x Potion" },
  { key: "quest_weekly_hunt", name: "Weekly Tracker", desc: "Go hunting 20 times.", type: "weekly", target: 20, rewardCoins: 1000, rewardGems: 15, item: "2x Ultra Ball" },
  { key: "quest_weekly_duel", name: "Weekly Duelist", desc: "Win 3 PvP duels against trainers.", type: "weekly", target: 3, rewardCoins: 1500, rewardGems: 20, item: "1x Rare Candy" },
  { key: "quest_story_first_catch", name: "First Hunt", desc: "Catch your first monster.", type: "story", target: 1, rewardCoins: 500, rewardGems: 5, item: "3x Great Ball" },
  { key: "quest_story_level_10", name: "Unlocking Potential", desc: "Reach Trainer Level 10.", type: "story", target: 10, rewardCoins: 2000, rewardGems: 30, item: "1x Master Ball" }
];
