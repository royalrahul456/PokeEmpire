"use client";

import React, { useState, useEffect } from "react";
import { PlayerProfile, LeaderboardEntry } from "@/types";
import {
  Trophy,
  Coins,
  Shield,
  Search,
  Flame,
  PackageCheck,
  Crown
} from "lucide-react";
import { triggerTelegramHaptic } from "@/lib/telegram";

interface LeaderboardTabProps {
  player: PlayerProfile | null;
}

export const LeaderboardTab: React.FC<LeaderboardTabProps> = ({ player }) => {
  const [activeCategory, setActiveCategory] = useState<"coins" | "catches" | "streak" | "guilds">("coins");
  const [entries, setEntries] = useState<LeaderboardEntry[]>([]);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchLeaderboard(activeCategory);
  }, [activeCategory]);

  const fetchLeaderboard = async (cat: string) => {
    setLoading(true);
    try {
      const res = await fetch(`/api/leaderboard?type=${cat}`);
      const data = await res.json();
      if (data.entries) {
        setEntries(data.entries);
      }
    } catch (e) {
      console.warn("Error fetching leaderboard:", e);
    } finally {
      setLoading(false);
    }
  };

  const handleCategorySwitch = (cat: "coins" | "catches" | "streak" | "guilds") => {
    triggerTelegramHaptic("light");
    setActiveCategory(cat);
  };

  const filteredEntries = entries.filter(
    (e) =>
      e.username.toLowerCase().includes(searchQuery.toLowerCase()) ||
      e.nickname.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const top1 = entries[0];
  const top2 = entries[1];
  const top3 = entries[2];

  return (
    <div className="space-y-4 pb-32 animate-fade-in">
      {/* 1. CATEGORY SWITCHER (LiquidGlass Pill Bar) */}
      <div
        data-glass="true"
        data-config='{"blurAmount":0.3,"refraction":0.4,"cornerRadius":22}'
        className="liquid-glass p-1.5 rounded-2xl flex space-x-1 text-xs"
      >
        <button
          onClick={() => handleCategorySwitch("coins")}
          className={`flex-1 py-1.5 rounded-xl font-black transition-all active:scale-95 ${
            activeCategory === "coins"
              ? "btn-violet shadow-md shadow-violet-500/30"
              : "text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          🪙 Coins
        </button>

        <button
          onClick={() => handleCategorySwitch("catches")}
          className={`flex-1 py-1.5 rounded-xl font-black transition-all active:scale-95 ${
            activeCategory === "catches"
              ? "btn-violet shadow-md shadow-violet-500/30"
              : "text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          🎒 Catches
        </button>

        <button
          onClick={() => handleCategorySwitch("streak")}
          className={`flex-1 py-1.5 rounded-xl font-black transition-all active:scale-95 ${
            activeCategory === "streak"
              ? "btn-violet shadow-md shadow-violet-500/30"
              : "text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          🔥 Streak
        </button>

        <button
          onClick={() => handleCategorySwitch("guilds")}
          className={`flex-1 py-1.5 rounded-xl font-black transition-all active:scale-95 ${
            activeCategory === "guilds"
              ? "btn-violet shadow-md shadow-violet-500/30"
              : "text-slate-500 dark:text-slate-400 hover:text-slate-900 dark:hover:text-white"
          }`}
        >
          🏰 Guilds
        </button>
      </div>

      {/* 2. TOP THREE PODIUM DISPLAY (LiquidGlass Pedestals) */}
      {entries.length >= 3 && (
        <div className="pt-2 px-1">
          <div className="flex items-end justify-center gap-2.5">
            {/* Rank 2 (Silver) */}
            <div className="flex-1 flex flex-col items-center">
              <div className="relative mb-2">
                <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-slate-400 to-slate-200 p-0.5 shadow-lg shadow-slate-400/25 overflow-hidden border-t border-white/60">
                  <img
                    src={top2?.avatar_url || "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/trainers/2.png"}
                    alt="Silver"
                    className="w-full h-full object-cover"
                  />
                </div>
                <span className="absolute -top-2 -right-1 text-base filter drop-shadow">🥈</span>
              </div>
              <span className="font-black text-xs text-slate-900 dark:text-white truncate max-w-[80px]">
                {top2?.nickname || top2?.username}
              </span>
              <span className="text-[10px] font-mono font-bold text-slate-500 dark:text-slate-400">
                {top2?.score?.toLocaleString()} {top2?.sub_label}
              </span>
              <div className="w-full h-14 liquid-glass rounded-t-2xl mt-2 flex items-center justify-center font-black text-sm text-slate-500 dark:text-slate-300 border-t-2 border-slate-300/60 shadow-lg">
                2
              </div>
            </div>

            {/* Rank 1 (Gold) */}
            <div className="flex-1 flex flex-col items-center -mt-4">
              <div className="relative mb-2">
                <Crown className="w-5 h-5 text-amber-400 absolute -top-5 left-1/2 -translate-x-1/2 animate-bounce" />
                <div className="w-16 h-16 rounded-2xl bg-gradient-to-tr from-amber-500 via-yellow-400 to-amber-200 p-0.5 shadow-xl shadow-amber-500/35 overflow-hidden border-t border-white/80">
                  <img
                    src={top1?.avatar_url || "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/trainers/1.png"}
                    alt="Gold"
                    className="w-full h-full object-cover"
                  />
                </div>
                <span className="absolute -top-2 -right-1 text-lg filter drop-shadow">🥇</span>
              </div>
              <span className="font-black text-xs text-slate-900 dark:text-white truncate max-w-[90px]">
                {top1?.nickname || top1?.username}
              </span>
              <span className="text-[10px] font-mono font-bold text-amber-500">
                {top1?.score?.toLocaleString()} {top1?.sub_label}
              </span>
              <div className="w-full h-20 liquid-glass-accent rounded-t-2xl mt-2 flex items-center justify-center font-black text-base text-amber-500 border-t-2 border-amber-400 shadow-xl">
                1
              </div>
            </div>

            {/* Rank 3 (Bronze) */}
            <div className="flex-1 flex flex-col items-center">
              <div className="relative mb-2">
                <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-amber-700 to-amber-500 p-0.5 shadow-lg shadow-amber-700/25 overflow-hidden border-t border-white/50">
                  <img
                    src={top3?.avatar_url || "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/trainers/1.png"}
                    alt="Bronze"
                    className="w-full h-full object-cover"
                  />
                </div>
                <span className="absolute -top-2 -right-1 text-base filter drop-shadow">🥉</span>
              </div>
              <span className="font-black text-xs text-slate-900 dark:text-white truncate max-w-[80px]">
                {top3?.nickname || top3?.username}
              </span>
              <span className="text-[10px] font-mono font-bold text-slate-500 dark:text-slate-400">
                {top3?.score?.toLocaleString()} {top3?.sub_label}
              </span>
              <div className="w-full h-11 liquid-glass rounded-t-2xl mt-2 flex items-center justify-center font-black text-sm text-amber-700 dark:text-amber-500 border-t-2 border-amber-600/60 shadow-lg">
                3
              </div>
            </div>
          </div>
        </div>
      )}

      {/* 3. SEARCH BAR */}
      <div className="liquid-glass px-3.5 py-2.5 rounded-2xl flex items-center space-x-2">
        <Search className="w-4 h-4 text-slate-400 shrink-0" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search trainer username or guild tag..."
          className="bg-transparent text-xs text-slate-900 dark:text-white outline-none w-full placeholder:text-slate-400 font-medium"
        />
      </div>

      {/* 4. LEADERBOARD LIST */}
      <div className="space-y-2">
        {loading ? (
          <div className="py-8 text-center text-xs text-slate-400 font-bold">
            Loading bot rankings...
          </div>
        ) : filteredEntries.length === 0 ? (
          <div className="py-8 text-center text-xs text-slate-400 font-bold">
            No trainers found.
          </div>
        ) : (
          filteredEntries.map((entry) => {
            const isCurrentPlayer = entry.id === player?.id;

            return (
              <div
                key={entry.rank}
                data-glass="true"
                data-config='{"blurAmount":0.22,"refraction":0.3,"cornerRadius":20}'
                className={`liquid-glass rounded-2xl p-3 flex items-center justify-between transition-all hover:scale-[1.01] ${
                  isCurrentPlayer
                    ? "liquid-glass-accent border-t border-violet-400/80 shadow-lg shadow-violet-500/20"
                    : ""
                }`}
              >
                <div className="flex items-center space-x-3 relative z-10">
                  <span className="font-black font-mono text-xs text-slate-400 w-5 text-center">
                    {entry.rank}
                  </span>

                  <div className="w-10 h-10 rounded-xl bg-violet-500/10 overflow-hidden flex items-center justify-center shrink-0 border-t border-white/40">
                    <img
                      src={entry.avatar_url || "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/trainers/1.png"}
                      alt={entry.nickname}
                      className="w-full h-full object-cover"
                    />
                  </div>

                  <div>
                    <div className="flex items-center space-x-1.5">
                      <span className="font-black text-xs text-slate-900 dark:text-white">
                        {entry.nickname}
                      </span>
                      {isCurrentPlayer && (
                        <span className="text-[9px] font-black uppercase px-1.5 py-0.2 rounded bg-violet-500 text-white shadow-sm">
                          YOU
                        </span>
                      )}
                    </div>
                    <span className="text-[10px] text-slate-400 block font-mono">
                      Lv.{entry.level} • @{entry.username}
                    </span>
                  </div>
                </div>

                <div className="text-right relative z-10">
                  <span className="font-black font-mono text-xs text-amber-500 block">
                    {entry.score.toLocaleString()}
                  </span>
                  <span className="text-[9px] font-bold text-slate-400">
                    {entry.sub_label}
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
