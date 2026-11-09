import { NextRequest, NextResponse } from "next/server";
import { queryDb } from "@/lib/db";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { userId, guildId, flag } = body;

    const uId = Number(userId);
    const gId = Number(guildId);
    const flagVal = String(flag || "shield").trim();

    // Verify user is leader of this guild
    const checkRole = await queryDb(
      `SELECT role FROM guild_members WHERE user_id = $1 AND guild_id = $2 LIMIT 1`,
      [uId, gId]
    );

    if (!checkRole || checkRole.length === 0 || checkRole[0].role !== "leader") {
      return NextResponse.json(
        { error: "Only the Guild Leader can set or change the official animated flag." },
        { status: 403 }
      );
    }

    // Update guild flag
    await queryDb(`UPDATE guilds SET flag = $1 WHERE id = $2`, [flagVal, gId]);

    return NextResponse.json({
      success: true,
      message: "Guild animated flag updated successfully!",
      flag: flagVal,
    });
  } catch (err: any) {
    return NextResponse.json({ error: err.message || "Failed to update guild flag" }, { status: 500 });
  }
}
