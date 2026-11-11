import { NextRequest, NextResponse } from "next/server";
import { getPokemonMoves } from "@/lib/battleEngine";
import { queryDb } from "@/lib/db";
import { PvpDuelSession, PokemonItem } from "@/types";

// In-memory active battle sessions cache
export const ACTIVE_BATTLES = new Map<string, PvpDuelSession>();

export async function POST(req: NextRequest) {
  try {
    const { user_id, bet = 0, team } = await req.json();

    if (!team || team.length === 0) {
      return NextResponse.json({ error: "Select at least 1 Pokémon to battle!" }, { status: 400 });
    }

    const playerTeam: PokemonItem[] = JSON.parse(JSON.stringify(team)).map((p: PokemonItem) => ({
      ...p,
      fainted: false,
      hp: p.max_hp || p.hp,
      moves: p.moves && p.moves.length > 0 ? p.moves : getPokemonMoves(p.name),
    }));

    // Find a rival trainer from DB or fallback
    let rivalName = "Rival Gary";
    try {
      const rows = await queryDb(
        `SELECT id, username, nickname FROM users WHERE id != $1 ORDER BY RANDOM() LIMIT 1`,
        [user_id]
      );
      if (rows && rows.length > 0) {
        rivalName = rows[0].nickname || rows[0].username || "Rival Gary";
      }
    } catch (e) {
      // Fallback
    }

    // Opponent 3-Pokemon squad matching bot
    const opponentTeam: PokemonItem[] = [
      {
        id: 901,
        pokemon_id: 130,
        name: "Gyarados",
        rarity: "Rare",
        generation: 1,
        level: 30,
        xp: 150,
        types: ["Water", "Flying"],
        hp: 120,
        max_hp: 120,
        atk: 105,
        def: 80,
        spd: 85,
        iv_hp: 25,
        iv_atk: 28,
        iv_def: 24,
        iv_spd: 26,
        moves: getPokemonMoves("Gyarados"),
        image_url: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/130.png",
        is_shiny: false,
        fainted: false,
      },
      {
        id: 902,
        pokemon_id: 59,
        name: "Arcanine",
        rarity: "Rare",
        generation: 1,
        level: 31,
        xp: 160,
        types: ["Fire"],
        hp: 125,
        max_hp: 125,
        atk: 110,
        def: 80,
        spd: 95,
        iv_hp: 26,
        iv_atk: 29,
        iv_def: 25,
        iv_spd: 28,
        moves: getPokemonMoves("Arcanine"),
        image_url: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/59.png",
        is_shiny: false,
        fainted: false,
      },
      {
        id: 903,
        pokemon_id: 94,
        name: "Gengar",
        rarity: "Epic",
        generation: 1,
        level: 32,
        xp: 175,
        types: ["Ghost", "Poison"],
        hp: 110,
        max_hp: 110,
        atk: 115,
        def: 75,
        spd: 110,
        iv_hp: 22,
        iv_atk: 31,
        iv_def: 20,
        iv_spd: 30,
        moves: getPokemonMoves("Gengar"),
        image_url: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/94.png",
        is_shiny: true,
        fainted: false,
      },
    ];

    const battleId = `battle_${Date.now()}_${Math.random().toString(36).substring(2, 7)}`;
    const duelSession: PvpDuelSession = {
      battle_id: battleId,
      user_id,
      opponent_name: rivalName,
      opponent_avatar: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/trainers/1.png",
      bet: Number(bet) || 0,
      format_type: 3,
      player_team: playerTeam,
      opponent_team: opponentTeam,
      player_active_idx: 0,
      opponent_active_idx: 0,
      turn: 1,
      status: "IN_PROGRESS",
      combat_log: [
        `⚔️ PvP Duel started against ${rivalName}!`,
        bet > 0 ? `💰 Pot: ${(bet * 2).toLocaleString()} Coins (${bet.toLocaleString()} wagered each)` : `🤝 Friendly duel (no wager)`,
        `▶️ You sent out ${playerTeam[0].name}!`,
        `▶️ ${rivalName} sent out ${opponentTeam[0].name}!`,
      ],
    };

    ACTIVE_BATTLES.set(battleId, duelSession);

    return NextResponse.json({ battle: duelSession });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
