import { NextRequest, NextResponse } from "next/server";
import { ACTIVE_BATTLES } from "../matchmake/route";
import { calculatePvpDamage } from "@/lib/battleEngine";
import { queryDb } from "@/lib/db";

export async function POST(req: NextRequest) {
  try {
    const { battle_id, action_type, move_index, switch_index } = await req.json();

    const battle = ACTIVE_BATTLES.get(battle_id);
    if (!battle) {
      return NextResponse.json({ error: "Active battle session expired or not found" }, { status: 404 });
    }

    if (battle.status !== "IN_PROGRESS") {
      return NextResponse.json({ battle });
    }

    const playerMon = battle.player_team[battle.player_active_idx];
    const oppMon = battle.opponent_team[battle.opponent_active_idx];

    // 1. FORFEIT
    if (action_type === "forfeit") {
      battle.status = "DEFEAT";
      battle.combat_log.push("🏳️ You surrendered the match.");
      if (battle.bet > 0) {
        try {
          await queryDb(
            `UPDATE users SET coins = GREATEST(0, coins - $1) WHERE id = $2`,
            [battle.bet, battle.user_id]
          );
        } catch (e) {}
      }
      return NextResponse.json({ battle });
    }

    // 2. SWITCH POKEMON
    if (action_type === "switch") {
      const newIdx = switch_index ?? 0;
      if (newIdx >= battle.player_team.length || battle.player_team[newIdx].fainted) {
        return NextResponse.json({ error: "Cannot switch to a fainted Pokémon!" }, { status: 400 });
      }
      battle.player_active_idx = newIdx;
      battle.combat_log.push(`🔄 Come back! Go, ${battle.player_team[newIdx].name}!`);

      // Opponent gets free turn attack on switch
      const oppMove = oppMon.moves ? oppMon.moves[Math.floor(Math.random() * oppMon.moves.length)] : { name: "Tackle", power: 40, accuracy: 1 };
      const oppCalc = calculatePvpDamage(oppMon, battle.player_team[newIdx], oppMove);
      battle.player_team[newIdx].hp = Math.max(0, battle.player_team[newIdx].hp - oppCalc.damage);
      const critText = oppCalc.isCrit ? "Critical hit! " : "";
      battle.combat_log.push(
        `${battle.opponent_name}'s ${oppMon.name} used ${oppMove.name}! ${critText}(-${oppCalc.damage} HP)`
      );

      if (battle.player_team[newIdx].hp <= 0) {
        battle.player_team[newIdx].fainted = true;
        battle.combat_log.push(`💀 Your ${battle.player_team[newIdx].name} fainted!`);
      }

      battle.turn += 1;
      return NextResponse.json({ battle });
    }

    // 3. ATTACK
    const pMoveIdx = move_index ?? 0;
    const playerMove = (playerMon.moves && playerMon.moves[pMoveIdx]) || { name: "Tackle", power: 40, accuracy: 1 };
    const oppMove = (oppMon.moves && oppMon.moves[Math.floor(Math.random() * oppMon.moves.length)]) || { name: "Tackle", power: 40, accuracy: 1 };

    // Speed priority
    const playerFirst = (playerMon.spd || 50) >= (oppMon.spd || 50);
    const firstAttacker = playerFirst ? playerMon : oppMon;
    const firstDefender = playerFirst ? oppMon : playerMon;
    const firstMove = playerFirst ? playerMove : oppMove;
    const firstIsPlayer = playerFirst;

    // First Strike
    const calc1 = calculatePvpDamage(firstAttacker, firstDefender, firstMove);
    firstDefender.hp = Math.max(0, firstDefender.hp - calc1.damage);
    const crit1 = calc1.isCrit ? "Critical hit! " : "";
    const name1 = firstIsPlayer ? "Your" : `${battle.opponent_name}'s`;
    battle.combat_log.push(
      `${name1} ${firstAttacker.name} used ${firstMove.name}! ${crit1}(-${calc1.damage} HP)`
    );

    if (firstDefender.hp <= 0) {
      firstDefender.fainted = true;
      const faintedName = firstIsPlayer ? `${battle.opponent_name}'s` : "Your";
      battle.combat_log.push(`💀 ${faintedName} ${firstDefender.name} fainted!`);
    } else {
      // Counter Strike
      const secondAttacker = firstDefender;
      const secondDefender = firstAttacker;
      const secondMove = firstIsPlayer ? oppMove : playerMove;
      const secondIsPlayer = !firstIsPlayer;

      const calc2 = calculatePvpDamage(secondAttacker, secondDefender, secondMove);
      secondDefender.hp = Math.max(0, secondDefender.hp - calc2.damage);
      const crit2 = calc2.isCrit ? "Critical hit! " : "";
      const name2 = secondIsPlayer ? "Your" : `${battle.opponent_name}'s`;
      battle.combat_log.push(
        `${name2} ${secondAttacker.name} used ${secondMove.name}! ${crit2}(-${calc2.damage} HP)`
      );

      if (secondDefender.hp <= 0) {
        secondDefender.fainted = true;
        const faintedName2 = secondIsPlayer ? `${battle.opponent_name}'s` : "Your";
        battle.combat_log.push(`💀 ${faintedName2} ${secondDefender.name} fainted!`);
      }
    }

    // Check Opponent Bench
    if (battle.opponent_team[battle.opponent_active_idx].fainted) {
      const nextOppIdx = battle.opponent_team.findIndex((m) => !m.fainted);
      if (nextOppIdx !== -1) {
        battle.opponent_active_idx = nextOppIdx;
        battle.combat_log.push(
          `⚠️ ${battle.opponent_name} sent out ${battle.opponent_team[nextOppIdx].name}!`
        );
      } else {
        // VICTORY!
        battle.status = "VICTORY";
        const winnings = battle.bet > 0 ? battle.bet : 250;
        const xpGained = 150;
        battle.rewards = {
          coins: winnings,
          xp: xpGained,
        };
        battle.combat_log.push(
          `🏆 VICTORY! You defeated ${battle.opponent_name}! (+${winnings} Coins, +${xpGained} XP)`
        );

        try {
          await queryDb(
            `UPDATE users
             SET coins = coins + $1,
                 trainer_xp = trainer_xp + $2
             WHERE id = $3`,
            [winnings, xpGained, battle.user_id]
          );
        } catch (e) {}
      }
    }

    // Check Player Bench
    if (battle.player_team[battle.player_active_idx].fainted) {
      const nextPIdx = battle.player_team.findIndex((m) => !m.fainted);
      if (nextPIdx !== -1) {
        battle.player_active_idx = nextPIdx;
        battle.combat_log.push(`🔄 Go! ${battle.player_team[nextPIdx].name}!`);
      } else {
        // DEFEAT!
        battle.status = "DEFEAT";
        battle.rewards = { coins: 0, xp: 25 };
        battle.combat_log.push(`💥 All your Pokémon fainted! You lost the duel.`);

        if (battle.bet > 0) {
          try {
            await queryDb(
              `UPDATE users
               SET coins = GREATEST(0, coins - $1),
                   trainer_xp = trainer_xp + 25
               WHERE id = $2`,
              [battle.bet, battle.user_id]
            );
          } catch (e) {}
        }
      }
    }

    battle.turn += 1;
    return NextResponse.json({ battle });
  } catch (err: any) {
    return NextResponse.json({ error: err.message }, { status: 500 });
  }
}
