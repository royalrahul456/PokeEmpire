import { NextRequest, NextResponse } from "next/server";
import { verifyTelegramInitData } from "@/lib/telegram";
import { queryDb } from "@/lib/db";
import { PlayerProfile } from "@/types";

const BOT_TOKEN = process.env.TELEGRAM_BOT_TOKEN || process.env.BOT_TOKEN || "8733227680:AAGHijvxZqpXKugVkJS2AszYIIRkkgG6K8g";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { init_data, mock_user_id, mock_username, mock_nickname } = body;

    let tgUser: any = null;
    if (init_data && BOT_TOKEN) {
      const res = verifyTelegramInitData(init_data, BOT_TOKEN);
      if (res.isValid && res.user) {
        tgUser = res.user;
      }
    }

    const userId = tgUser?.id || mock_user_id || 6593485710;
    const username = tgUser?.username || mock_username || "TheDarkKratosX";
    const nickname = tgUser?.first_name || mock_nickname || "R ꫝ፝֟፝ ʜ ᴜ ʟㅤ⸙";

    let dbUser: any = null;
    let guildInfo: any = null;
    let pokemonCount = 0;

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

      if (rows && rows.length > 0) {
        dbUser = rows[0];
        pokemonCount = Number(dbUser.pokemon_count || 0);
        if (dbUser.guild_id) {
          guildInfo = {
            id: dbUser.guild_id,
            name: dbUser.guild_name,
            tag: dbUser.guild_tag,
            role: dbUser.guild_role,
          };
        }
      } else {
        // Register new trainer in database
        const insertRes = await queryDb(
          `INSERT INTO users (id, username, nickname, coins, poke_gems, trainer_level, trainer_xp)
           VALUES ($1, $2, $3, 1000, 25, 1, 0)
           RETURNING *`,
          [userId, username, nickname]
        );
        dbUser = insertRes[0];

        // Seed 3 starter pokemon for the new user if they have none
        const starterIds = [4, 7, 1]; // Charmander, Squirtle, Bulbasaur
        for (const pid of starterIds) {
          try {
            await queryDb(
              `INSERT INTO user_pokemon (user_id, pokemon_id, nickname, level, xp, iv_hp, iv_atk, iv_def, iv_spd)
               VALUES ($1, $2, (SELECT name FROM pokemon WHERE id = $2 LIMIT 1), 15, 50, 24, 26, 22, 28)
               ON CONFLICT DO NOTHING`,
              [userId, pid]
            );
          } catch (e) {
            // Ignore starter conflict
          }
        }
        pokemonCount = 3;
      }
    } catch (dbErr: any) {
      console.warn("Database fallback in auth/verify:", dbErr.message);
      dbUser = {
        id: userId,
        username,
        nickname,
        coins: 1500,
        poke_gems: 30,
        trainer_level: 5,
        trainer_xp: 220,
        current_streak: 3,
        best_streak: 5,
        is_vip: false,
        vip_tier: null,
      };
      pokemonCount = 3;
    }

    // Daily Claim Cooldown calculation
    const lastDaily = dbUser.last_daily_at ? new Date(dbUser.last_daily_at) : null;
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

    const photoUrl = tgUser?.photo_url || dbUser?.avatar_url || "/profile-avatar.png";

    const player: PlayerProfile = {
      id: Number(dbUser.id),
      username: dbUser.username || username || "TheDarkKratosX",
      nickname: dbUser.nickname || nickname || "Rahul",
      avatar_url: photoUrl,
      coins: Number(dbUser.coins || 0),
      gems: Number(dbUser.poke_gems || 0),
      level: Number(dbUser.trainer_level || 1),
      xp: Number(dbUser.trainer_xp || 0),
      next_level_xp: (Number(dbUser.trainer_level || 1)) * 100,
      current_streak: Number(dbUser.current_streak || 0),
      best_streak: Number(dbUser.best_streak || 0),
      can_claim_daily: canClaim,
      next_daily_seconds: nextClaimSeconds,
      can_claim_pokemon: true,
      next_claim_seconds: 0,
      pokemon_count: pokemonCount,
      guild_id: guildInfo?.id || null,
      guild_name: guildInfo?.name || null,
      guild_tag: guildInfo?.tag || null,
      guild_role: guildInfo?.role || null,
      is_vip: Boolean(dbUser.is_vip),
      vip_tier: dbUser.vip_tier || null,
      pvp_wins: Number(dbUser.pvp_wins || 0),
      pvp_losses: Number(dbUser.pvp_losses || 0),
    };

    return NextResponse.json({
      success: true,
      authenticated: Boolean(tgUser),
      player,
    });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
