"use client";

import React, { useState, useEffect } from "react";
import { useTheme } from "@/lib/themeContext";

export const LoadingScreen: React.FC = () => {
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  const isDark = !mounted || resolvedTheme === "dark";

  return (
    <main
      className={`w-full max-w-md min-h-screen flex flex-col items-center justify-center space-y-6 px-6 select-none relative overflow-hidden transition-colors duration-200 ${
        isDark ? "bg-[#0c0e14] text-white" : "bg-[#f6f7fb] text-slate-900"
      }`}
    >
      {/* Hero Emblem & Smooth Pulsing Halo */}
      <div className="relative z-10 flex flex-col items-center space-y-5">
        <div className="relative">
          {/* Subtle clean halo */}
          <div className="absolute -inset-2 rounded-full bg-amber-400/15 blur-md animate-pulse" />

          {/* Logo container */}
          <div className="relative w-20 h-20 rounded-full p-1 bg-slate-200 dark:bg-[#1a1e2b] border border-slate-300/60 dark:border-white/10 shadow-xl flex items-center justify-center">
            <div className="w-full h-full rounded-full overflow-hidden bg-slate-900">
              <img
                src="/logo.png"
                alt="POKEEMPIRE"
                className="w-full h-full object-cover animate-poke-float"
                onError={(e) => {
                  (e.target as HTMLImageElement).src =
                    "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/384.png";
                }}
              />
            </div>
          </div>
        </div>

        {/* Clean Typography */}
        <div className="text-center space-y-1">
          <h1 className="font-extrabold text-xl tracking-[0.18em] text-slate-900 dark:text-white">
            POKEEMPIRE
          </h1>
          <p className="text-[11px] font-semibold text-slate-400 dark:text-slate-500">
            Connecting to Telegram WebApp...
          </p>
        </div>

        {/* Minimalist Spinner */}
        <div className="pt-1 flex items-center justify-center">
          <div className="w-5 h-5 rounded-full border-2 border-slate-300 dark:border-white/20 border-t-amber-500 animate-spin" />
        </div>
      </div>
    </main>
  );
};
