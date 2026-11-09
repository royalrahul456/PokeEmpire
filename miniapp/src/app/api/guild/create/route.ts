import { NextRequest, NextResponse } from "next/server";
import { queryDb } from "@/lib/db";

export async function POST(req: NextRequest) {
  try {
    const { user_id, name, tag } = await req.json();

    if (!user_id || !name || !tag) {
      return NextResponse.json({ error: "Guild Name and Tag are required." }, { status: 400 });
    }

    if (tag.length < 2 || tag.length > 5) {
      return NextResponse.json({ error: "Tag must be 2 to 5 characters." }, { status: 400 });
    }

    const creationCost = 5000;

    // Check coins & existing guild membership
    const userRes = await queryDb(
      `SELECT coins, (SELECT guild_id FROM guild_members WHERE user_id = $1 LIMIT 1) as existing_guild
       FROM users WHERE id = $1`,
      [user_id]
    );

    if (userRes.length > 0 && userRes[0].existing_guild) {
      return NextResponse.json({ error: "You are already a member of a Guild!" }, { status: 400 });
    }

    if (userRes.length > 0 && userRes[0].coins < creationCost) {
      return NextResponse.json(
        { error: `Insufficient coins. Guild creation requires 🪙 ${creationCost} coins.` },
        { status: 400 }
      );
    }

    // Deduct coins & Insert guild
    await queryDb(`UPDATE users SET coins = coins - $1 WHERE id = $2`, [creationCost, user_id]);

    const cleanTag = tag.toUpperCase().trim();
    const cleanName = name.trim();

    const guildRes = await queryDb(
      `INSERT INTO guilds (name, tag, owner_id, treasury, level)
       VALUES ($1, $2, $3, 1000, 1)
       RETURNING id, name, tag`,
      [cleanName, cleanTag, user_id]
    );

    const guildId = guildRes[0].id;

    // Insert user as leader
    await queryDb(
      `INSERT INTO guild_members (guild_id, user_id, role)
       VALUES ($1, $2, 'leader')`,
      [guildId, user_id]
    );

    return NextResponse.json({
      status: "success",
      message: `🎉 Guild [${cleanTag}] ${cleanName} created successfully!`,
      guild: guildRes[0],
    });
  } catch (err: any) {
    if (err.message?.includes("unique")) {
      return NextResponse.json({ error: "A Guild with that Name or Tag already exists!" }, { status: 400 });
    }
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
