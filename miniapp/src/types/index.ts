export type ThemeMode = "light" | "dark" | "system";

export type NavTab = "home" | "battle" | "guild" | "leaderboard" | "profile";

export interface BotMove {
  name: string;
  power: number;
  accuracy: number;
  type?: string;
}

export interface PlayerProfile {
  id: number;
  username: string;
  nickname: string;
  avatar_url?: string;
  coins: number;
  gems: number;
  level: number;
  xp: number;
  next_level_xp: number;
  current_streak: number;
  best_streak: number;
  can_claim_daily: boolean;
  next_daily_seconds: number;
  can_claim_pokemon: boolean;
  next_claim_seconds: number;
  pokemon_count: number;
  guild_id?: number | null;
  guild_name?: string | null;
  guild_tag?: string | null;
  guild_role?: string | null;
  is_vip: boolean;
  vip_tier?: string | null;
  pvp_wins: number;
  pvp_losses: number;
}

export interface PokemonItem {
  id: number;
  pokemon_id: number;
  name: string;
  nickname?: string;
  rarity: "Common" | "Uncommon" | "Medium" | "Rare" | "Epic" | "Legendary" | "Mythical";
  generation: number;
  level: number;
  xp: number;
  types: string[];
  hp: number;
  max_hp: number;
  atk: number;
  def: number;
  spd: number;
  iv_hp: number;
  iv_atk: number;
  iv_def: number;
  iv_spd: number;
  image_url: string;
  is_shiny: boolean;
  is_amv?: boolean;
  form_index?: number;
  fainted?: boolean;
  moves?: BotMove[];
}

export interface BotQuest {
  id: string;
  name: string;
  description: string;
  type: "daily" | "weekly";
  target_amount: number;
  current_amount: number;
  completed: boolean;
  reward_coins: number;
  reward_xp: number;
}

export interface ShopItem {
  id: string;
  name: string;
  description: string;
  category: "box" | "upgrade";
  price: number;
  icon: string;
  shiny_rate?: string;
}

export interface PvpDuelSession {
  battle_id: string;
  user_id: number;
  opponent_name: string;
  opponent_avatar: string;
  bet: number;
  format_type: 3 | 6;
  player_team: PokemonItem[];
  opponent_team: PokemonItem[];
  player_active_idx: number;
  opponent_active_idx: number;
  turn: number;
  status: "IN_PROGRESS" | "VICTORY" | "DEFEAT";
  combat_log: string[];
  rewards?: {
    coins: number;
    xp: number;
  };
}

export interface GuildMember {
  user_id: number;
  username: string;
  nickname: string;
  role: "leader" | "co_leader" | "member";
  level: number;
  joined_at: string;
}

export interface GuildData {
  id: number;
  name: string;
  tag: string;
  owner_id: number;
  owner_name?: string;
  treasury: number;
  level: number;
  members_count: number;
  max_members: number;
  created_at: string;
  announcement?: string;
  flag?: string;
  flag_locked?: boolean;
  members?: GuildMember[];
}

export interface LeaderboardEntry {
  rank: number;
  id: number;
  username: string;
  nickname: string;
  avatar_url?: string;
  level: number;
  score: number;
  sub_label: string;
  badge_emoji: string;
}
