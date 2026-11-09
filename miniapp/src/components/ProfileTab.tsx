"use client";

import React, { useState, useEffect } from "react";
import { PlayerProfile, PokemonItem } from "@/types";
import { triggerTelegramHaptic } from "@/lib/telegram";
import {
  Sparkles,
  ChevronRight,
  Crown,
  Gem,
  CheckCircle2,
  ExternalLink,
  CreditCard,
  Tag,
  Edit3,
  X,
  Flame,
  Coins
} from "lucide-react";

interface ProfileTabProps {
  player: PlayerProfile | null;
  roster: PokemonItem[];
  onRefreshPlayer: () => Promise<void>;
}

interface CustomArtItem {
  id: number;
  pokemonId: number;
  name: string;
  formName: string;
  formBadge: string;
  gemCost: number;
  imageUrl: string;
  boost: string;
  rarity: "Epic" | "Legendary" | "Mythical";
}

const PREMIUM_ART_ITEMS: CustomArtItem[] = [
  {
    id: 1,
    pokemonId: 6,
    name: "Charizard",
    formName: "AMV Special Art",
    formBadge: "🎬 AMV Form",
    gemCost: 150,
    imageUrl: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/6.png",
    boost: "+20% Special Fire ATK",
    rarity: "Epic",
  },
  {
    id: 2,
    pokemonId: 94,
    name: "Gengar",
    formName: "Dynamax Shadow",
    formBadge: "⚡ Dynamax (Dmax)",
    gemCost: 200,
    imageUrl: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/94.png",
    boost: "+25% Max HP in Arena",
    rarity: "Epic",
  },
  {
    id: 3,
    pokemonId: 9,
    name: "Blastoise",
    formName: "Gigantamax Artillery",
    formBadge: "💥 Gigantamax (Gmax)",
    gemCost: 250,
    imageUrl: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/9.png",
    boost: "+30% Hydro Shield DEF",
    rarity: "Legendary",
  },
  {
    id: 4,
    pokemonId: 448,
    name: "Lucario",
    formName: "Z-Move Aura Strike",
    formBadge: "🌀 Z-Move Strike",
    gemCost: 300,
    imageUrl: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/448.png",
    boost: "Guaranteed Critical Aura",
    rarity: "Legendary",
  },
  {
    id: 5,
    pokemonId: 150,
    name: "Mewtwo",
    formName: "Terastal Psystrike",
    formBadge: "🔮 Terastal Crystal",
    gemCost: 450,
    imageUrl: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/150.png",
    boost: "Dual Psychic/Electric Blast",
    rarity: "Mythical",
  },
  {
    id: 6,
    pokemonId: 384,
    name: "Shiny Rayquaza",
    formName: "Ascended Primal Art",
    formBadge: "👑 Mythic Shiny",
    gemCost: 500,
    imageUrl: "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/shiny/384.png",
    boost: "Delta Stream +35% All Stats",
    rarity: "Mythical",
  },
];

interface VipPlan {
  id: string;
  tier: string;
  badge: string;
  durationDays: number;
  inrPrice: number;
  isPopular?: boolean;
  perks: string[];
}

const VIP_PLANS: VipPlan[] = [
  {
    id: "weekly",
    tier: "Weekly VIP",
    badge: "🥉 7 Days Pass",
    durationDays: 7,
    inrPrice: 39,
    perks: [
      "Daily /vipclaim: Guaranteed Rare Alternate-Art Pokémon",
      "+2,500 Daily Coins & 2x Shiny Catch Boost",
      "VIP Crown Badge on profile & leaderboards",
    ],
  },
  {
    id: "monthly",
    tier: "Monthly VIP",
    badge: "🥈 30 Days Pass",
    durationDays: 30,
    inrPrice: 79,
    isPopular: true,
    perks: [
      "All Weekly privileges included",
      "Daily /vipdaily: 50-80 ⭐ PokeGems bundle",
      "Exclusive Violet Glow Profile Aura & Guild Boost",
      "7-Day Streak Milestones: +50 Bonus Gems",
    ],
  },
  {
    id: "bi_monthly",
    tier: "2 Months VIP",
    badge: "🥇 60 Days Pass",
    durationDays: 60,
    inrPrice: 129,
    perks: [
      "Full 60 Days VIP privileges",
      "Daily /vipclaim + /vipdaily rewards",
      "Guaranteed Epic Alternate-Art Form at activation",
      "Guild VIP Contributor Status",
    ],
  },
  {
    id: "quarterly",
    tier: "3 Months Elite",
    badge: "👑 90 Days Elite",
    durationDays: 90,
    inrPrice: 199,
    perks: [
      "Instant Mythical Terastal Alternate Art unlock",
      "150 Daily Gems & VIP priority catches",
      "Direct Developer / Support fast-track access",
      "Max Tier VIP Crown with Permanent Discord/TG role",
    ],
  },
];

