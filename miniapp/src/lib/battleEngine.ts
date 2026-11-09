import { PokemonItem, BotMove, BotQuest, ShopItem } from "@/types";

/**
 * Moves mapping matching handlers/battle.py
 */
export function getPokemonMoves(pokemonName: string): BotMove[] {
  const name = (pokemonName || "").toLowerCase();

  if (["char", "fire", "burn", "flare", "growlithe", "moltres"].some((x) => name.includes(x))) {
    return [
      { name: "Flamethrower", power: 90, accuracy: 1.0, type: "Fire" },
      { name: "Fire Blast", power: 110, accuracy: 0.85, type: "Fire" },
      { name: "Dragon Claw", power: 80, accuracy: 1.0, type: "Dragon" },
      { name: "Slash", power: 70, accuracy: 1.0, type: "Normal" },
    ];
  } else if (["squirt", "water", "aqua", "hydro", "blastoise", "gyarados"].some((x) => name.includes(x))) {
    return [
      { name: "Hydro Pump", power: 110, accuracy: 0.85, type: "Water" },
      { name: "Surf", power: 90, accuracy: 1.0, type: "Water" },
      { name: "Ice Beam", power: 90, accuracy: 1.0, type: "Ice" },
      { name: "Skull Bash", power: 100, accuracy: 1.0, type: "Normal" },
    ];
  } else if (["bulb", "saur", "grass", "vine", "leaf", "oddish"].some((x) => name.includes(x))) {
    return [
      { name: "Solar Beam", power: 120, accuracy: 1.0, type: "Grass" },
      { name: "Razor Leaf", power: 55, accuracy: 0.95, type: "Grass" },
      { name: "Sludge Bomb", power: 90, accuracy: 1.0, type: "Poison" },
      { name: "Body Slam", power: 85, accuracy: 1.0, type: "Normal" },
    ];
  } else if (["pika", "electric", "spark", "thunder", "zapdos"].some((x) => name.includes(x))) {
    return [
      { name: "Thunderbolt", power: 90, accuracy: 1.0, type: "Electric" },
      { name: "Thunder", power: 110, accuracy: 0.7, type: "Electric" },
      { name: "Iron Tail", power: 100, accuracy: 0.75, type: "Steel" },
      { name: "Quick Attack", power: 40, accuracy: 1.0, type: "Normal" },
    ];
  } else if (["gengar", "ghost", "shadow", "gastly"].some((x) => name.includes(x))) {
    return [
      { name: "Shadow Ball", power: 80, accuracy: 1.0, type: "Ghost" },
      { name: "Dark Pulse", power: 80, accuracy: 1.0, type: "Dark" },
      { name: "Psychic", power: 90, accuracy: 1.0, type: "Psychic" },
      { name: "Sludge Wave", power: 95, accuracy: 1.0, type: "Poison" },
    ];
  } else {
    return [
      { name: "Hyper Beam", power: 150, accuracy: 0.9, type: "Normal" },
      { name: "Double Edge", power: 120, accuracy: 1.0, type: "Normal" },
      { name: "Swift", power: 60, accuracy: 1.0, type: "Normal" },
      { name: "Tackle", power: 40, accuracy: 1.0, type: "Normal" },
    ];
  }
}

/**
 * Exact PvP damage formula from handlers/battle.py
 */
export function calculatePvpDamage(
  attacker: PokemonItem,
  defender: PokemonItem,
  move: BotMove
): { damage: number; isCrit: boolean } {
  const level = attacker.level || 15;
  const power = move.power || 70;
  const atk = attacker.atk || 50;
  const def = Math.max(1, defender.def || 50);

  // Critical hit chance (~8%)
  const isCrit = Math.random() < 0.08;
  const critMultiplier = isCrit ? 1.5 : 1.0;

  // Base formula from bot: (((2 * level / 5 + 2) * power * (atk / def)) / 50 + 2) * modifier
  const baseDmg = ((2 * level / 5 + 2) * power * (atk / def)) / 50 + 2;
  const randomFactor = 0.85 + Math.random() * 0.15;
  const damage = Math.max(1, Math.floor(baseDmg * critMultiplier * randomFactor));

  return { damage, isCrit };
}

/**
 * Real Bot Mystery Boxes & Upgrades from handlers/shop.py
 */
export const MYSTERY_BOXES: ShopItem[] = [
  { id: "buy_box_Common", name: "Common Box", price: 6000, category: "box", description: "Contains a random Common Pokémon.", icon: "📦" },
  { id: "buy_box_Rare", name: "Rare Box", price: 7000, category: "box", description: "Contains a random Rare Pokémon.", icon: "🎁" },
  { id: "buy_box_Epic", name: "Epic Box", price: 8000, category: "box", description: "Contains a random Epic Pokémon.", icon: "🔮" },
  { id: "buy_box_Legendary", name: "Legendary Box", price: 10000, category: "box", description: "Contains a random Legendary Pokémon.", icon: "⭐" },
  { id: "buy_box_Mythical", name: "Mythical Box", price: 14000, category: "box", description: "Contains a random Mythical Pokémon.", icon: "👑" },
  { id: "buy_charm", name: "Shiny Charm", price: 3000, category: "upgrade", description: "Permanently gives +1% shiny upgrade chance!", icon: "✨" },
];

/**
 * Real Bot Quests from handlers/quests.py
 */
export const BOT_QUESTS: BotQuest[] = [
  {
    id: "daily_catch",
    name: "Catch 3 Wild Pokémon",
    description: "Catch wild Pokémon using /catch or mini-app claim",
    type: "daily",
    target_amount: 3,
    current_amount: 1,
    completed: false,
    reward_coins: 500,
    reward_xp: 200,
  },
  {
    id: "daily_chat",
    name: "Send 20 Group Messages",
    description: "Participate actively in the community chat group",
    type: "daily",
    target_amount: 20,
    current_amount: 14,
    completed: false,
    reward_coins: 300,
    reward_xp: 100,
  },
  {
    id: "daily_game",
    name: "Play 1 PvP Duel or Mini-Game",
    description: "Complete a Pokémon PvP battle or game round",
    type: "daily",
    target_amount: 1,
    current_amount: 1,
    completed: true,
    reward_coins: 750,
    reward_xp: 300,
  },
  {
    id: "weekly_catch",
    name: "Catch 20 Wild Pokémon",
    description: "Catch 20 Pokémon across the week",
    type: "weekly",
    target_amount: 20,
    current_amount: 8,
    completed: false,
    reward_coins: 3000,
    reward_xp: 1000,
  },
  {
    id: "weekly_auction",
    name: "Place 2 Auction Bids",
    description: "Bid on rare Pokémon in the auction house",
    type: "weekly",
    target_amount: 2,
    current_amount: 0,
    completed: false,
    reward_coins: 2000,
    reward_xp: 500,
  },
];
