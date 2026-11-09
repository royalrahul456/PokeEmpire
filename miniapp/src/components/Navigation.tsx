"use client";

import React from "react";
import { NavTab } from "@/types";
import { Home, Swords, Shield, Trophy, User } from "lucide-react";
import { triggerTelegramHaptic } from "@/lib/telegram";

interface NavigationProps {
  activeTab: NavTab;
  onTabChange: (tab: NavTab) => void;
}

export const Navigation: React.FC<NavigationProps> = ({ activeTab, onTabChange }) => {
  const tabs: { id: NavTab; label: string; icon: React.FC<{ className?: string }> }[] = [
    { id: "home", label: "Home", icon: Home },
    { id: "battle", label: "Battle", icon: Swords },
    { id: "guild", label: "Guild", icon: Shield },
    { id: "leaderboard", label: "Ranks", icon: Trophy },
    { id: "profile", label: "Profile", icon: User },
  ];

  const handleSelect = (tab: NavTab) => {
    triggerTelegramHaptic("light");
    onTabChange(tab);
  };

  return (
    <div className="fixed bottom-3 left-0 right-0 z-50 px-4 max-w-md mx-auto pointer-events-none">
      <nav
        className="pointer-events-auto rounded-2xl px-2 py-1.5 flex justify-around items-center bg-white/95 dark:bg-[#141721]/95 border border-slate-200 dark:border-white/[0.08] backdrop-blur-xl shadow-lg shadow-black/10 dark:shadow-black/50"
      >
        {tabs.map((tab) => {
          const isActive = activeTab === tab.id;
          const Icon = tab.icon;

          return (
            <button
              key={tab.id}
              onClick={() => handleSelect(tab.id)}
              className={`relative flex flex-col items-center justify-center py-1.5 px-3 rounded-xl transition-all duration-150 active:scale-95 ${
                isActive
                  ? "text-amber-500 font-bold"
                  : "text-slate-400 dark:text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
              }`}
            >
              <Icon
                className={`w-5 h-5 transition-transform duration-150 ${
                  isActive ? "scale-105" : ""
                }`}
              />
              <span className="text-[10px] mt-0.5 font-semibold tracking-tight">{tab.label}</span>
            </button>
          );
        })}
      </nav>
    </div>
  );
};