const PRESET_TAGS = [
  "⚡ Pokémon Master",
  "👑 League Champion",
  "🌟 Elite Four Trainer",
  "🌿 Ace Trainer",
  "🐉 Dragon Tamer",
  "✨ Shiny Pokémon Hunter",
  "🥋 Gym Leader",
  "💥 Gigantamax Battler",
  "🧬 Terastal Specialist",
  "🌋 Legendary Catcher",
  "🔮 Psychic Master",
  "🎒 Rookie Trainer",
];

export const ProfileTab: React.FC<ProfileTabProps> = ({
  player,
  roster,
  onRefreshPlayer,
}) => {
  const [toastMessage, setToastMessage] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState<string | null>(null);
  const [successItem, setSuccessItem] = useState<{ title: string; subtitle: string } | null>(null);

  // Custom Pokémon Tag state (Default: Pokémon Master)
  const [userTag, setUserTag] = useState<string>("⚡ Pokémon Master");
  const [isTagModalOpen, setIsTagModalOpen] = useState(false);
  const [customTagInput, setCustomTagInput] = useState("");

  // Telegram profile photo detection
  const [telegramPhoto, setTelegramPhoto] = useState<string | null>(null);

  useEffect(() => {
    // Detect Telegram avatar
    if (typeof window !== "undefined") {
      const tg = (window as any).Telegram?.WebApp;
      const photo = tg?.initDataUnsafe?.user?.photo_url;
      if (photo) {
        setTelegramPhoto(photo);
      }
      // Load saved tag from localStorage if available (reset legacy hunter tags)
      const savedTag = localStorage.getItem("pokeempire_user_tag");
      if (savedTag && !savedTag.includes("Newbie") && !savedTag.includes("E-Rank") && !savedTag.includes("Swordsman")) {
        setUserTag(savedTag);
      } else {
        setUserTag("⚡ Pokémon Master");
        localStorage.setItem("pokeempire_user_tag", "⚡ Pokémon Master");
      }
    }
  }, []);

  const showToast = (msg: string) => {
    setToastMessage(msg);
    setTimeout(() => setToastMessage(null), 3200);
  };

  // Set / Save Tag
  const handleSaveTag = (tagToSave: string) => {
    const finalTag = tagToSave.trim();
    if (!finalTag) return;
    triggerTelegramHaptic("success");
    setUserTag(finalTag);
    if (typeof window !== "undefined") {
      localStorage.setItem("pokeempire_user_tag", finalTag);
    }
    setIsTagModalOpen(false);
    showToast(`✅ Trainer tag updated to: ${finalTag}`);
  };

  // Referral Invite
  const handleInvite = () => {
    triggerTelegramHaptic("medium");
    const refId = player?.id || 6593485710;
    const botUrl = `https://t.me/PokeEmpire_bot?start=ref_${refId}`;
    const shareText = `Join me in PokeEmpire! Build your team, catch rare Pokémon, and battle together! 🎮⚡`;
    const tgShareUrl = `https://t.me/share/url?url=${encodeURIComponent(botUrl)}&text=${encodeURIComponent(shareText)}`;

    if (navigator?.clipboard?.writeText) {
      navigator.clipboard.writeText(botUrl).catch(() => {});
    }

    if (typeof window !== "undefined" && (window as any).Telegram?.WebApp?.openTelegramLink) {
      (window as any).Telegram.WebApp.openTelegramLink(tgShareUrl);
    } else {
      window.open(tgShareUrl, "_blank");
    }

    showToast("📋 Referral link copied! Opening Telegram share...");
  };

  // Buy Pokemon Art directly with PokeGems
  const handleBuyArt = async (art: CustomArtItem) => {
    triggerTelegramHaptic("medium");
    const currentGems = player?.gems ?? 1000;
    if (currentGems < art.gemCost) {
      showToast(`⚠️ You need 💎 ${art.gemCost} PokeGems. Upgrade your VIP or earn gems!`);
      return;
    }

    setIsProcessing(`art-${art.id}`);
    try {
      const res = await fetch("/api/shop/buy-art", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          userId: player?.id || 6593485710,
          pokemonId: art.pokemonId,
          name: art.name,
          formIndex: art.id,
          gemCost: art.gemCost,
          rarity: art.rarity,
        }),
      });

      const data = await res.json();
      if (!res.ok || data.error) {
        showToast(`❌ ${data.error || "Purchase failed"}`);
      } else {
        triggerTelegramHaptic("success");
        setSuccessItem({
          title: `Unlocked ${art.name} (${art.formName})!`,
          subtitle: `Added to your collection with ${art.boost}. Remaining: 💎 ${data.remainingGems}`,
        });
        await onRefreshPlayer();
      }
    } catch {
      showToast("❌ Network error. Please try again.");
    } finally {
      setIsProcessing(null);
    }
  };

  // Direct VIP Purchase (Cash / INR / UPI / Telegram Stars only - NOT PokeGems)
  const handleBuyVip = (plan: VipPlan) => {
    triggerTelegramHaptic("heavy");
    const paymentMsg = `Hi! I want to activate ${plan.tier} (₹${plan.inrPrice}) for my PokeEmpire Trainer ID #${player?.id || 6593485710}.`;
    const tgUrl = `https://t.me/TheDarkKratosX?text=${encodeURIComponent(paymentMsg)}`;

    showToast(`💳 Opening payment for ${plan.tier} (₹${plan.inrPrice})...`);

    if (typeof window !== "undefined" && (window as any).Telegram?.WebApp?.openTelegramLink) {
      (window as any).Telegram.WebApp.openTelegramLink(tgUrl);
    } else {
      window.open(tgUrl, "_blank");
    }
  };

  // Profile data
  const displayName = player?.nickname || "R ꫝ፝֟፝ ʜ ᴜ ʟㅤ⸙";
  const displayUsername = player?.username ? `@${player.username}` : "@TheDarkKratosX";
  const userCoins = player?.coins ?? 1576597;
  const userPokemon = player?.pokemon_count || roster.length || 342;
  const userStreak = player?.current_streak ?? 0;
  const userGems = player?.gems ?? 523;

  // Active avatar (Telegram real photo first, then player avatar, then fallback)
  const avatarSrc = telegramPhoto || player?.avatar_url || "/profile-avatar.png";

  return (
    <div className="space-y-4 pb-32 animate-fade-in relative">
      {/* Toast Notification */}
      {toastMessage && (
        <div className="fixed top-5 left-1/2 -translate-x-1/2 z-50 w-11/12 max-w-sm px-4 py-3 rounded-2xl bg-slate-900/90 dark:bg-slate-800/95 shadow-2xl border border-white/10 text-center text-xs font-bold text-white animate-fade-in backdrop-blur-xl">
          {toastMessage}
        </div>
      )}

      {/* Celebratory Purchase Modal */}
      {successItem && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-fade-in">
          <div className="liquid-glass-accent w-full max-w-sm rounded-2xl p-6 text-center space-y-4 border border-amber-400/50 relative overflow-hidden shadow-2xl">
            <div className="w-16 h-16 mx-auto rounded-full bg-amber-400/20 text-amber-400 flex items-center justify-center shadow-lg">
              <Sparkles className="w-8 h-8" />
            </div>
            <div>
              <h3 className="font-bold text-lg text-slate-900 dark:text-white">
                {successItem.title}
              </h3>
              <p className="text-xs text-slate-600 dark:text-slate-300 mt-1 leading-relaxed">
                {successItem.subtitle}
              </p>
            </div>
            <button
              onClick={() => {
                triggerTelegramHaptic("light");
                setSuccessItem(null);
              }}
              className="btn-gold w-full py-3 rounded-xl text-xs font-black uppercase tracking-wider"
            >
              Claim & Continue
            </button>
          </div>
        </div>
      )}

      {/* ============================================================== */}
      {/* 🏷️ SET TAG MODAL                                              */}
      {/* ============================================================== */}
      {isTagModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-fade-in">
          <div className="liquid-glass-accent w-full max-w-sm rounded-2xl p-5 space-y-4 border border-white/10 relative shadow-2xl">
            <div className="flex items-center justify-between pb-2 border-b border-slate-200 dark:border-white/10">
              <div className="flex items-center space-x-2">
                <Tag className="w-4 h-4 text-violet-500" />
                <h3 className="font-bold text-sm text-slate-900 dark:text-white">
                  Set Pokémon Trainer Tag
                </h3>
              </div>
              <button
                onClick={() => setIsTagModalOpen(false)}
                className="p-1 rounded-full text-slate-400 hover:text-white hover:bg-white/10"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Custom Input */}
            <div className="space-y-1.5">
              <label className="text-[11px] font-semibold text-slate-400">
                Custom Pokémon Title
              </label>
              <div className="flex space-x-2">
                <input
                  type="text"
                  value={customTagInput}
                  onChange={(e) => setCustomTagInput(e.target.value)}
                  placeholder="e.g. ⚡ Kanto Champion"
                  maxLength={30}
                  className="flex-1 px-3.5 py-2 rounded-xl text-xs text-slate-900 dark:text-white bg-slate-100 dark:bg-[#1a1e2b] border border-slate-300 dark:border-white/10 outline-none placeholder:text-slate-500"
                />
                <button
                  onClick={() => handleSaveTag(customTagInput)}
                  disabled={!customTagInput.trim()}
                  className="btn-violet px-4 py-2 rounded-xl text-xs font-bold disabled:opacity-50"
                >
                  Save
                </button>
              </div>
            </div>

            {/* Preset Tags */}
            <div className="space-y-1.5 pt-1">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-400 block">
                Quick Select Tag
              </span>
              <div className="grid grid-cols-2 gap-2 max-h-48 overflow-y-auto pr-1">
                {PRESET_TAGS.map((t) => (
                  <button
                    key={t}
                    onClick={() => handleSaveTag(t)}
                    className="p-2 rounded-xl text-[11px] font-semibold text-slate-700 dark:text-slate-200 bg-slate-100/80 dark:bg-white/5 hover:border-violet-500 border border-transparent active:scale-95 text-left truncate transition-all"
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================== */}
      {/* 1. TOP TRAINER PROFILE (Clean Native Telegram Avatar & Tags)   */}
      {/* ============================================================== */}
      <div className="flex flex-col items-center pt-3 pb-1 space-y-2 relative animate-slide-up">
        {/* Telegram Profile Avatar with Clean Crisp Ring */}
        <div className="relative group cursor-pointer" onClick={() => triggerTelegramHaptic("light")}>
          <div className="w-24 h-24 rounded-full p-1 bg-slate-200 dark:bg-[#1a1e2b] border border-slate-300/60 dark:border-white/10 shadow-md flex items-center justify-center">
            <div className="w-full h-full rounded-full overflow-hidden bg-slate-900">
              <img
                src={avatarSrc}
                alt="Telegram Profile"
                className="w-full h-full object-cover"
                onError={(e) => {
                  (e.target as HTMLImageElement).src = "/profile-avatar.png";
                }}
              />
            </div>
          </div>

          {/* Green Live Online Dot */}
          <div className="absolute bottom-1 right-1 w-3.5 h-3.5 rounded-full bg-emerald-500 border-2 border-white dark:border-[#0c0e14] shadow-sm" />
        </div>

        {/* Name and Handle */}
        <div className="text-center space-y-0.5">
          <h2 className="text-lg font-bold tracking-tight text-slate-900 dark:text-white flex items-center justify-center space-x-1">
            <span>{displayName}</span>
          </h2>
          <p className="text-xs font-medium text-slate-500 dark:text-slate-400">
            {displayUsername}
          </p>
        </div>

        {/* Dynamic Pokémon Trainer Tags & Set Tag Action */}
        <div className="flex flex-col items-center space-y-1.5 pt-1">
          {/* Primary Customizable Tag */}
          <button
            onClick={() => {
              triggerTelegramHaptic("light");
              setCustomTagInput(userTag);
              setIsTagModalOpen(true);
            }}
            className="px-3.5 py-1 rounded-full flex items-center space-x-1.5 bg-slate-100 dark:bg-[#181c26] border border-slate-200 dark:border-white/10 shadow-sm hover:scale-105 active:scale-95 transition-all"
          >
            <span className="text-xs font-semibold text-slate-800 dark:text-slate-200">
              {userTag}
            </span>
            <span className="text-[10px] text-violet-500 font-semibold flex items-center space-x-0.5">
              <Edit3 className="w-2.5 h-2.5 inline" />
              <span>Edit</span>
            </span>
          </button>

          {/* Secondary Pokémon Sub-Tags */}
          <div className="flex items-center space-x-2">
            <button
              onClick={() => handleSaveTag("✨ Shiny Hunter")}
              className="px-3 py-0.5 rounded-full text-[11px] font-semibold text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-[#181c26] border border-slate-200 dark:border-white/10 active:scale-95 transition-all flex items-center space-x-1"
            >
              <span>✨</span>
              <span>Shiny Hunter</span>
            </button>
            <button
              onClick={() => handleSaveTag("⚔️ Pokémon Champion")}
              className="px-3 py-0.5 rounded-full text-[11px] font-semibold text-slate-600 dark:text-slate-300 bg-slate-100 dark:bg-[#181c26] border border-slate-200 dark:border-white/10 active:scale-95 transition-all flex items-center space-x-1"
            >
              <span>⚔️</span>
              <span>Pokémon Champion</span>
            </button>
          </div>
        </div>
      </div>

      {/* ============================================================== */}
      {/* 2. STATS GRID (Bank Removed, Pokémon Added, PokéGems & Coins)  */}
      {/* ============================================================== */}
      <div className="grid grid-cols-2 gap-3 pt-1">
        {/* Card 1: Coins */}
        <div className="bg-white dark:bg-[#141721] border border-slate-200 dark:border-white/[0.08] rounded-2xl p-4 flex flex-col justify-between shadow-sm active:scale-98 transition-transform cursor-default">
          <div className="text-2xl font-black tracking-tight text-slate-900 dark:text-white font-mono">
            {userCoins.toLocaleString()}
          </div>
          <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-500 dark:text-slate-400 mt-2">
            <span>🪙</span>
            <span>Coins</span>
          </div>
        </div>

        {/* Card 2: PokeGems (Replaces removed Bank) */}
        <div className="bg-white dark:bg-[#141721] border border-slate-200 dark:border-white/[0.08] rounded-2xl p-4 flex flex-col justify-between shadow-sm active:scale-98 transition-transform cursor-default">
          <div className="text-2xl font-black tracking-tight text-sky-500 dark:text-sky-400 font-mono">
            {userGems.toLocaleString()}
          </div>
          <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-500 dark:text-slate-400 mt-2">
            <span>💎</span>
            <span>PokéGems</span>
          </div>
        </div>

        {/* Card 3: Pokémon (Renamed from Characters) */}
        <div className="bg-white dark:bg-[#141721] border border-slate-200 dark:border-white/[0.08] rounded-2xl p-4 flex flex-col justify-between shadow-sm active:scale-98 transition-transform cursor-default">
          <div className="text-2xl font-black tracking-tight text-slate-900 dark:text-white font-mono">
            {userPokemon.toLocaleString()}
          </div>
          <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-500 dark:text-slate-400 mt-2">
            <span>🐾</span>
            <span>Pokémon</span>
          </div>
        </div>

        {/* Card 4: Day streak */}
        <div className="bg-white dark:bg-[#141721] border border-slate-200 dark:border-white/[0.08] rounded-2xl p-4 flex flex-col justify-between shadow-sm active:scale-98 transition-transform cursor-default">
          <div className="text-2xl font-black tracking-tight text-amber-500 dark:text-amber-400 font-mono">
            {userStreak}
          </div>
          <div className="flex items-center space-x-1.5 text-xs font-semibold text-slate-500 dark:text-slate-400 mt-2">
            <span>🔥</span>
            <span>Day streak</span>
          </div>
        </div>
      </div>

      {/* ============================================================== */}
      {/* 3. INVITE FRIENDS SECTION                                      */}
      {/* ============================================================== */}
      <div className="space-y-1.5 pt-1 animate-slide-up">
        <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500 px-1">
          INVITE
        </span>
        <div
          onClick={handleInvite}
          className="bg-white dark:bg-[#141721] border border-slate-200 dark:border-white/[0.08] rounded-2xl p-4 flex items-center justify-between cursor-pointer active:scale-98 transition-all shadow-sm group"
        >
          <div className="flex items-center space-x-3.5">
            <div className="w-10 h-10 rounded-xl bg-violet-100 dark:bg-violet-950/70 text-violet-600 dark:text-violet-300 flex items-center justify-center text-lg shrink-0">
              👥
            </div>
            <div>
              <h4 className="font-bold text-sm text-slate-900 dark:text-white">
                Invite friends
              </h4>
              <p className="text-[11px] text-slate-500 dark:text-slate-400 font-medium">
                Tap to share your link — +5,000 coins per friend
              </p>
            </div>
          </div>
          <ChevronRight className="w-5 h-5 text-slate-400 group-hover:translate-x-0.5 transition-transform" />
        </div>
      </div>

      {/* ============================================================== */}
      {/* 4. PREMIUM POKEGEMS ART STORE (Direct Pokémon Art with Gems)   */}
      {/* ============================================================== */}
      <div className="space-y-3 pt-3 animate-slide-up delay-350">
        <div className="flex items-center justify-between px-1">
          <div className="flex items-center space-x-2">
            <span className="p-1 rounded-lg bg-sky-500/15 text-sky-400 animate-pulse">
              <Gem className="w-4 h-4" />
            </span>
            <div>
              <h3 className="font-black text-xs uppercase tracking-wider text-slate-900 dark:text-white">
                Premium PokéGems Store
              </h3>
              <p className="text-[10px] text-slate-500 dark:text-slate-400">
                Directly buy rare alternate art & custom forms with PokéGems
              </p>
            </div>
          </div>

          {/* User Gems Badge */}
          <div className="liquid-glass-pill px-3 py-1 rounded-xl flex items-center space-x-1.5 border border-sky-400/30 hover:scale-105 transition-transform">
            <span className="text-xs animate-bounce">💎</span>
            <span className="font-mono font-black text-xs text-sky-500 dark:text-sky-300">
              {userGems.toLocaleString()}
            </span>
          </div>
        </div>

        {/* 2-Column Art Cards Grid */}
        <div className="grid grid-cols-2 gap-3">
          {PREMIUM_ART_ITEMS.map((item) => {
            const isBuying = isProcessing === `art-${item.id}`;
            return (
              <div
                key={item.id}
                data-glass="true"
                className="liquid-glass glass-sheen rounded-[24px] p-3.5 flex flex-col justify-between space-y-3 shadow-lg relative overflow-hidden group hover:-translate-y-1.5 hover:shadow-violet-500/20 hover:shadow-xl transition-all duration-300"
              >
                {/* Top Badge */}
                <div className="flex justify-between items-start">
                  <span
                    className="text-[9px] font-black uppercase px-2 py-0.5 rounded-full text-white shadow-sm border-t border-white/30 truncate max-w-[110px]"
                    style={{
                      background:
                        item.id === 1
                          ? "#ea580c"
                          : item.id === 2
                          ? "#7c3aed"
                          : item.id === 3
                          ? "#0284c7"
                          : item.id === 4
                          ? "#0ea5e9"
                          : item.id === 5
                          ? "#d946ef"
                          : "#10b981",
                    }}
                  >
                    {item.formBadge}
                  </span>
                  <span className="text-[9px] font-mono font-bold text-slate-400">
                    #{item.pokemonId}
                  </span>
                </div>

                {/* Pokemon Sprite with ambient glow and levitation */}
                <div className="w-24 h-24 mx-auto relative flex items-center justify-center my-1">
                  <div className="absolute inset-0 rounded-full bg-violet-500/15 blur-xl group-hover:bg-violet-500/30 animate-pulse transition-colors" />
                  <img
                    src={item.imageUrl}
                    alt={item.name}
                    className="w-full h-full object-contain filter drop-shadow-xl animate-float-shadow group-hover:scale-115 transition-transform duration-300 relative z-10"
                  />
                </div>

                {/* Details */}
                <div className="space-y-1">
                  <div className="flex items-center justify-between">
                    <h4 className="font-black text-xs text-slate-900 dark:text-white truncate">
                      {item.name}
                    </h4>
                    <span className="text-[9px] font-bold text-amber-500">
                      {item.rarity}
                    </span>
                  </div>
                  <p className="text-[10px] text-slate-500 dark:text-slate-400 line-clamp-1">
                    {item.boost}
                  </p>
                </div>

                {/* Direct Buy Button with PokeGems */}
                <button
                  onClick={() => handleBuyArt(item)}
                  disabled={isBuying}
                  className="btn-violet w-full py-2 rounded-xl text-xs font-black flex items-center justify-center space-x-1.5 shadow-md shadow-violet-500/25 active:scale-95 disabled:opacity-60 transition-transform"
                >
                  {isBuying ? (
                    <span className="animate-spin text-xs">⏳</span>
                  ) : (
                    <>
                      <span>💎</span>
                      <span>{item.gemCost}</span>
                      <span className="font-normal text-[10px] opacity-90">Buy Art</span>
                    </>
                  )}
                </button>
              </div>
            );
          })}
        </div>
      </div>

      {/* ============================================================== */}
      {/* 5. DIRECT VIP MEMBERSHIP (Real ₹ / INR / Stars - NOT GEMS)    */}
      {/* ============================================================== */}
      <div className="space-y-3 pt-3">
        <div className="flex items-center justify-between px-1">
          <div className="flex items-center space-x-2">
            <span className="p-1 rounded-lg bg-amber-500/15 text-amber-500">
              <Crown className="w-4 h-4" />
            </span>
            <div>
              <h3 className="font-black text-xs uppercase tracking-wider text-slate-900 dark:text-white">
                VIP Trainer Plans
              </h3>
              <p className="text-[10px] text-slate-500 dark:text-slate-400">
                Direct buy via UPI / Telegram Stars • Grants daily PokeGems & exclusive art
              </p>
            </div>
          </div>

          {player?.is_vip ? (
            <span className="text-[10px] font-black uppercase px-2.5 py-0.5 rounded-full bg-emerald-500/15 text-emerald-500 border border-emerald-500/30">
              🟢 Active
            </span>
          ) : (
            <span className="text-[9px] font-bold px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-500 border border-amber-500/20">
              Real Cash / Stars
            </span>
          )}
        </div>

        {/* VIP Plan Cards */}
        <div className="space-y-2.5">
          {VIP_PLANS.map((plan) => {
            return (
              <div
                key={plan.id}
                data-glass="true"
                className={`liquid-glass glass-sheen rounded-[24px] p-4 space-y-3 relative overflow-hidden hover:-translate-y-1 transition-all duration-300 ${
                  plan.isPopular ? "border-violet-500/60 shadow-violet-500/25 shadow-xl animate-pulse-border" : ""
                }`}
              >
                {plan.isPopular && (
                  <span className="absolute top-0 right-0 bg-gradient-to-l from-violet-600 via-fuchsia-600 to-pink-500 text-white font-black text-[9px] uppercase px-3 py-1 rounded-bl-xl shadow-md animate-shimmer">
                    🔥 Best Value
                  </span>
                )}

                <div className="flex items-center justify-between pr-14">
                  <div>
                    <h4 className="font-black text-sm text-slate-900 dark:text-white flex items-center space-x-1.5">
                      <span>{plan.tier}</span>
                      <span className="text-xs font-normal text-slate-500 dark:text-slate-400">
                        ({plan.badge})
                      </span>
                    </h4>
                    <div className="flex items-center space-x-2 text-xs font-mono mt-0.5">
                      <span className="font-black text-amber-500 text-base">₹{plan.inrPrice}</span>
                      <span className="text-[10px] text-slate-400 uppercase font-sans font-semibold">
                        Direct Activation
                      </span>
                    </div>
                  </div>
                </div>

                {/* Perks List */}
                <div className="space-y-1.5 pt-1">
                  {plan.perks.map((perk, i) => (
                    <div key={i} className="flex items-start space-x-2 text-[11px] text-slate-600 dark:text-slate-300">
                      <CheckCircle2 className="w-3.5 h-3.5 text-emerald-500 shrink-0 mt-0.5" />
                      <span>{perk}</span>
                    </div>
                  ))}
                </div>

                {/* Direct Action Button (Cash / UPI / Stars Only) */}
                <div className="pt-1">
                  <button
                    onClick={() => handleBuyVip(plan)}
                    className="btn-gold w-full py-2.5 rounded-xl text-xs font-black flex items-center justify-center space-x-2 shadow-md active:scale-95"
                  >
                    <CreditCard className="w-3.5 h-3.5 text-slate-900" />
                    <span>Purchase {plan.tier} — ₹{plan.inrPrice}</span>
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
