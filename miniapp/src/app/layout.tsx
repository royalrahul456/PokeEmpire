import type { Metadata, Viewport } from "next";
import Script from "next/script";
import "./globals.css";
import { ThemeProvider } from "@/lib/themeContext";

export const metadata: Metadata = {
  title: "POKEEMPIRE - Official Telegram Mini App",
  description: "POKEEMPIRE: Premium Pokémon gaming ecosystem with advanced turn-based PvP Arena, Guilds, and Leaderboards.",
  icons: {
    icon: "/logo.png",
    apple: "/logo.png",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  maximumScale: 1,
  userScalable: false,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" suppressHydrationWarning className="dark h-full">
      <head>
        <Script
          src="https://telegram.org/js/telegram-web-app.js"
          strategy="beforeInteractive"
        />
      </head>
      <body className="min-h-full flex flex-col justify-start items-center">
        <ThemeProvider>
          {children}
        </ThemeProvider>
      </body>
    </html>
  );
}
