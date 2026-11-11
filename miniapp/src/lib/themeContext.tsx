"use client";

import React, { createContext, useContext, useEffect, useState } from "react";
import { ThemeMode } from "@/types";
import { getTelegramWebApp } from "./telegram";

interface ThemeContextType {
  theme: ThemeMode;
  resolvedTheme: "light" | "dark";
  setTheme: (mode: ThemeMode) => void;
}

const ThemeContext = createContext<ThemeContextType>({
  theme: "system",
  resolvedTheme: "dark",
  setTheme: () => {},
});

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setThemeState] = useState<ThemeMode>("system");
  const [resolvedTheme, setResolvedTheme] = useState<"light" | "dark">("dark");

  const applyTheme = (mode: ThemeMode) => {
    let active: "light" | "dark" = "dark";

    if (mode === "system") {
      const tg = getTelegramWebApp();
      if (tg?.colorScheme) {
        active = tg.colorScheme === "light" ? "light" : "dark";
      } else if (typeof window !== "undefined") {
        const prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
        active = prefersDark ? "dark" : "light";
      }
    } else {
      active = mode;
    }

    setResolvedTheme(active);

    if (typeof document !== "undefined") {
      const root = document.documentElement;
      root.setAttribute("data-theme", active);
      if (active === "dark") {
        root.classList.add("dark");
        root.classList.remove("light");
      } else {
        root.classList.add("light");
        root.classList.remove("dark");
      }

      // Update Telegram header color if running inside Telegram
      const tg = getTelegramWebApp();
      if (tg?.setHeaderColor) {
        try {
          tg.setHeaderColor(active === "dark" ? "#06040c" : "#ffffff");
          tg.setBackgroundColor(active === "dark" ? "#05040a" : "#f8f9ff");
        } catch (e) {
          // ignore
        }
      }
    }
  };

  useEffect(() => {
    const saved = localStorage.getItem("pokeempire_theme") as ThemeMode | null;
    const initialMode = saved || "system";
    setThemeState(initialMode);
    applyTheme(initialMode);

    // Listen to Telegram theme change
    const tg = getTelegramWebApp();
    if (tg?.onEvent) {
      const handleThemeChange = () => {
        if (theme === "system") {
          applyTheme("system");
        }
      };
      tg.onEvent("themeChanged", handleThemeChange);
      return () => {
        tg.offEvent("themeChanged", handleThemeChange);
      };
    }
  }, []);

  const setTheme = (mode: ThemeMode) => {
    setThemeState(mode);
    localStorage.setItem("pokeempire_theme", mode);
    applyTheme(mode);
  };

  return (
    <ThemeContext.Provider value={{ theme, resolvedTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
