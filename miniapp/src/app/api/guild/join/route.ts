import { NextRequest, NextResponse } from "next/server";
import { queryDb } from "@/lib/db";

export async function POST(req: NextRequest) {
  try {
    const { user_id, guild_id } = await req.json();

    if (!user_id || !guild_id) {
      return NextResponse.json({ error: "Missing parameters" }, { status: 400 });
    }

    // Check if already in guild
    const checkRes = await queryDb(`SELECT guild_id FROM guild_members WHERE user_id = $1`, [user_id]);
    if (checkRes.length > 0) {
      return NextResponse.json({ error: "You are already in a Guild!" }, { status: 400 });
    }

    // Check member limit (30)
    const countRes = await queryDb(
      `SELECT COUNT(*) as count FROM guild_members WHERE guild_id = $1`,
      [guild_id]
    );
    if (countRes.length > 0 && Number(countRes[0].count) >= 30) {
      return NextResponse.json({ error: "This Guild is currently full (30/30)!" }, { status: 400 });
    }

    await queryDb(
      `INSERT INTO guild_members (guild_id, user_id, role)
       VALUES ($1, $2, 'member')`,
      [guild_id, user_id]
    );

    return NextResponse.json({ status: "success", message: "Joined Guild successfully!" });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
