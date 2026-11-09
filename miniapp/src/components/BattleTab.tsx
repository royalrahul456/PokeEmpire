"use client";

import React, { useState, useRef, useEffect } from "react";
import {
  PlayerProfile,
  PokemonItem,
  PvpDuelSession,
  BotMove
} from "@/types";
import {
  Swords,
  Shield,
  Coins,
  ArrowRightLeft,
  Flag,
  Flame,
  Droplets,
  Zap,
  ChevronRight,
  AlertCircle,
  RotateCcw,
  Clock,
  Search,
  X,
  CheckCircle2,
  Sparkles,
  Trophy
} from "lucide-react";
import { triggerTelegramHaptic } from "@/lib/telegram";

interface BattleTabProps {
  player: PlayerProfile | null;
  roster: PokemonItem[];
  battle: PvpDuelSession | null;
  onStartBattle: (bet: number, customTeam?: PokemonItem[]) => Promise<void>;
  onAttack: (moveIndex: number) => Promise<void>;
  onSwitch: (switchIndex: number) => Promise<void>;
  onForfeit: () => Promise<void>;
  onCloseBattle: () => void;
  isActionLoading: boolean;
}

const RIVAL_TRAINERS = [
  { name: "Cynthia_Champion", avatar: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/trainers/2.png", level: 45, winRate: "78%", badge: "Sinnoh Champion" },
  { name: "Red_Legend", avatar: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/trainers/1.png", level: 50, winRate: "88%", badge: "Mt. Silver Master" },
  { name: "Ash_Ketchum_99", avatar: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/trainers/3.png", level: 38, winRate: "65%", badge: "World Monarch" },
  { name: "Steven_Hoenn", avatar: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/trainers/4.png", level: 42, winRate: "72%", badge: "Steel Specialist" },
  { name: "Lance_Dragonite", avatar: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/trainers/5.png", level: 44, winRate: "75%", badge: "Dragon Master" },
  { name: "Blue_Oak_Ace", avatar: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/trainers/6.png", level: 40, winRate: "70%", badge: "Viridian Leader" },
];

const TYPE_COLORS: Record<string, string> = {
  Fire: "bg-red-500/20 text-red-500 border-red-500/30",
  Water: "bg-blue-500/20 text-blue-500 border-blue-500/30",
  Grass: "bg-emerald-500/20 text-emerald-500 border-emerald-500/30",
  Electric: "bg-amber-500/20 text-amber-500 border-amber-500/30",
  Psychic: "bg-pink-500/20 text-pink-500 border-pink-500/30",
  Ghost: "bg-purple-500/20 text-purple-500 border-purple-500/30",
  Dragon: "bg-indigo-500/20 text-indigo-500 border-indigo-500/30",
  Normal: "bg-slate-500/20 text-slate-400 border-slate-500/30",
};

export const BattleTab: React.FC<BattleTabProps> = ({
  player,
  roster,
  battle,
  onStartBattle,
  onAttack,
  onSwitch,
  onForfeit,
  onCloseBattle,
  isActionLoading,
}) => {
  const [selectedBet, setSelectedBet] = useState<number>(500);
  const [showSwitchModal, setShowSwitchModal] = useState(false);
  const [hitOpponent, setHitOpponent] = useState(false);
  const [hitPlayer, setHitPlayer] = useState(false);

  // Turn Attack Countdown Timer (15 seconds per turn)
  const [turnTimeLeft, setTurnTimeLeft] = useState<number>(15);

  // Team Selection / Custom Squad (3 Pokémon)
  const [selectedSquad, setSelectedSquad] = useState<PokemonItem[]>(() => {
    if (typeof window !== "undefined") {
      try {
        const saved = localStorage.getItem("pokeempire_squad_ids");
        if (saved && roster.length > 0) {
          const ids: number[] = JSON.parse(saved);
          const matched = ids
            .map((id) => roster.find((r) => r.id === id))
            .filter(Boolean) as PokemonItem[];
          if (matched.length === 3) return matched;
        }
      } catch (e) {}
    }
    return roster.slice(0, 3);
  });

  // Modal to pick Pokémon for a specific slot (0, 1, or 2)
  const [editingSlot, setEditingSlot] = useState<number | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  // 1v1 Matchmaking state
  const [isMatchmaking, setIsMatchmaking] = useState(false);
  const [matchedRival, setMatchedRival] = useState<typeof RIVAL_TRAINERS[0] | null>(null);

  const logEndRef = useRef<HTMLDivElement>(null);

  // Auto-scroll combat log
  useEffect(() => {
    if (logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [battle?.combat_log]);

  // Turn timer countdown (15s per turn during battle)
  useEffect(() => {
    if (!battle || battle.status !== "IN_PROGRESS") return;

    setTurnTimeLeft(15);
    const interval = setInterval(() => {
      setTurnTimeLeft((prev) => {
        if (prev <= 1) {
          // Time expired! Auto attack with primary move
          clearInterval(interval);
          triggerTelegramHaptic("warning");
          handleMoveClick(0);
          return 0;
        }
        if (prev === 4) {
          triggerTelegramHaptic("warning");
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [battle?.turn, battle?.status]);

  // Save customized squad to localStorage
  const handleAssignToSlot = (slotIdx: number, mon: PokemonItem) => {
    triggerTelegramHaptic("medium");
    const updated = [...selectedSquad];

    // If already in another slot, swap them
    const existingIdx = updated.findIndex((item) => item.id === mon.id);
    if (existingIdx !== -1 && existingIdx !== slotIdx) {
      const temp = updated[slotIdx];
      updated[slotIdx] = mon;
      updated[existingIdx] = temp;
    } else {
      updated[slotIdx] = mon;
    }

    setSelectedSquad(updated);
    if (typeof window !== "undefined") {
      try {
        localStorage.setItem(
          "pokeempire_squad_ids",
          JSON.stringify(updated.map((m) => m.id))
        );
      } catch (e) {}
    }
    setEditingSlot(null);
  };

  // Start 1v1 Matchmaking with other trainers
  const handleStartMatchmaking = () => {
    if (selectedBet > (player?.coins ?? 0)) {
      triggerTelegramHaptic("error");
      return;
    }
    triggerTelegramHaptic("medium");
    setIsMatchmaking(true);
    setMatchedRival(null);

    // Simulate matchmaking radar search
    setTimeout(() => {
      const rival = RIVAL_TRAINERS[Math.floor(Math.random() * RIVAL_TRAINERS.length)];
      setMatchedRival(rival);
      triggerTelegramHaptic("success");

      // Auto-enter stadium after match reveal
      setTimeout(async () => {
        setIsMatchmaking(false);
        setMatchedRival(null);
        await onStartBattle(selectedBet, selectedSquad);
      }, 1300);
    }, 1000);
  };

  const handleMoveClick = async (idx: number) => {
    if (isActionLoading) return;
    triggerTelegramHaptic("heavy");
    setHitOpponent(true);
    setTimeout(() => setHitOpponent(false), 450);
    await onAttack(idx);
    setHitPlayer(true);
    setTimeout(() => setHitPlayer(false), 450);
  };

  // ==============================================================
  // VIEW A: ACTIVE TURN-BASED COMBAT ARENA
  // ==============================================================
  if (battle) {
    const activePlayerMon = battle.player_team[battle.player_active_idx];
    const activeOpponentMon = battle.opponent_team[battle.opponent_active_idx];
    const timerPercent = (turnTimeLeft / 15) * 100;

    return (
      <div className="space-y-3 pb-24 animate-fade-in">
        {/* Battle Top Bar & Turn Attack Timer */}
        <div className="bg-white dark:bg-[#141721] border border-slate-200 dark:border-white/[0.08] px-3.5 py-2.5 rounded-2xl flex items-center justify-between text-xs shadow-sm">
          <div className="flex items-center space-x-2">
            <span className="text-base">⚔️</span>
            <div>
              <span className="text-[10px] text-slate-400 uppercase tracking-wider block font-semibold">
                Rival Trainer
              </span>
              <span className="font-bold text-slate-900 dark:text-white">
                {battle.opponent_name}
              </span>
            </div>
          </div>

          {/* Turn Countdown Timer */}
          <div className="flex items-center space-x-2">
            <div className="flex items-center space-x-1.5 px-2.5 py-1 rounded-xl bg-slate-100 dark:bg-[#1a1e2b] border border-slate-200 dark:border-white/[0.08]">
              <Clock
                className={`w-3.5 h-3.5 ${
                  turnTimeLeft <= 4 ? "text-red-500 animate-pulse" : "text-amber-500"
                }`}
              />
              <span
                className={`font-mono font-bold text-xs ${
                  turnTimeLeft <= 4 ? "text-red-500 animate-pulse font-black" : "text-slate-800 dark:text-slate-200"
                }`}
              >
                {turnTimeLeft}s
              </span>
            </div>

            <button
              onClick={() => {
                triggerTelegramHaptic("error");
                onForfeit();
              }}
              disabled={battle.status !== "IN_PROGRESS"}
              className="text-[10px] bg-red-500/10 text-red-500 px-2.5 py-1 rounded-xl font-bold flex items-center space-x-1 hover:bg-red-500/20 disabled:opacity-40 active:scale-95 transition"
            >
              <Flag className="w-3 h-3" />
              <span>Surrender</span>
            </button>
          </div>
        </div>

        {/* Turn Timer Linear Progress Indicator */}
        {battle.status === "IN_PROGRESS" && (
          <div className="w-full h-1 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden">
            <div
              className={`h-full transition-all duration-1000 ease-linear ${
                turnTimeLeft <= 4 ? "bg-red-500" : turnTimeLeft <= 8 ? "bg-amber-500" : "bg-emerald-500"
              }`}
              style={{ width: `${timerPercent}%` }}
            />
          </div>
        )}

        {/* BATTLE STADIUM ARENA */}
        <div className="relative rounded-2xl p-4 overflow-hidden bg-white dark:bg-[#141721] border border-slate-200 dark:border-white/[0.08] shadow-sm min-h-[300px] flex flex-col justify-between">
          {/* 1. OPPONENT HUD & SPRITE */}
          <div className="flex items-start justify-between relative z-10">
            <div className="bg-slate-50 dark:bg-[#1a1e2b] border border-slate-200 dark:border-white/[0.08] px-3 py-2 rounded-xl max-w-[58%] w-full shadow-sm">
              <div className="flex items-center justify-between space-x-2">
                <span className="font-bold text-xs text-slate-900 dark:text-white truncate">
                  {activeOpponentMon.name}
                </span>
                <span className="text-[10px] font-mono font-bold text-violet-500">
                  Lv.{activeOpponentMon.level}
                </span>
              </div>
              <div className="mt-1 space-y-1">
                <div className="flex justify-between text-[9px] font-mono font-semibold text-slate-400">
                  <span>HP</span>
                  <span>{Math.max(0, activeOpponentMon.hp)}/{activeOpponentMon.max_hp}</span>
                </div>
                <div className="w-full h-1.5 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full transition-all duration-300 ${
                      activeOpponentMon.hp / activeOpponentMon.max_hp > 0.5
                        ? "bg-emerald-500"
                        : activeOpponentMon.hp / activeOpponentMon.max_hp > 0.2
                        ? "bg-amber-500"
                        : "bg-red-500"
                    }`}
                    style={{
                      width: `${Math.max(0, (activeOpponentMon.hp / activeOpponentMon.max_hp) * 100)}%`,
                    }}
                  />
                </div>
              </div>
            </div>

            <div className={`w-28 h-28 shrink-0 flex items-center justify-center transition-transform ${hitOpponent ? "animate-pulse scale-90 translate-x-1" : ""}`}>
              <img
                src={activeOpponentMon.image_url}
                alt={activeOpponentMon.name}
                className="w-full h-full object-contain filter drop-shadow-md"
              />
            </div>
          </div>

          {/* 2. PLAYER HUD & SPRITE */}
          <div className="flex items-end justify-between relative z-10 mt-4">
            <div className={`w-32 h-32 shrink-0 flex items-center justify-center transition-transform ${hitPlayer ? "animate-pulse scale-90 -translate-x-1" : ""}`}>
              <img
                src={activePlayerMon.image_url}
                alt={activePlayerMon.name}
                className="w-full h-full object-contain filter drop-shadow-md"
              />
            </div>

            <div className="bg-slate-50 dark:bg-[#1a1e2b] border border-slate-200 dark:border-white/[0.08] px-3 py-2 rounded-xl max-w-[58%] w-full shadow-sm">
              <div className="flex items-center justify-between space-x-2">
                <span className="font-bold text-xs text-slate-900 dark:text-white truncate">
                  {activePlayerMon.name}
                </span>
                <span className="text-[10px] font-mono font-bold text-violet-500">
                  Lv.{activePlayerMon.level}
                </span>
              </div>
              <div className="mt-1 space-y-1">
                <div className="flex justify-between text-[9px] font-mono font-semibold text-slate-400">
                  <span>HP</span>
                  <span>{Math.max(0, activePlayerMon.hp)}/{activePlayerMon.max_hp}</span>
                </div>
                <div className="w-full h-2 bg-slate-200 dark:bg-slate-700 rounded-full overflow-hidden">
                  <div
                    className={`h-full transition-all duration-300 ${
                      activePlayerMon.hp / activePlayerMon.max_hp > 0.5
                        ? "bg-emerald-500"
                        : activePlayerMon.hp / activePlayerMon.max_hp > 0.2
                        ? "bg-amber-500"
                        : "bg-red-500"
                    }`}
                    style={{
                      width: `${Math.max(0, (activePlayerMon.hp / activePlayerMon.max_hp) * 100)}%`,
                    }}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* COMBAT ACTIONS (4 MOVES) OR BATTLE RESULT */}
        {battle.status === "IN_PROGRESS" ? (
          <div className="space-y-2.5">
            <div className="grid grid-cols-2 gap-2">
              {(activePlayerMon.moves || []).map((move, idx) => {
                const typeStyle = TYPE_COLORS[move.type || "Normal"] || TYPE_COLORS.Normal;

                return (
                  <button
                    key={idx}
                    onClick={() => handleMoveClick(idx)}
                    disabled={isActionLoading || activePlayerMon.hp <= 0}
                    className="p-3 rounded-xl bg-white dark:bg-[#141721] border border-slate-200 dark:border-white/[0.08] flex flex-col justify-between hover:border-violet-500/50 active:scale-95 disabled:opacity-50 text-left transition-all shadow-sm group"
                  >
                    <div className="flex items-center justify-between w-full">
                      <span className="font-bold text-xs text-slate-900 dark:text-white truncate">
                        {move.name}
                      </span>
                      <span className={`text-[9px] font-bold uppercase px-1.5 py-0.2 rounded border ${typeStyle}`}>
                        {move.type || "Normal"}
                      </span>
                    </div>
                    <div className="mt-2 flex items-center justify-between text-[10px] font-mono text-slate-400">
                      <span>PWR {move.power}</span>
                      <span>ACC {Math.floor(move.accuracy * 100)}%</span>
                    </div>
                  </button>
                );
              })}
            </div>

            <div className="flex space-x-2">
              <button
                onClick={() => setShowSwitchModal(true)}
                className="flex-1 py-2.5 rounded-xl text-xs font-bold flex items-center justify-center space-x-1.5 bg-slate-100 dark:bg-[#1a1e2b] border border-slate-200 dark:border-white/[0.08] text-violet-600 dark:text-violet-400 active:scale-95 transition"
              >
                <ArrowRightLeft className="w-3.5 h-3.5" />
                <span>Switch Pokémon</span>
              </button>
            </div>
          </div>
        ) : (
          /* RESULT CARD */
          <div className="bg-white dark:bg-[#141721] border border-slate-200 dark:border-white/[0.08] rounded-2xl p-6 text-center space-y-3 shadow-md animate-fade-in">
            <div className="text-4xl">
              {battle.status === "VICTORY" ? "🏆" : "💥"}
            </div>
            <h3 className="text-lg font-bold text-slate-900 dark:text-white uppercase tracking-wider">
              {battle.status === "VICTORY" ? "Duel Victory!" : "Defeat in Duel"}
            </h3>
            <p className="text-xs text-slate-500 dark:text-slate-400">
              {battle.status === "VICTORY"
                ? `You defeated ${battle.opponent_name} and claimed the ${battle.bet > 0 ? `🪙 ${(battle.bet * 2).toLocaleString()} pot` : "victory"}!`
                : `${battle.opponent_name}'s Pokémon overcame your team.`}
            </p>
            <button
              onClick={() => {
                triggerTelegramHaptic("medium");
                onCloseBattle();
              }}
              className="btn-gold w-full py-2.5 rounded-xl text-xs font-bold uppercase tracking-wider"
            >
              Continue
            </button>
          </div>
        )}

        {/* COMBAT LOG */}
        <div className="bg-white dark:bg-[#141721] border border-slate-200 dark:border-white/[0.08] p-3 rounded-2xl space-y-1.5 max-h-32 overflow-y-auto text-xs font-mono shadow-sm">
          <span className="text-[10px] uppercase font-bold text-slate-400 block pb-1 border-b border-slate-100 dark:border-white/5">
            Battle Chronicle
          </span>
          {battle.combat_log.map((log, i) => (
            <div key={i} className="text-[11px] text-slate-600 dark:text-slate-300 leading-tight">
              {log}
            </div>
          ))}
          <div ref={logEndRef} />
        </div>

        {/* SWITCH MODAL */}
        {showSwitchModal && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fade-in">
            <div className="bg-white dark:bg-[#141721] border border-slate-200 dark:border-white/[0.08] w-full max-w-sm rounded-2xl p-4 space-y-3 shadow-2xl">
              <div className="flex justify-between items-center pb-2 border-b border-slate-100 dark:border-white/10">
                <h4 className="font-bold text-sm text-slate-900 dark:text-white">
                  Switch Active Pokémon
                </h4>
                <button
                  onClick={() => setShowSwitchModal(false)}
                  className="p-1 rounded-full text-slate-400 hover:text-white"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              <div className="space-y-2">
                {battle.player_team.map((mon, idx) => (
                  <button
                    key={`${mon.id}-${idx}`}
                    disabled={idx === battle.player_active_idx || mon.hp <= 0}
                    onClick={async () => {
                      triggerTelegramHaptic("medium");
                      setShowSwitchModal(false);
                      await onSwitch(idx);
                    }}
                    className="w-full p-2.5 rounded-xl flex items-center justify-between bg-slate-50 dark:bg-[#1a1e2b] border border-slate-200 dark:border-white/[0.08] disabled:opacity-40 active:scale-95 transition"
                  >
                    <div className="flex items-center space-x-2.5">
                      <img src={mon.image_url} alt={mon.name} className="w-10 h-10 object-contain" />
                      <div className="text-left">
                        <span className="font-bold text-xs text-slate-900 dark:text-white block">
                          {mon.name}
                        </span>
                        <span className="text-[10px] text-slate-400 font-mono">
                          HP {Math.max(0, mon.hp)}/{mon.max_hp}
                        </span>
                      </div>
                    </div>
                    {idx === battle.player_active_idx && (
                      <span className="text-[10px] font-bold text-violet-500">Active</span>
                    )}
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>
    );
  }

  // ==============================================================
  // VIEW B: 1v1 MATCHMAKING RADAR MODAL
  // ==============================================================
  if (isMatchmaking) {
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-fade-in">
        <div className="w-full max-w-sm rounded-2xl p-6 bg-[#141721] border border-white/[0.08] text-center space-y-5 shadow-2xl">
          <div className="relative w-24 h-24 mx-auto flex items-center justify-center">
            {/* Radar Pulse Ring */}
            <div className="absolute inset-0 rounded-full border-2 border-violet-500/30 animate-ping opacity-60" />
            <div className="w-20 h-20 rounded-full bg-violet-600/10 border border-violet-500/40 flex items-center justify-center text-3xl">
              ⚔️
            </div>
          </div>

          {!matchedRival ? (
            <div className="space-y-1.5">
              <h3 className="font-bold text-base text-white">
                Searching 1v1 Trainer...
              </h3>
              <p className="text-xs text-slate-400">
                Scanning active Telegram trainers for coin wager duel
              </p>
            </div>
          ) : (
            <div className="space-y-3 animate-fade-in">
              <span className="text-[10px] font-bold uppercase tracking-wider text-emerald-400 bg-emerald-500/10 px-2.5 py-0.5 rounded-full border border-emerald-500/20">
                Opponent Found!
              </span>
              <div className="flex items-center space-x-3 p-3 rounded-xl bg-white/5 border border-white/10 text-left">
                <img
                  src={matchedRival.avatar}
                  alt={matchedRival.name}
                  className="w-12 h-12 rounded-full border border-white/20 object-cover"
                />
                <div>
                  <h4 className="font-bold text-sm text-white">
                    {matchedRival.name}
                  </h4>
                  <p className="text-[11px] text-slate-400 font-mono">
                    Lv.{matchedRival.level} • {matchedRival.winRate} Win Rate
                  </p>
                  <span className="text-[9px] text-amber-400 font-semibold block mt-0.5">
                    🏅 {matchedRival.badge}
                  </span>
                </div>
              </div>
              <p className="text-xs text-violet-300 font-semibold animate-pulse">
                Entering 1v1 Arena...
              </p>
            </div>
          )}
        </div>
      </div>
    );
  }

  // ==============================================================
  // VIEW C: BATTLE STADIUM LOBBY (Team Builder & Wager Selector)
  // ==============================================================
  return (
    <div className="space-y-4 pb-32 animate-fade-in">
      {/* 1. ARENA HEADER BANNER */}
      <div className="bg-white dark:bg-[#141721] border border-slate-200 dark:border-white/[0.08] rounded-2xl p-4.5 shadow-sm">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-[10px] font-bold uppercase px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-600 dark:text-violet-400">
              1v1 PvP Stadium
            </span>
            <h2 className="text-lg font-bold text-slate-900 dark:text-white mt-1">
              Battle Arena
            </h2>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
              Choose your Pokémon squad, place wagers, and duel trainers!
            </p>
          </div>
          <div className="w-12 h-12 rounded-xl bg-violet-600/10 text-violet-600 dark:text-violet-400 flex items-center justify-center text-2xl shrink-0">
            ⚔️
          </div>
        </div>

        <div className="mt-3 pt-2.5 border-t border-slate-100 dark:border-white/5 flex items-center justify-between text-xs">
          <div className="flex items-center space-x-1.5">
            <span className="font-semibold text-slate-600 dark:text-slate-300">Record:</span>
            <span className="font-mono font-bold text-emerald-500">{player?.pvp_wins || 0}W</span>
            <span className="text-slate-400">/</span>
            <span className="font-mono font-bold text-red-500">{player?.pvp_losses || 0}L</span>
          </div>
          <div className="text-amber-500 font-semibold font-mono text-xs">
            Coins: {(player?.coins || 0).toLocaleString()} 🪙
          </div>
        </div>
      </div>

      {/* 2. COIN WAGER SELECTOR & START 1v1 DUEL */}
      <div className="bg-white dark:bg-[#141721] border border-slate-200 dark:border-white/[0.08] rounded-2xl p-4 space-y-3 shadow-sm">
        <div className="flex justify-between items-center">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
            Select Wager
          </span>
          <span className="text-[10px] font-semibold text-violet-500">Winner takes pot</span>
        </div>

        <div className="grid grid-cols-4 gap-2">
          {[
            { label: "Friendly", amount: 0 },
            { label: "500 🪙", amount: 500 },
            { label: "1,000 🪙", amount: 1000 },
            { label: "5,000 🪙", amount: 5000 },
          ].map((wager) => (
            <button
              key={wager.amount}
              onClick={() => {
                triggerTelegramHaptic("light");
                setSelectedBet(wager.amount);
              }}
              className={`p-2 rounded-xl text-center transition-all active:scale-95 ${
                selectedBet === wager.amount
                  ? "btn-violet shadow-sm"
                  : "bg-slate-100 dark:bg-[#1a1e2b] border border-slate-200 dark:border-white/[0.08] text-slate-700 dark:text-slate-300"
              }`}
            >
              <span className="font-bold text-xs block">{wager.label}</span>
              <span className="text-[9px] opacity-75 mt-0.5 block">
                {wager.amount === 0 ? "Free" : "Coin Bet"}
              </span>
            </button>
          ))}
        </div>

        <button
          onClick={handleStartMatchmaking}
          className="btn-violet w-full py-3 rounded-xl text-xs font-bold tracking-wider uppercase flex items-center justify-center space-x-2 active:scale-98 shadow-sm"
        >
          <Swords className="w-4 h-4" />
          <span>Find 1v1 Trainer Duel</span>
        </button>
      </div>

      {/* 3. YOUR CHOSEN 3-POKÉMON BATTLE SQUAD (TEAM BUILDER) */}
      <div className="space-y-2">
        <div className="flex justify-between items-center px-1">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
            Battle Squad (Choose 3 Pokémon)
          </span>
          <span className="text-[10px] font-semibold text-emerald-500">
            Tap slot to choose Pokémon
          </span>
        </div>

        <div className="space-y-2">
          {[0, 1, 2].map((slotIdx) => {
            const mon = selectedSquad[slotIdx];

            return (
              <div
                key={slotIdx}
                onClick={() => {
                  triggerTelegramHaptic("light");
                  setEditingSlot(slotIdx);
                }}
                className="bg-white dark:bg-[#141721] border border-slate-200 dark:border-white/[0.08] rounded-2xl p-3 flex items-center justify-between cursor-pointer hover:border-violet-500/50 active:scale-98 transition-all shadow-sm group"
              >
                {mon ? (
                  <>
                    <div className="flex items-center space-x-3">
                      <div className="w-12 h-12 rounded-xl bg-slate-100 dark:bg-white/5 flex items-center justify-center overflow-hidden shrink-0 border border-slate-200 dark:border-white/10">
                        <img
                          src={mon.image_url}
                          alt={mon.name}
                          className="w-full h-full object-contain filter drop-shadow-sm group-hover:scale-110 transition-transform"
                        />
                      </div>
                      <div>
                        <div className="flex items-center space-x-1.5">
                          <h4 className="font-bold text-xs text-slate-900 dark:text-white">
                            {mon.name}
                          </h4>
                          {mon.is_shiny && <span className="text-amber-400 text-xs">✨</span>}
                        </div>
                        <div className="flex items-center space-x-2 text-[10px] text-slate-400 mt-0.5 font-mono">
                          <span>Lv.{mon.level}</span>
                          <span>•</span>
                          <span className="text-emerald-500">HP {mon.hp}</span>
                          <span>•</span>
                          <span>ATK {mon.atk}</span>
                        </div>
                      </div>
                    </div>

                    <div className="text-right">
                      <span className="text-[10px] font-bold text-violet-500 group-hover:underline block">
                        Slot #{slotIdx + 1} {slotIdx === 0 ? "⚡ Starter" : ""}
                      </span>
                      <span className="text-[9px] text-slate-400 mt-0.5 block">
                        Tap to change
                      </span>
                    </div>
                  </>
                ) : (
                  <div className="py-2 w-full text-center text-xs text-slate-400 font-medium">
                    + Choose Pokémon for Slot #{slotIdx + 1}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* 4. CHOOSE POKÉMON MODAL (TEAM BUILDER ROSTER DRAWER) */}
      {editingSlot !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-fade-in">
          <div className="bg-white dark:bg-[#141721] border border-slate-200 dark:border-white/[0.08] w-full max-w-sm rounded-2xl p-4.5 space-y-3.5 shadow-2xl max-h-[85vh] flex flex-col">
            <div className="flex items-center justify-between pb-2 border-b border-slate-100 dark:border-white/10 shrink-0">
              <div>
                <h3 className="font-bold text-sm text-slate-900 dark:text-white">
                  Choose Pokémon for Slot #{editingSlot + 1}
                </h3>
                <p className="text-[11px] text-slate-500 dark:text-slate-400">
                  Select a Pokémon from your collection to join the battle squad
                </p>
              </div>
              <button
                onClick={() => setEditingSlot(null)}
                className="p-1 rounded-full text-slate-400 hover:text-white hover:bg-white/10"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Search Input */}
            <div className="flex items-center space-x-2 px-3 py-2 rounded-xl bg-slate-100 dark:bg-[#1a1e2b] border border-slate-200 dark:border-white/[0.08] shrink-0">
              <Search className="w-3.5 h-3.5 text-slate-400" />
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="Search by name..."
                className="w-full text-xs bg-transparent outline-none text-slate-900 dark:text-white placeholder:text-slate-500"
              />
            </div>

            {/* Roster Grid */}
            <div className="flex-1 overflow-y-auto space-y-2 pr-1">
              {roster
                .filter((mon) =>
                  mon.name.toLowerCase().includes(searchQuery.toLowerCase())
                )
                .map((mon) => {
                  const currentSlot = selectedSquad.findIndex((s) => s?.id === mon.id);
                  const isAssigned = currentSlot !== -1;

                  return (
                    <div
                      key={mon.id}
                      onClick={() => handleAssignToSlot(editingSlot, mon)}
                      className={`p-2.5 rounded-xl border flex items-center justify-between cursor-pointer transition-all active:scale-98 ${
                        currentSlot === editingSlot
                          ? "bg-violet-500/10 border-violet-500"
                          : "bg-slate-50 dark:bg-[#1a1e2b] border-slate-200 dark:border-white/[0.08] hover:border-slate-300 dark:hover:border-white/20"
                      }`}
                    >
                      <div className="flex items-center space-x-3">
                        <img
                          src={mon.image_url}
                          alt={mon.name}
                          className="w-10 h-10 object-contain"
                        />
                        <div>
                          <div className="flex items-center space-x-1.5">
                            <span className="font-bold text-xs text-slate-900 dark:text-white">
                              {mon.name}
                            </span>
                            {mon.is_shiny && <span className="text-amber-400 text-xs">✨</span>}
                          </div>
                          <div className="flex items-center space-x-2 text-[10px] text-slate-400 font-mono mt-0.5">
                            <span>Lv.{mon.level}</span>
                            <span>•</span>
                            <span className="text-emerald-500">HP {mon.hp}</span>
                            <span>•</span>
                            <span>ATK {mon.atk}</span>
                          </div>
                        </div>
                      </div>

                      <div className="text-right">
                        {isAssigned ? (
                          <span className="text-[10px] font-bold text-violet-500 px-2 py-0.5 rounded bg-violet-500/10 border border-violet-500/20">
                            Slot #{currentSlot + 1}
                          </span>
                        ) : (
                          <span className="text-[10px] font-bold text-slate-400 group-hover:text-white">
                            Select
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
