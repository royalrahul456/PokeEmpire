"use client";

import React from "react";

interface TelegramAnimatedEmojiProps {
  emoji?: string | null;
  emojiId?: string | null;
  size?: "xs" | "sm" | "md" | "lg" | "xl" | "2xl";
  className?: string;
  showGlow?: boolean;
}

// Preset Animated Flag Definitions matching utils/guild_flags.py
const PRESET_EMOJI_DATA: Record<
  string,
  {
    name: string;
    symbol: string;
    bgGradient: string;
    glowColor: string;
    animationClass: string;
  }
> = {
  strawhat: {
    name: "Straw Hat Pirates",
    symbol: "🏴‍☠️",
    bgGradient: "from-amber-600 via-red-600 to-black",
    glowColor: "rgba(239, 68, 68, 0.45)",
    animationClass: "animate-bounce",
  },
  dragon: {
    name: "Imperial Dragon",
    symbol: "🐉",
    bgGradient: "from-emerald-500 via-teal-700 to-slate-900",
    glowColor: "rgba(16, 185, 129, 0.5)",
    animationClass: "animate-pulse",
  },
  phoenix: {
    name: "Blazing Phoenix",
    symbol: "🔥",
    bgGradient: "from-orange-500 via-amber-600 to-red-700",
    glowColor: "rgba(245, 158, 11, 0.55)",
    animationClass: "animate-bounce",
  },
  crown: {
    name: "Royal Sovereign",
    symbol: "👑",
    bgGradient: "from-yellow-400 via-amber-500 to-yellow-600",
    glowColor: "rgba(234, 179, 8, 0.55)",
    animationClass: "animate-pulse",
  },
  lightning: {
    name: "Thunder Strike",
    symbol: "⚡",
    bgGradient: "from-amber-400 via-yellow-400 to-indigo-600",
    glowColor: "rgba(250, 204, 21, 0.6)",
    animationClass: "animate-ping-slow",
  },
  samurai: {
    name: "Cyber Samurai",
    symbol: "👹",
    bgGradient: "from-red-600 via-rose-700 to-slate-950",
    glowColor: "rgba(225, 29, 72, 0.5)",
    animationClass: "animate-pulse",
  },
  jedi_blue: {
    name: "Galactic Order",
    symbol: "💠",
    bgGradient: "from-cyan-400 via-blue-600 to-indigo-900",
    glowColor: "rgba(6, 182, 212, 0.55)",
    animationClass: "animate-spin-slow",
  },
  jedi_grey: {
    name: "Grey Guardian",
    symbol: "⚔️",
    bgGradient: "from-slate-400 via-slate-600 to-slate-900",
    glowColor: "rgba(148, 163, 184, 0.4)",
    animationClass: "animate-pulse",
  },
  wolf: {
    name: "Iron Wolf",
    symbol: "🐺",
    bgGradient: "from-slate-600 via-indigo-800 to-slate-950",
    glowColor: "rgba(99, 102, 241, 0.45)",
    animationClass: "animate-pulse",
  },
  shield: {
    name: "Golden Aegis",
    symbol: "🛡️",
    bgGradient: "from-amber-500 via-yellow-600 to-purple-800",
    glowColor: "rgba(217, 119, 6, 0.45)",
    animationClass: "animate-pulse",
  },
  skull: {
    name: "Shadow Skull",
    symbol: "💀",
    bgGradient: "from-purple-900 via-fuchsia-950 to-black",
    glowColor: "rgba(168, 85, 247, 0.5)",
    animationClass: "animate-pulse",
  },
  star: {
    name: "Celestial Star",
    symbol: "⭐",
    bgGradient: "from-amber-300 via-yellow-400 to-purple-600",
    glowColor: "rgba(251, 191, 36, 0.55)",
    animationClass: "animate-spin-slow",
  },
};

export const TelegramAnimatedEmoji: React.FC<TelegramAnimatedEmojiProps> = ({
  emoji = "shield",
  emojiId,
  size = "md",
  className = "",
  showGlow = true,
}) => {
  // Size mapping
  const sizeMap = {
    xs: { box: "w-5 h-5", text: "text-xs", rounded: "rounded-md" },
    sm: { box: "w-8 h-8", text: "text-base", rounded: "rounded-xl" },
    md: { box: "w-12 h-12", text: "text-2xl", rounded: "rounded-2xl" },
    lg: { box: "w-16 h-16", text: "text-3xl", rounded: "rounded-2xl" },
    xl: { box: "w-20 h-20", text: "text-4xl", rounded: "rounded-3xl" },
    "2xl": { box: "w-24 h-24", text: "text-5xl", rounded: "rounded-[32px]" },
  };

  const { box, text, rounded } = sizeMap[size];

  // Parse if emoji is raw tag `<tg-emoji emoji-id="12345">🛡️</tg-emoji>`
  let resolvedKey = (emoji || "shield").trim().toLowerCase();
  let parsedEmojiId = emojiId;
  let fallbackChar = "🛡️";

  if (emoji && emoji.includes("<tg-emoji")) {
    const m = emoji.match(/emoji-id="(\d+)"/);
    if (m) parsedEmojiId = m[1];
    const charMatch = emoji.match(/>([^<]+)<\/tg-emoji>/);
    if (charMatch) fallbackChar = charMatch[1];
  } else if (emoji && emoji.length > 2 && PRESET_EMOJI_DATA[resolvedKey]) {
    fallbackChar = PRESET_EMOJI_DATA[resolvedKey].symbol;
  } else if (emoji) {
    fallbackChar = emoji;
  }

  const preset = PRESET_EMOJI_DATA[resolvedKey];

  return (
    <div
      className={`relative inline-flex items-center justify-center shrink-0 ${box} ${className}`}
      style={{
        filter: showGlow
          ? `drop-shadow(0 0 14px ${preset?.glowColor || "rgba(147, 51, 234, 0.35)"})`
          : undefined,
      }}
    >
      {/* Outer Animated Liquid Glass Vessel */}
      <div
        className={`w-full h-full ${rounded} p-[1.5px] bg-gradient-to-tr ${
          preset?.bgGradient || "from-violet-600 via-purple-500 to-indigo-500"
        } shadow-lg relative overflow-hidden flex items-center justify-center`}
      >
        {/* Optical Specular Sheen Sweep */}
        <div className="absolute inset-0 bg-gradient-to-b from-white/35 via-transparent to-black/30 pointer-events-none" />

        {/* Ambient Fluid Glow Core */}
        <div className="w-full h-full bg-slate-950/75 backdrop-blur-md rounded-[inherit] flex items-center justify-center relative">
          <span
            className={`${text} select-none transform transition-transform duration-300 hover:scale-125 filter drop-shadow ${
              preset?.animationClass || "animate-pulse"
            }`}
          >
            {fallbackChar}
          </span>
        </div>
      </div>

      {/* Telegram Custom Emoji Verified Badge if user provided custom ID */}
      {parsedEmojiId && (
        <span
          title={`Telegram Custom Emoji ID: ${parsedEmojiId}`}
          className="absolute -top-1 -right-1 bg-sky-500 text-white text-[8px] font-black px-1 rounded-full shadow border border-white/60 animate-pulse"
        >
          TG
        </span>
      )}
    </div>
  );
};
