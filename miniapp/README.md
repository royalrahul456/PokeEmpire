# ⚡ POKEEMPIRE – Official Telegram Mini App (TMA)

POKEEMPIRE is a complete, production-ready Telegram Mini App designed to run directly inside Telegram on mobile and desktop, integrating directly with the PokeEmpire Telegram Bot and PostgreSQL/Supabase game backend.

---

## 🌟 Architecture & Features

### 1. Platform & Technology
- **Framework**: Next.js 16 (App Router) + React 19 + TypeScript + Tailwind CSS.
- **Backend**: Node.js REST API routes integrated directly with PostgreSQL / Supabase connection pooling.
- **Telegram SDK**: Official Telegram Web Apps SDK (`https://telegram.org/js/telegram-web-app.js`) with native `initData` HMAC-SHA256 verification, safe-area adaptation, and haptic feedback.

### 2. Brand Identity & Advanced Glassmorphism
- **Light Theme**:
  - Pure white background (`#f8f9ff` / `#ffffff`)
  - Frosted translucent glass cards with realistic `backdrop-filter: blur(20px)`
  - Lavender and royal violet accents (`#7c3aed`, `#8b5cf6`, `#ddd6fe`)
  - Subtle shadows and crisp dark typography
- **Dark Theme**:
  - Obsidian & charcoal black background (`#05040a` / `#0a0814`)
  - Dark translucent glass cards (`rgba(18, 14, 32, 0.75)`)
  - Electric violet accents (`#c084fc`, `#a855f7`) with glowing borders
  - Soft lavender highlights and ambient lighting
- **System Synchronization**: Automatically respects Telegram client `colorScheme` and `themeParams`, with live manual override toggle.

### 3. Five Primary Navigation Tabs
1. **🏠 HOME**:
   - Welcome greeting with Telegram avatar & trainer level.
   - Profile summary with XP progress bar, coins 🪙, and gems 💎.
   - Daily Mystery Claim with streak tracking (+350 Coins, +5 Gems).
   - Quick Action buttons (Arena, Squad, Guild, Podiums).
   - Featured Tournaments carousel (Indigo Championship, Ancient Guild Raids).
   - Recent activity live feed and announcement ticker.
2. **⚔️ BATTLE**:
   - **PvP Ranked Arena**: Matchmaking against real trainers from the database.
   - **Gym Leader Circuit**: 5 progressive Gym Leaders (Brock 🪨, Misty 💧, Lt. Surge ⚡, Giovanni 🌍, Champion Red 👑).
   - **Turn-Based Combat Arena**:
     - Stadium view with sprite animations, floating idle, and hit shake reactions.
     - Dynamic health bars (Green $\to$ Yellow $\to$ Red).
     - 4 typed moves per Pokémon with power, accuracy, and physical/special damage.
     - In-battle bench swapping and forfeit surrender.
     - Live combat log ticker.
     - Victory & Defeat outcome screens with Trophies, Coins, and XP gains.
3. **🛡️ GUILD**:
   - Full Guild Overview: Name, Tag, Level, Treasury balance (🪙), and member counts.
   - Leadership roles (`Leader`, `Co-Leader`, `Member`).
   - Members roster with levels, contribution, and join dates.
   - Create Guild modal with tag validation and 5,000 coins creation fee.
   - Public Guild Directory with live search and 1-tap join requests.
4. **🏆 LEADERBOARD**:
   - Top-3 Olympic-style Podium (🥇 Gold, 🥈 Silver, 🥉 Bronze) with custom medal crowns and avatar cards.
   - Filterable categories: **Trophies (PvP)**, **Battle Wins**, **Wealth (Coins)**, and **Top Guilds**.
   - Searchable player leaderboard with rank movement indicators (▲ / ▼ / —).
   - Pinned bottom bar displaying the authenticated player's personal rank and score.
5. **🎒 PROFILE**:
   - Trainer ID card with Telegram avatar, username, and `#TG_ID`.
   - Full Pokémon Collection Vault with rarity filters (Common, Rare, Epic, Legendary) and search.
   - Interactive Pokémon Stats Modal with HP, Attack, Defense, Speed, and learned moves.
   - Lifetime statistics (Total Catches, Daily Streak, Battle Record, VIP tier).
   - Milestone Achievements checklist.
   - Dual Theme Selector (Light, Dark, Telegram Sync).

---

## 🚀 Running the App Locally

The Mini App is currently running and accessible at:
- **Local URL**: [http://localhost:3000](http://localhost:3000)
- **Network URL**: [http://10.225.232.135:3000](http://10.225.232.135:3000)

To start manually at any time:
```powershell
cd miniapp
npm run dev
```

---

## 🤖 Configuring in Telegram Bot (@BotFather)

1. Open [@BotFather](https://t.me/BotFather) on Telegram and send `/mybots`.
2. Select `@pokeempirebot`.
3. Choose **Bot Settings** ➔ **Menu Button** ➔ **Configure menu button**.
4. Enter your deployed HTTPS URL (e.g. `https://your-domain.vercel.app`).
5. Set the button text to: `🎮 PokeEmpire App`.
6. *(Optional)* Send `/newapp` to create a direct short link (e.g. `t.me/pokeempirebot/app`).
