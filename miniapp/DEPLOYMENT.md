# 🚀 Hosting PokéEmpire Mini App

This guide explains how to host the PokéEmpire Telegram Mini App (`miniapp/`) directly from this repository with free SSL, high-performance edge caching, and Telegram WebApp integration.

---

## ⚡ Option 1: Vercel (Recommended — 1-Click Free Hosting)

Vercel is the creator and official home of Next.js, providing native support for App Router, dynamic serverless API routes, and edge networks.

### Steps:
1. Go to **[vercel.com](https://vercel.com)** and sign in with GitHub.
2. Click **"Add New..."** ➔ **"Project"**.
3. Import your repository: **`royalrahul456/PokeEmpire`**.
4. In the configuration screen:
   - **Framework Preset**: Next.js (auto-detected)
   - **Root Directory**: Click **Edit** and select **`miniapp`**.
5. **Environment Variables** (Optional — defaults are already configured in code):
   - `DATABASE_URL`: Your PostgreSQL / Supabase connection URL
   - `BOT_TOKEN`: Your Telegram Bot Token from `@BotFather`
6. Click **Deploy**.
7. In ~60 seconds, your Mini App is live with a production HTTPS domain (e.g. `https://pokeempire-miniapp.vercel.app`).

---

## 🌐 Option 2: Netlify (Free Hosting via `netlify.toml`)

This repository already includes `netlify.toml` pre-configured to build the Next.js app inside `miniapp/` using `@netlify/plugin-nextjs`.

### Steps:
1. Go to **[netlify.com](https://netlify.com)** and log in with GitHub.
2. Click **"Add new site"** ➔ **"Import an existing project"**.
3. Select **`royalrahul456/PokeEmpire`**.
4. Netlify will automatically detect settings from `netlify.toml`:
   - Base directory: `miniapp`
   - Build command: `npm run build`
   - Publish directory: `.next`
5. Click **"Deploy site"**.

---

## 🐳 Option 3: Docker / Render / Railway / Self-Hosted VPS

If you want to host on Render, Railway, or your own Linux VPS using PM2 or Docker:

### Manual Node.js / PM2:
```bash
cd miniapp
npm install
npm run build
npm run start
```
By default, the server listens on `http://0.0.0.0:3000` (or the port specified by the `PORT` environment variable).

---

## 📱 Linking the Mini App to Telegram Bot

Once your Mini App is deployed (for example `https://pokeempire-miniapp.vercel.app`):

### 1. Update the Bot Environment Variable
In your bot hosting settings (Render / VPS `.env` file):
```env
WEBAPP_URL=https://your-deployed-domain.vercel.app
```
Then restart the bot.

### 2. Configure Telegram Menu Button (@BotFather)
1. Open [@BotFather](https://t.me/BotFather) on Telegram and send `/mybots`.
2. Select your bot (e.g. `@pokeempirebot`).
3. Tap **Bot Settings** ➔ **Menu Button** ➔ **Configure menu button**.
4. Send your deployed HTTPS URL (e.g. `https://your-deployed-domain.vercel.app`).
5. Set button title: `⚡ PokéEmpire App`.

### 3. Create a Direct Link (`/newapp`)
1. In [@BotFather](https://t.me/BotFather), send `/newapp`.
2. Select your bot.
3. Enter App Title (e.g. `PokéEmpire`).
4. Enter Description and upload logo (or skip).
5. Enter your deployed HTTPS URL.
6. Choose a short name (e.g. `app`).
7. Your direct launch URL is ready: `https://t.me/your_bot_username/app`!
