import { NextRequest, NextResponse } from "next/server";
import { queryDb } from "@/lib/db";
import { getPokemonMoves } from "@/lib/battleEngine";
import { PokemonItem } from "@/types";

const STARTER_ROSTER: PokemonItem[] = [
  {
    id: 101,
    pokemon_id: 6,
    name: "Charizard",
    nickname: "Ignis",
    rarity: "Epic",
    generation: 1,
    level: 36,
    xp: 220,
    types: ["Fire", "Flying"],
    hp: 135,
    max_hp: 135,
    atk: 104,
    def: 78,
    spd: 100,
    iv_hp: 28,
    iv_atk: 31,
    iv_def: 25,
    iv_spd: 30,
    moves: getPokemonMoves("Charizard"),
    image_url: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/6.png",
    is_shiny: true,
  },
  {
    id: 102,
    pokemon_id: 9,
    name: "Blastoise",
    nickname: "Torrent",
    rarity: "Rare",
    generation: 1,
    level: 34,
    xp: 180,
    types: ["Water"],
    hp: 142,
    max_hp: 142,
    atk: 85,
    def: 110,
    spd: 78,
    iv_hp: 29,
    iv_atk: 22,
    iv_def: 30,
    iv_spd: 20,
    moves: getPokemonMoves("Blastoise"),
    image_url: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/9.png",
    is_shiny: false,
  },
  {
    id: 103,
    pokemon_id: 25,
    name: "Pikachu",
    nickname: "Sparky",
    rarity: "Rare",
    generation: 1,
    level: 30,
    xp: 140,
    types: ["Electric"],
    hp: 95,
    max_hp: 95,
    atk: 80,
    def: 60,
    spd: 115,
    iv_hp: 24,
    iv_atk: 27,
    iv_def: 19,
    iv_spd: 31,
    moves: getPokemonMoves("Pikachu"),
    image_url: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/25.png",
    is_shiny: false,
  },
];

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const userId = searchParams.get("user_id") || "6593485710";

  try {
    const rows = await queryDb(
      `SELECT up.id as up_id, up.pokemon_id, up.nickname, up.level, up.xp,
              up.iv_hp, up.iv_atk, up.iv_def, up.iv_spd, up.is_shiny, up.is_amv,
              p.name, p.rarity, p.generation, p.image_url
       FROM user_pokemon up
       JOIN pokemon p ON p.id = up.pokemon_id
       WHERE up.user_id = $1
       ORDER BY up.level DESC, up.id DESC`,
      [userId]
    );

    if (rows && rows.length > 0) {
      const pokemonList: PokemonItem[] = rows.map((r: any) => {
        const types = r.name.toLowerCase().includes("char")
          ? ["Fire", "Flying"]
          : r.name.toLowerCase().includes("squirt") || r.name.toLowerCase().includes("blastoise")
          ? ["Water"]
          : r.name.toLowerCase().includes("bulb") || r.name.toLowerCase().includes("saur")
          ? ["Grass", "Poison"]
          : r.name.toLowerCase().includes("pika")
          ? ["Electric"]
          : ["Normal"];

        const hp = Math.floor(50 + (r.level * 2.2) + (r.iv_hp || 15));
        const atk = Math.floor(40 + (r.level * 1.8) + (r.iv_atk || 15));
        const def = Math.floor(35 + (r.level * 1.7) + (r.iv_def || 15));
        const spd = Math.floor(45 + (r.level * 1.9) + (r.iv_spd || 15));

        return {
          id: Number(r.up_id),
          pokemon_id: Number(r.pokemon_id),
          name: r.name ? r.name.charAt(0).toUpperCase() + r.name.slice(1) : "Pokemon",
          nickname: r.nickname || r.name,
          rarity: r.rarity || "Common",
          generation: Number(r.generation || 1),
          level: Number(r.level || 15),
          xp: Number(r.xp || 50),
          types,
          hp,
          max_hp: hp,
          atk,
          def,
          spd,
          iv_hp: r.iv_hp || 20,
          iv_atk: r.iv_atk || 20,
          iv_def: r.iv_def || 20,
          iv_spd: r.iv_spd || 20,
          moves: getPokemonMoves(r.name || "Pokemon"),
          image_url: r.image_url?.startsWith("http")
            ? r.image_url
            : `https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/${r.pokemon_id}.png`,
          is_shiny: Boolean(r.is_shiny),
          is_amv: Boolean(r.is_amv),
        };
      });

      return NextResponse.json({ roster: pokemonList });
    }

    return NextResponse.json({ roster: STARTER_ROSTER });
  } catch (err: any) {
    return NextResponse.json({ roster: STARTER_ROSTER });
  }
}
