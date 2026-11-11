"use client";

import React, { useState, useEffect } from "react";
import { PlayerProfile, PokemonItem, PvpDuelSession, NavTab } from "@/types";
import { Navigation } from "@/components/Navigation";
import { HomeTab } from "@/components/HomeTab";
import { BattleTab } from "@/components/BattleTab";
import { GuildTab } from "@/components/GuildTab";
import { LeaderboardTab } from "@/components/LeaderboardTab";
import { ProfileTab } from "@/components/ProfileTab";
import { LoadingScreen } from "@/components/LoadingScreen";
import { LiquidGlassScene } from "@/components/LiquidGlass";
import { getTelegramWebApp, triggerTelegramHaptic } from "@/lib/telegram";
import { useTheme } from "@/lib/themeContext";
import { Sun, Moon, Palette } from "lucide-react";

export default function PokeEmpireMiniApp() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [activeTab, setActiveTab] = useState<NavTab>("home");
  const [player, setPlayer] = useState<PlayerProfile | null>(null);
  const [roster, setRoster] = useState<PokemonItem[]>([]);
  const [battle, setBattle] = useState<PvpDuelSession | null>(null);
  const [loading, setLoading] = useState(true);
  const [isClaiming, setIsClaiming] = useState(false);
  const [isBattleActionLoading, setIsBattleActionLoading] = useState(false);
  const [toastMessage, setToastMessage] = useState<string>("");
  const [telegramPhoto, setTelegramPhoto] = useState<string | null>(null);
  const [greeting, setGreeting] = useState<string>("Good Morning!");

  // Dynamic Greeting based on time of day
  useEffect(() => {
    const updateGreeting = () => {
      const hour = new Date().getHours();
      if (hour >= 5 && hour < 12) {
        setGreeting("Good Morning!");
      } else if (hour >= 12 && hour < 17) {
        setGreeting("Good Afternoon!");
      } else if (hour >= 17 && hour < 22) {
        setGreeting("Good Evening!");
      } else {
        setGreeting("Good Night!");
      }
    };
    updateGreeting();
    const interval = setInterval(updateGreeting, 60000);
    return () => clearInterval(interval);
  }, []);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(""), 3500);
  };

  // 1. Initial Authentication & Telegram WebApp Initialization
  useEffect(() => {
    const initApp = async () => {
      setLoading(true);
      const tg = getTelegramWebApp();

      let initData = "";
      if (tg) {
        try {
          tg.expand();
          tg.ready();
          tg.setHeaderColor(resolvedTheme === "dark" ? "#06030c" : "#f5f6ff");
          tg.setBackgroundColor(resolvedTheme === "dark" ? "#06030c" : "#f5f6ff");
          initData = tg.initData || "";
        } catch (e) {
          console.warn("Telegram SDK initialization note:", e);
        }
      }

      try {
        const tgUser = tg?.initDataUnsafe?.user;
        const tgPhoto = tgUser?.photo_url;
        if (tgPhoto) {
          setTelegramPhoto(tgPhoto);
        }

        const authRes = await fetch("/api/auth/verify", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            init_data: initData,
            mock_user_id: tgUser?.id || 6593485710,
            mock_username: tgUser?.username || "TheDarkKratosX",
            mock_nickname: tgUser?.first_name || "R ꫝ፝֟፝ ʜ ᴜ ʟㅤ⸙",
            photo_url: tgPhoto || null,
          }),
        });

        const authData = await authRes.json();
        if (authData.player) {
          if (tgPhoto) {
            authData.player.avatar_url = tgPhoto;
          }
          setPlayer(authData.player);
          await loadUserData(authData.player.id);
        }
      } catch (err) {
        console.error("Auth verify error:", err);
      } finally {
        setLoading(false);
      }
    };

    initApp();
  }, []);

  // 2. Telegram BackButton synchronization
  useEffect(() => {
    const tg = getTelegramWebApp();
    if (!tg?.BackButton) return;

    if (battle) {
      tg.BackButton.show();
      const handleBack = () => {
        setBattle(null);
      };
      tg.BackButton.onClick(handleBack);
      return () => {
        tg.BackButton.offClick(handleBack);
      };
    } else if (activeTab !== "home") {
      tg.BackButton.show();
      const handleBack = () => {
        setActiveTab("home");
      };
      tg.BackButton.onClick(handleBack);
      return () => {
        tg.BackButton.offClick(handleBack);
      };
    } else {
      tg.BackButton.hide();
    }
  }, [battle, activeTab]);

  // Load User Pokemon Roster
  const loadUserData = async (userId: number) => {
    try {
      const res = await fetch(`/api/pokemon?user_id=${userId}`);
      const data = await res.json();
      if (data.roster) setRoster(data.roster);
    } catch (e) {
      console.warn("Error loading user pokemon:", e);
    }
  };

  const refreshPlayer = async () => {
    if (!player) return;
    try {
      const res = await fetch(`/api/player?user_id=${player.id}`);
      const data = await res.json();
      if (data.player) setPlayer(data.player);
    } catch (e) {}
  };

  // Daily Claim
  const handleClaimDaily = async () => {
    if (!player || isClaiming) return;
    setIsClaiming(true);
    triggerTelegramHaptic("medium");

    try {
      const res = await fetch("/api/player/claim-daily", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: player.id }),
      });
      const data = await res.json();
      if (res.ok) {
        triggerTelegramHaptic("success");
        showToast(data.message || "Daily reward claimed!");
        setPlayer({
          ...player,
          coins: player.coins + (data.reward_coins || 350),
          can_claim_daily: false,
          current_streak: player.current_streak + 1,
        });
      }
    } catch (e) {
      triggerTelegramHaptic("error");
    } finally {
      setIsClaiming(false);
    }
  };

  // Start PvP Duel
  const handleStartBattle = async (bet: number, customTeam?: PokemonItem[]) => {
    if (!player) return;
    triggerTelegramHaptic("medium");

    const teamToSend = customTeam && customTeam.length > 0 ? customTeam : roster.slice(0, 3);
    if (teamToSend.length === 0) {
      showToast("⚠️ You need at least 1 Pokémon to battle!");
      return;
    }

    if (bet > player.coins) {
      showToast("⚠️ Insufficient coins for this wager!");
      return;
    }

    try {
      const res = await fetch("/api/battle/matchmake", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          user_id: player.id,
          bet,
          team: teamToSend,
        }),
      });

      const data = await res.json();
      if (res.ok && data.battle) {
        setBattle(data.battle);
      } else {
        showToast(data.error || "Could not start battle");
      }
    } catch (err: any) {
      showToast("Network error initiating duel");
    }
  };

  // Attack Action
  const handleAttack = async (moveIndex: number) => {
    if (!battle || battle.status !== "IN_PROGRESS" || isBattleActionLoading) return;
    setIsBattleActionLoading(true);

    try {
      const res = await fetch("/api/battle/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          battle_id: battle.battle_id,
          action_type: "attack",
          move_index: moveIndex,
        }),
      });

      const data = await res.json();
      if (res.ok && data.battle) {
        setBattle(data.battle);
        if (data.battle.status === "VICTORY") {
          triggerTelegramHaptic("success");
          if (player && data.battle.rewards) {
            setPlayer({
              ...player,
              coins: player.coins + data.battle.rewards.coins,
              xp: player.xp + data.battle.rewards.xp,
              pvp_wins: player.pvp_wins + 1,
            });
          }
        } else if (data.battle.status === "DEFEAT") {
          triggerTelegramHaptic("error");
          if (player) {
            setPlayer({
              ...player,
              coins: Math.max(0, player.coins - battle.bet),
              pvp_losses: player.pvp_losses + 1,
            });
          }
        }
      }
    } catch (e) {
      showToast("Error executing move");
    } finally {
      setIsBattleActionLoading(false);
    }
  };

  // Switch Action
  const handleSwitch = async (switchIndex: number) => {
    if (!battle || isBattleActionLoading) return;
    setIsBattleActionLoading(true);

    try {
      const res = await fetch("/api/battle/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          battle_id: battle.battle_id,
          action_type: "switch",
          switch_index: switchIndex,
        }),
      });

      const data = await res.json();
      if (res.ok && data.battle) {
        setBattle(data.battle);
      }
    } catch (e) {
      showToast("Could not switch Pokémon");
    } finally {
      setIsBattleActionLoading(false);
    }
  };

  // Forfeit Action
  const handleForfeit = async () => {
    if (!battle) return;
    try {
      const res = await fetch("/api/battle/action", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          battle_id: battle.battle_id,
          action_type: "forfeit",
        }),
      });

      const data = await res.json();
      if (res.ok && data.battle) {
        setBattle(data.battle);
        if (player && battle.bet > 0) {
          setPlayer({
            ...player,
            coins: Math.max(0, player.coins - battle.bet),
            pvp_losses: player.pvp_losses + 1,
          });
        }
      }
    } catch (e) {
      setBattle({ ...battle, status: "DEFEAT" });
    }
  };

  if (loading) {
    return <LoadingScreen />;
  }

  return (
    <LiquidGlassScene className="w-full max-w-md min-h-screen flex flex-col relative select-none shadow-2xl overflow-x-hidden">
      {/* ============================================================== */}
      {/* TOP USER PROFILE & GREETING HEADER BAR                         */}
      {/* ============================================================== */}
      <header
        className={`sticky top-0 z-40 px-4 pt-[max(env(safe-area-inset-top),12px)] pb-3 flex items-center justify-between transition-colors duration-200 ${
          resolvedTheme === "dark"
            ? "bg-[#10131a]/95 border-b border-white/[0.08] backdrop-blur-xl"
            : "bg-white/95 border-b border-slate-200/90 backdrop-blur-xl"
        }`}
      >
        {/* Left: Circular Avatar + Dynamic Time Greeting + Trainer Name */}
        <div
          onClick={() => {
            triggerTelegramHaptic("light");
            setActiveTab("profile");
          }}
          className="flex items-center space-x-3 cursor-pointer group active:scale-98 transition-transform"
        >
          {/* Circular Telegram Avatar with clean subtle border */}
          <div className="relative w-10 h-10 rounded-full shrink-0">
            <div className="w-full h-full rounded-full overflow-hidden bg-slate-800 border border-slate-300/40 dark:border-white/15 shadow-sm">
              <img
                src={telegramPhoto || player?.avatar_url || "/profile-avatar.png"}
                alt={player?.nickname || "Trainer"}
                className="w-full h-full object-cover"
                onError={(e) => {
                  (e.target as HTMLImageElement).src = "/profile-avatar.png";
                }}
              />
            </div>
            {/* Live Online Dot */}
            <span className="absolute bottom-0 right-0 w-2.5 h-2.5 rounded-full bg-emerald-500 border-2 border-white dark:border-[#10131a]" />
          </div>

          <div className="leading-tight">
            <div className="text-[11px] font-medium text-slate-500 dark:text-slate-400">
              {greeting}
            </div>
            <h2 className="text-sm font-bold text-slate-900 dark:text-white flex items-center space-x-1.5 mt-0.5">
              <span>{player?.nickname || "R ͥ ͣ ͫ H U L 🌲 📖"}</span>
              {player?.is_vip && (
                <span className="bg-amber-400 text-slate-950 font-black text-[8px] px-1 py-0.2 rounded shadow-sm">
                  VIP
                </span>
              )}
            </h2>
          </div>
        </div>

        {/* Right: Currency Balance & Theme Palette Button (Search removed per request) */}
        <div className="flex items-center space-x-2 relative z-10">
          {/* Quick Currency Pill */}
          <div
            onClick={() => {
              triggerTelegramHaptic("light");
              setActiveTab("home");
            }}
            className={`px-3 py-1 rounded-full flex items-center space-x-1.5 text-xs font-bold font-mono shadow-sm cursor-pointer active:scale-95 transition-all ${
              resolvedTheme === "dark"
                ? "bg-[#181c26] border border-white/[0.08] text-amber-400"
                : "bg-slate-100 border border-slate-200 text-amber-700"
            }`}
            title="Trainer Coins"
          >
            <span>🪙</span>
            <span>{(player?.coins ?? 1576597).toLocaleString()}</span>
          </div>

          {/* Circular Theme Palette Button */}
          <button
            onClick={() => {
              triggerTelegramHaptic("light");
              setTheme(resolvedTheme === "dark" ? "light" : "dark");
            }}
            className={`w-9 h-9 rounded-full flex items-center justify-center transition-all duration-200 active:scale-90 border shadow-sm ${
              resolvedTheme === "dark"
                ? "bg-[#181c26] border-white/[0.08] text-slate-300 hover:text-white hover:bg-[#202534]"
                : "bg-slate-100 border-slate-200 text-slate-700 hover:text-slate-900 hover:bg-slate-200"
            }`}
            title="Switch Theme"
          >
            <Palette className="w-4 h-4" />
          </button>
        </div>
      </header>

      {/* TOAST POPUP NOTIFICATION */}
      {toastMessage && (
        <div className="fixed top-16 left-1/2 -translate-x-1/2 z-50 liquid-glass-accent px-4 py-2 rounded-2xl text-xs font-bold text-slate-900 dark:text-white shadow-2xl border-t border-white/50 animate-in fade-in slide-in-from-top-2">
          {toastMessage}
        </div>
      )}

      {/* ============================================================== */}
      {/* PRIMARY TAB VIEWPORTS                                         */}
      {/* ============================================================== */}
      <div className="flex-1 p-3.5 relative z-10">
        {activeTab === "home" && (
          <HomeTab
            player={player}
            onNavigate={(tab) => {
              triggerTelegramHaptic("light");
              setActiveTab(tab);
            }}
            onClaimDaily={handleClaimDaily}
            isClaiming={isClaiming}
          />
        )}

        {activeTab === "battle" && (
          <BattleTab
            player={player}
            roster={roster}
            battle={battle}
            onStartBattle={handleStartBattle}
            onAttack={handleAttack}
            onSwitch={handleSwitch}
            onForfeit={handleForfeit}
            onCloseBattle={() => setBattle(null)}
            isActionLoading={isBattleActionLoading}
          />
        )}

        {activeTab === "guild" && (
          <GuildTab player={player} onRefreshPlayer={refreshPlayer} />
        )}

        {activeTab === "leaderboard" && (
          <LeaderboardTab player={player} />
        )}

        {activeTab === "profile" && (
          <ProfileTab player={player} roster={roster} onRefreshPlayer={refreshPlayer} />
        )}
      </div>

      {/* ============================================================== */}
      {/* FLOATING 5-TAB NAVIGATION DOCK (Apple VisionOS LiquidGlass)     */}
      {/* ============================================================== */}
      {!battle && (
        <Navigation
          activeTab={activeTab}
          onTabChange={(tab) => setActiveTab(tab)}
        />
      )}
    </LiquidGlassScene>
  );
}
