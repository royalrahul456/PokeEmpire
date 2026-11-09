import { NextRequest, NextResponse } from "next/server";
import { queryDb } from "@/lib/db";
import { GuildData, GuildMember } from "@/types";

export async function GET(req: NextRequest) {
  const { searchParams } = new URL(req.url);
  const userId = searchParams.get("user_id") || "6593485710";

  try {
    const memberRows = await queryDb(
      `SELECT gm.guild_id, gm.role, g.name, g.tag, g.owner_id, g.treasury, g.level, g.created_at, g.flag, g.flag_locked,
              u.nickname as owner_name
       FROM guild_members gm
       JOIN guilds g ON g.id = gm.guild_id
       LEFT JOIN users u ON u.id = g.owner_id
       WHERE gm.user_id = $1 LIMIT 1`,
      [userId]
    );

    if (!memberRows || memberRows.length === 0) {
      return NextResponse.json({ in_guild: false, guild: null });
    }

    const g = memberRows[0];
    const membersListRows = await queryDb(
      `SELECT gm.user_id, gm.role, gm.joined_at, u.username, u.nickname, u.trainer_level as level
       FROM guild_members gm
       JOIN users u ON u.id = gm.user_id
       WHERE gm.guild_id = $1
       ORDER BY CASE WHEN gm.role = 'leader' THEN 1 WHEN gm.role = 'co_leader' THEN 2 ELSE 3 END, gm.joined_at ASC`,
      [g.guild_id]
    );

    const members: GuildMember[] = membersListRows.map((m: any) => ({
      user_id: Number(m.user_id),
      username: m.username || `Trainer_${m.user_id}`,
      nickname: m.nickname || "Trainer",
      role: m.role || "member",
      level: Number(m.level || 1),
      joined_at: new Date(m.joined_at).toLocaleDateString(),
      is_online: true,
    }));

    const guild: GuildData = {
      id: Number(g.guild_id),
      name: g.name,
      tag: g.tag,
      owner_id: Number(g.owner_id),
      owner_name: g.owner_name || "Guildmaster",
      treasury: Number(g.treasury || 0),
      level: Number(g.level || 1),
      members_count: members.length,
      max_members: 30,
      announcement: `Welcome to [${g.tag}] ${g.name}! Complete daily raids and donate to level up our treasury.`,
      created_at: new Date(g.created_at).toLocaleDateString(),
      flag: g.flag || "shield",
      flag_locked: Boolean(g.flag_locked),
      members,
    };

    return NextResponse.json({ in_guild: true, guild });
  } catch (err: any) {
    // Return sample guild for testing
    return NextResponse.json({ in_guild: false, guild: null });
  }
}
