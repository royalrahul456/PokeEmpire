import { NextRequest, NextResponse } from "next/server";
import { queryDb } from "@/lib/db";
import { PlayerProfile } from "@/types";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const userId = searchParams.get("user_id") || "6593485710";

  try {
    const rows = await queryDb(
      `SELECT u.*, g.id as guild_id, g.name as guild_name, g.tag as guild_tag, gm.role as guild_role,
              (SELECT COUNT(*) FROM user_pokemon WHERE user_id = u.id) as pokemon_count
       FROM users u
       LEFT JOIN guild_members gm ON gm.user_id = u.id
       LEFT JOIN guilds g ON g.id = gm.guild_id
       WHERE u.id = $1 LIMIT 1`,
      [userId]
    );

    if (!rows || rows.length === 0) {
      return NextResponse.json({ error: "User not found" }, { status: 404 });
    }

    const u = rows[0];

    const lastDaily = u.last_daily_at ? new Date(u.last_daily_at) : null;
    let canClaim = true;
    let nextClaimSeconds = 0;
    if (lastDaily) {
      const diffMs = Date.now() - lastDaily.getTime();
      const twentyFourHours = 24 * 60 * 60 * 1000;
      if (diffMs < twentyFourHours) {
        canClaim = false;
        nextClaimSeconds = Math.floor((twentyFourHours - diffMs) / 1000);
      }
    }

    const player: PlayerProfile = {
      id: Number(u.id),
      username: u.username || "TheDarkKratosX",
      nickname: u.nickname || "Rahul",
      avatar_url: u.avatar_url || "/profile-avatar.png",
      coins: Number(u.coins || 0),
      gems: Number(u.poke_gems || 0),
      level: Number(u.trainer_level || 1),
      xp: Number(u.trainer_xp || 0),
      next_level_xp: (Number(u.trainer_level || 1)) * 100,
      current_streak: Number(u.current_streak || 0),
      best_streak: Number(u.best_streak || 0),
      can_claim_daily: canClaim,
      next_daily_seconds: nextClaimSeconds,
      can_claim_pokemon: true,
      next_claim_seconds: 0,
      pokemon_count: Number(u.pokemon_count || 0),
      guild_id: u.guild_id || null,
      guild_name: u.guild_name || null,
      guild_tag: u.guild_tag || null,
      guild_role: u.guild_role || null,
      is_vip: Boolean(u.is_vip),
      vip_tier: u.vip_tier || null,
      pvp_wins: Number(u.pvp_wins || 0),
      pvp_losses: Number(u.pvp_losses || 0),
    };

    return NextResponse.json({ player });
  } catch (err: any) {
    return NextResponse.json({
      player: {
        id: Number(userId),
        username: "TheDarkKratosX",
        nickname: "Rahul",
        avatar_url: "/profile-avatar.png",
        coins: 1500,
        gems: 30,
        level: 5,
        xp: 220,
        next_level_xp: 500,
        current_streak: 3,
        best_streak: 5,
        can_claim_daily: true,
        next_daily_seconds: 0,
        can_claim_pokemon: true,
        next_claim_seconds: 0,
        pokemon_count: 6,
        guild_id: null,
        guild_name: null,
        guild_tag: null,
        guild_role: null,
        is_vip: false,
        vip_tier: null,
        pvp_wins: 14,
        pvp_losses: 3,
      }
    });
  }
}
