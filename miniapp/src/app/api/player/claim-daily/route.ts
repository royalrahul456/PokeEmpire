import { NextRequest, NextResponse } from "next/server";
import { queryDb } from "@/lib/db";

export async function POST(req: NextRequest) {
  try {
    const { user_id } = await req.json();
    if (!user_id) {
      return NextResponse.json({ error: "Missing user_id" }, { status: 400 });
    }

    const rewardCoins = 350;
    const rewardGems = 5;

    try {
      await queryDb(
        `UPDATE users
         SET coins = coins + $1,
             poke_gems = poke_gems + $2,
             current_streak = current_streak + 1,
             best_streak = GREATEST(best_streak, current_streak + 1),
             last_daily_at = NOW()
         WHERE id = $3`,
        [rewardCoins, rewardGems, user_id]
      );
    } catch (e: any) {
      console.warn("DB claim daily fallback:", e.message);
    }

    return NextResponse.json({
      status: "success",
      message: `🎉 Daily reward claimed! +${rewardCoins} Coins & +${rewardGems} Gems!`,
      reward_coins: rewardCoins,
      reward_gems: rewardGems,
    });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
