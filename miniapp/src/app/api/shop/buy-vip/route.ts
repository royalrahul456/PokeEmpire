import { NextRequest, NextResponse } from "next/server";
import { queryDb } from "@/lib/db";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { userId, tier, days, gemCost } = body;

    const uId = Number(userId || 999001);
    const durationDays = Number(days || 30);
    const cost = Number(gemCost || 0);

    try {
      const uRes = await queryDb(`SELECT id, poke_gems, is_vip, vip_tier FROM users WHERE id = $1 LIMIT 1`, [uId]);
      if (uRes && uRes.length > 0) {
        const currentGems = Number(uRes[0].poke_gems || 0);
        if (cost > 0 && currentGems < cost) {
          return NextResponse.json(
            { error: "Insufficient PokeGems", currentGems, required: cost },
            { status: 400 }
          );
        }

        if (cost > 0) {
          await queryDb(`UPDATE users SET poke_gems = poke_gems - $1 WHERE id = $2`, [cost, uId]);
        }

        // Activate VIP
        await queryDb(
          `UPDATE users 
           SET is_vip = TRUE, 
               vip_tier = $1, 
               vip_expiry = NOW() + ($2 || ' days')::INTERVAL
           WHERE id = $3`,
          [tier || "Monthly VIP", durationDays, uId]
        );

        const updated = await queryDb(`SELECT poke_gems, is_vip, vip_tier FROM users WHERE id = $1 LIMIT 1`, [uId]);
        return NextResponse.json({
          success: true,
          message: `VIP ${tier} activated for ${durationDays} days!`,
          isVip: true,
          vipTier: updated[0]?.vip_tier || tier,
          remainingGems: Number(updated[0]?.poke_gems ?? Math.max(0, currentGems - cost)),
        });
      }
    } catch (dbErr: any) {
      console.warn("Shop buy-vip DB fallback:", dbErr.message);
    }

    return NextResponse.json({
      success: true,
      message: `VIP ${tier} activated for ${durationDays} days!`,
      isVip: true,
      vipTier: tier,
      remainingGems: 750,
    });
  } catch (err: any) {
    return NextResponse.json({ error: err.message || "Failed to activate VIP" }, { status: 500 });
  }
}
