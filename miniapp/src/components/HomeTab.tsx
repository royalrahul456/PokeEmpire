"use client";

import React, { useState } from "react";
import { PlayerProfile, NavTab } from "@/types";
import {
  Sparkles,
  Flame,
  Swords,
  Shield,
  Gift,
  Zap,
  ChevronRight,
  Clock,
  Bell,
  Star,
  PackageCheck,
  ShoppingBag
} from "lucide-react";
import { triggerTelegramHaptic } from "@/lib/telegram";
import { BOT_QUESTS, MYSTERY_BOXES } from "@/lib/battleEngine";

interface HomeTabProps {
  player: PlayerProfile | null;
  onNavigate: (tab: NavTab) => void;
  onClaimDaily: () => Promise<void>;
  isClaiming: boolean;
}

export const HomeTab: React.FC<HomeTabProps> = ({
  player,
  onNavigate,
  onClaimDaily,
  isClaiming,
}) => {
  const [announcementIdx, setAnnouncementIdx] = useState(0);

  const announcements = [
    "⚡ Daily Wild Pokémon Spawns active in all registered Telegram groups!",
    "🎁 Mystery Boxes now stocked with Legendary & Mythical Pokémon!",
    "🏰 Join or create a Guild to receive passive +5% Shiny Chance and +10% Coins!"
  ];

  return (
    <div className="space-y-4 pb-32 animate-fade-in">
      {/* 1. TRAINER PROFILE SUMMARY CARD (LiquidGlass Accent) */}
      <div
        data-glass="true"
        data-config='{"blurAmount":0.35,"refraction":0.55,"cornerRadius":28,"edgeHighlight":0.18,"specular":0.16}'
        className="liquid-glass-accent glass-sheen rounded-[28px] p-4.5 relative overflow-hidden animate-slide-up"
      >
        <div className="flex items-center justify-between relative z-10">
          <div className="flex items-center space-x-3.5">
            <div className="relative">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-tr from-violet-600 via-purple-500 to-lavender-400 p-0.5 shadow-xl shadow-violet-500/30 flex items-center justify-center overflow-hidden border-t border-white/60">
                <img
                  src={player?.avatar_url || "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/trainers/1.png"}
                  alt="Trainer"
                  className="w-full h-full object-cover"
                />
              </div>
              <span className="absolute -bottom-1 -right-1 bg-amber-400 text-slate-950 font-black text-[9px] px-1.5 py-0.2 rounded-full shadow border border-white/50">
                Lv.{player?.level || 1}
              </span>
            </div>

            <div>
              <div className="flex items-center space-x-1.5">
                <h2 className="font-black text-base tracking-tight text-slate-900 dark:text-white">
                  {player?.nickname || player?.username || "Trainer"}
                </h2>
                {player?.is_vip && (
                  <span className="bg-gradient-to-r from-amber-400 to-yellow-500 text-slate-950 text-[9px] font-black px-1.5 py-0.2 rounded tracking-wide shadow-sm">
                    VIP
                  </span>
                )}
              </div>
              <div className="flex items-center space-x-2 text-xs text-slate-500 dark:text-slate-400 mt-0.5 font-medium">
                {player?.guild_tag ? (
                  <span className="font-semibold text-violet-600 dark:text-violet-400">
                    [{player.guild_tag}] {player.guild_name}
                  </span>
                ) : (
                  <span className="text-slate-400">Independent Trainer</span>
                )}
                <span>•</span>
                <span className="font-mono text-slate-700 dark:text-slate-200">
                  {player?.pokemon_count || 0} Pokémon
                </span>
              </div>
            </div>
          </div>

          {/* Quick Balance Glass Pills */}
          <div className="text-right space-y-1.5">
            <div className="inline-flex items-center space-x-1.5 liquid-glass-pill px-2.5 py-1 rounded-xl text-xs font-bold text-amber-600 dark:text-amber-400">
              <span>🪙</span>
              <span>{player?.coins?.toLocaleString() || 0}</span>
            </div>
            <div>
              <div className="inline-flex items-center space-x-1.5 liquid-glass-pill px-2.5 py-1 rounded-xl text-xs font-bold text-sky-600 dark:text-sky-400">
                <span>💎</span>
                <span>{player?.gems || 0}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Level XP Progress Bar */}
        <div className="mt-4 pt-3 border-t border-violet-500/15 relative z-10">
          <div className="flex justify-between text-[10px] font-bold text-slate-500 dark:text-slate-400 mb-1">
            <span>Trainer Progress</span>
            <span className="font-mono text-violet-600 dark:text-violet-300">
              {player?.xp || 0} / {player?.next_level_xp || 100} XP
            </span>
          </div>
          <div className="w-full h-2 bg-slate-200/80 dark:bg-slate-950/80 rounded-full overflow-hidden border border-white/20 dark:border-white/5 shadow-inner">
            <div
              className="h-full bg-gradient-to-r from-violet-600 via-purple-500 to-indigo-400 rounded-full transition-all duration-500 shadow-sm"
              style={{
                width: `${Math.min(
                  100,
                  Math.max(8, (((player?.xp || 0) % 100) / 100) * 100)
                )}%`,
              }}
            />
          </div>
        </div>
      </div>

      {/* 2. ANNOUNCEMENT TICKER */}
      <div
        data-glass="true"
        data-config='{"blurAmount":0.25,"refraction":0.35,"cornerRadius":20}'
        className="liquid-glass rounded-2xl px-3.5 py-2.5 flex items-center space-x-2.5 text-xs text-slate-700 dark:text-slate-300"
      >
        <Bell className="w-4 h-4 text-violet-500 shrink-0 animate-pulse" />
        <p className="truncate flex-1 font-semibold">{announcements[announcementIdx]}</p>
        <button
          onClick={() => setAnnouncementIdx((prev) => (prev + 1) % announcements.length)}
          className="text-violet-600 dark:text-violet-400 hover:opacity-80 font-bold text-[10px] shrink-0"
        >
          Next
        </button>
      </div>

      {/* 3. DAILY REWARDS CLAIM CARD (/daily) */}
      <div
        data-glass="true"
        data-config='{"blurAmount":0.3,"refraction":0.45,"cornerRadius":28,"edgeHighlight":0.16}'
        className="liquid-glass glass-sheen rounded-[28px] p-4 flex items-center justify-between border-t border-amber-400/50 relative overflow-hidden animate-slide-up delay-150"
      >
        <div className="flex items-center space-x-3.5 relative z-10">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-amber-500 to-yellow-400 flex items-center justify-center text-2xl shadow-lg shadow-amber-500/25 border-t border-white/60 shrink-0">
            🎁
          </div>
          <div>
            <div className="flex items-center space-x-1.5">
              <h3 className="font-black text-sm text-slate-900 dark:text-white">Daily Coins Bonus</h3>
              <span className="flex items-center text-[10px] font-bold text-amber-500 dark:text-amber-400 bg-amber-500/10 px-1.5 py-0.2 rounded-md">
                <Flame className="w-3 h-3 mr-0.5 fill-amber-500" />
                {player?.current_streak || 1}d Streak
              </span>
            </div>
            <p className="text-[11px] text-slate-500 dark:text-slate-400 mt-0.5">
              Claim daily for +250 to +550 free Coins!
            </p>
          </div>
        </div>

        <div className="relative z-10 shrink-0">
          {player?.can_claim_daily ? (
            <button
              onClick={() => {
                triggerTelegramHaptic("medium");
                onClaimDaily();
              }}
              disabled={isClaiming}
              className="btn-gold px-4 py-2 rounded-xl text-xs font-black tracking-wider uppercase disabled:opacity-50"
            >
              {isClaiming ? "Claiming..." : "CLAIM"}
            </button>
          ) : (
            <div className="flex items-center space-x-1 text-[11px] font-bold text-slate-400 liquid-glass-pill px-3 py-1.5 rounded-xl">
              <Clock className="w-3.5 h-3.5" />
              <span>Claimed</span>
            </div>
          )}
        </div>
      </div>

      {/* 4. QUICK ACCESS GRID */}
      <div className="space-y-2">
        <div className="flex justify-between items-center px-1">
          <span className="text-xs font-black uppercase tracking-wider text-slate-400 dark:text-slate-500">
            Quick Actions
          </span>
        </div>

        <div className="grid grid-cols-4 gap-2">
          <button
            onClick={() => onNavigate("battle")}
            className="liquid-glass p-3 rounded-[22px] flex flex-col items-center justify-center hover:scale-[1.03] transition-all active:scale-95 group"
          >
            <div className="w-10 h-10 rounded-xl bg-violet-500/15 text-violet-500 flex items-center justify-center text-xl group-hover:scale-110 transition shadow-sm">
              ⚔️
            </div>
            <span className="text-[11px] font-bold mt-1.5 text-slate-800 dark:text-slate-200">PvP Battle</span>
            <span className="text-[9px] text-slate-400">Coin Duels</span>
          </button>

          <button
            onClick={() => onNavigate("profile")}
            className="liquid-glass p-3 rounded-[22px] flex flex-col items-center justify-center hover:scale-[1.03] transition-all active:scale-95 group"
          >
            <div className="w-10 h-10 rounded-xl bg-purple-500/15 text-purple-500 flex items-center justify-center text-xl group-hover:scale-110 transition shadow-sm">
              🎒
            </div>
            <span className="text-[11px] font-bold mt-1.5 text-slate-800 dark:text-slate-200">Collection</span>
            <span className="text-[9px] text-slate-400">Stats & IVs</span>
          </button>

          <button
            onClick={() => onNavigate("guild")}
            className="liquid-glass p-3 rounded-[22px] flex flex-col items-center justify-center hover:scale-[1.03] transition-all active:scale-95 group"
          >
            <div className="w-10 h-10 rounded-xl bg-indigo-500/15 text-indigo-500 flex items-center justify-center text-xl group-hover:scale-110 transition shadow-sm">
              🏰
            </div>
            <span className="text-[11px] font-bold mt-1.5 text-slate-800 dark:text-slate-200">Guild</span>
            <span className="text-[9px] text-slate-400">Treasury</span>
          </button>

          <button
            onClick={() => onNavigate("leaderboard")}
            className="liquid-glass p-3 rounded-[22px] flex flex-col items-center justify-center hover:scale-[1.03] transition-all active:scale-95 group"
          >
            <div className="w-10 h-10 rounded-xl bg-amber-500/15 text-amber-500 flex items-center justify-center text-xl group-hover:scale-110 transition shadow-sm">
              🏆
            </div>
            <span className="text-[11px] font-bold mt-1.5 text-slate-800 dark:text-slate-200">Ranks</span>
            <span className="text-[9px] text-slate-400">Standings</span>
          </button>
        </div>
      </div>

      {/* 5. ACTIVE BOT QUESTS (/quests) */}
      <div className="space-y-2">
        <div className="flex justify-between items-center px-1">
          <span className="text-xs font-black uppercase tracking-wider text-slate-400 dark:text-slate-500">
            Active Trainer Quests
          </span>
          <span className="text-[10px] text-violet-500 font-bold">Bot Sync</span>
        </div>

        <div className="space-y-2">
          {BOT_QUESTS.slice(0, 3).map((quest) => (
            <div
              key={quest.id}
              data-glass="true"
              data-config='{"blurAmount":0.22,"refraction":0.3,"cornerRadius":22}'
              className="liquid-glass rounded-[22px] p-3 flex items-center justify-between"
            >
              <div className="flex-1 pr-3 relative z-10">
                <div className="flex items-center space-x-1.5">
                  <span className="text-[9px] font-black uppercase px-1.5 py-0.5 rounded bg-violet-500/15 text-violet-600 dark:text-violet-300">
                    {quest.type}
                  </span>
                  <h4 className="font-bold text-xs text-slate-800 dark:text-slate-100">{quest.name}</h4>
                </div>
                <div className="mt-2 flex items-center space-x-2">
                  <div className="flex-1 h-1.5 bg-slate-200/80 dark:bg-slate-900 rounded-full overflow-hidden shadow-inner">
                    <div
                      className="h-full bg-violet-500 rounded-full shadow-sm"
                      style={{
                        width: `${Math.min(100, (quest.current_amount / quest.target_amount) * 100)}%`,
                      }}
                    />
                  </div>
                  <span className="text-[10px] font-mono font-bold text-slate-500 dark:text-slate-400">
                    {quest.current_amount}/{quest.target_amount}
                  </span>
                </div>
              </div>

              <div className="text-right shrink-0 relative z-10">
                <div className="text-[11px] font-black text-amber-500">+{quest.reward_coins} 🪙</div>
                <div className="text-[10px] font-mono text-violet-500">+{quest.reward_xp} XP</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 6. MYSTERY BOXES SHOP PREVIEW (/shop) */}
      <div className="space-y-2">
        <div className="flex justify-between items-center px-1">
          <span className="text-xs font-black uppercase tracking-wider text-slate-400 dark:text-slate-500">
            PokéEmpire Mystery Boxes
          </span>
          <span className="text-[10px] text-violet-500 font-bold">Shop Hub</span>
        </div>

        <div className="grid grid-cols-2 gap-2.5">
          {MYSTERY_BOXES.slice(0, 4).map((box) => (
            <div
              key={box.id}
              data-glass="true"
              data-config='{"blurAmount":0.25,"refraction":0.35,"cornerRadius":22}'
              className="liquid-glass rounded-[22px] p-3 flex flex-col justify-between hover:scale-[1.02] transition-all"
            >
              <div className="flex items-center space-x-2 relative z-10">
                <span className="text-2xl filter drop-shadow">{box.icon}</span>
                <div>
                  <h5 className="font-black text-xs text-slate-900 dark:text-white leading-tight">
                    {box.name}
                  </h5>
                  <span className="text-[10px] text-amber-500 font-bold font-mono">
                    🪙 {box.price.toLocaleString()}
                  </span>
                </div>
              </div>
              <p className="text-[10px] text-slate-500 dark:text-slate-400 mt-2 line-clamp-1 relative z-10">
                {box.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
