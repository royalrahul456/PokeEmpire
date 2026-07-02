# Walkthrough - PokeEmpire Updates & Fixes

This document summarizes the changes, additions, and layout refinements completed for the PokeEmpire bot.

## Accomplishments

### 1. Catch & Guess Reaction Updates
- **Emoji Guess Reactions**: Fixed the aiogram reaction parameter keyword typo (`reactions=` to `reaction=`) so that the bot now successfully reacts with `🎉` on correct guesses/catches.
- **Overhauled `/catch` victory flow**: After catching a wild spawn, the bot responds with three sequential messages:
  1. A quick coin victory alert: `🎉 +{coins_won} coins! Balance: {balance}` (upgraded reward to 80-130 coins, which is a +50 coin increase).
  2. A detailed catch HTML media card:
     ```html
     💥 🌟 <b>{nickname}</b> caught!
     
     <blockquote>⛔ <b>NAME:</b> {pokemon_name}
     🎦 <b>ANIME:</b> Gen {generation}
     {r_emoji} <b>RARITY:</b> {r_emoji} {rarity}
     ⏱️ <b>TIME:</b> {seconds}s</blockquote>
     ```
     - Attached inline button `📖 View Pokedex` pointing to the user's Pokedex checklist.
  3. A separate streak milestone alert: `🔥🔥🔥🔥f {streak}-Day Streak! Keep going! 🎯`

### 2. Gameplay Rewards (+50 Coins)
- Upgraded the coin rewards across all bot features:
  - **Daily Reward**: 250 - 550 coins (was 200 - 500)
  - **Catch Reward**: 80 - 130 coins (was 30 - 80)
  - **Lucky Spin**: all options shifted by +50 (new: `[100, 150, 200, 250, 350, 550]`)
  - **Trivia**: 150 coins (was 100)
  - **Scribble (Word Scramble)**: 150 coins standard (was 100) / 60-100 auto (was 10, 50)
  - **Nameguess (Guess the Pokémon)**: 200 coins standard (was 150) / 150-250 auto (was 100-200)

### 3. Daily Pokémon Claim (`/claim`)
- Added `/claim` command to let users claim one free random Pokémon every 24 hours.
- Implemented a local JSON-based cooldown tracker in `utils/claim.py` (avoiding database schema migrations).
- Restricts claims on a 24-hour cooldown, displaying time remaining inside a blockquote card on cooldown.
- Includes a 1% shiny roll check and random IV rolling.

### 4. Membership Verification System
- Created `utils/membership.py` implementing `check_membership` and `MembershipMiddleware`.
- Users must join the official group `@pokeempireunion` and updates channel `@pokeempireupdates` to interact with the bot in DMs or run commands in groups.
- Unverified users are intercepted dynamically and showed a custom "Verify Membership" menu with join links and a refresh/verify button.

### 5. Anti-Spam & Banned Words Improvements
- **Sticker & Spam Message Deletions**: In `GroupActivityMiddleware`, if a user exceeds the anti-flood limit (sending more than 5 messages/stickers in 3 seconds), their spam messages and stickers are deleted immediately, the 20,000 coins fine is transferred, and processing halts.
- **Group Warnings & Tagging**: Violators are tagged in the group chat and warned: `you are fined X coins for your behaviour`.
- **Fines Transfer**: Charged fines are:
  - **Bad Word Fine**: 50,000 coins (50k)
  - **Anti-Spam Fine**: 20,000 coins (20k)
- **Creator DM Warnings**: Restored private DM notifications to the bot creator showing who got fined for bad words or spam.
- **Removed Proxy Network Overheads**: Removed the `TELEGRAM_PROXY` configuration from `.env` to connect directly to the Telegram API, fixing latency and reducing ping times.

### 6. Visual Overhaul & Bot Leaderboard Exclusions
- Converted all outcomes and results to use HTML blockquotes `<blockquote>...</blockquote>` for clean colored left-borders.
- Refined `/daily`, `/spin`, `/coinflip`, `/rps`, `/redeem` claims, and unboxing result cards to use the blockquote structure.
- Refined shop unboxing shiny rate to **5%** (from 1%) in `handlers/shop.py`.
- **Mystery Box Price Increases**: Increased the price of all Mystery Boxes in the shop by 5k, displaying purely in `k` notation:
  - **Common Box**: 5,000 coins (5k)
  - **Rare Box**: 6,000 coins (6k)
  - **Epic Box**: 7,000 coins (7k)
  - **Legendary Box**: 9,000 coins (9k)
  - **Mythical Box**: 13,000 coins (13k)
- **Leaderboard Formatting Fix**: Fixed leaderboard layout issues by changing the leaderboard bot commands and queries to send HTML and wrapping rankings within a `<blockquote>` element.
- **Excluding Bot on Leaderboards**: Configured leaderboard queries to exclude the bot's own user ID (parsed from the token) from Coins, Pokémon catches, and Daily Streak leaderboards.
- **Direct Media Update Formatting**: Modified the direct `/setpokemedia` uploader console response to use the clean blockquote card styling.

### 7. Database & Latency Optimizations
- Configured PostgreSQL async engine connection pool settings (`pool_size=20`, `max_overflow=30`, `pool_recycle=1800`) to address high ping and late replies.
- Implemented in-memory caching of group spawn thresholds and active message counters in `utils/group_monitor.py` to prevent heavy database write traffic on every user message.
- Updated settings commands (`/setspawn`, `/toggle_spawns`, `/spawnsetting`) to sync directly with the cache.

### 8. Spawn Rules & Rarity Spawns
- **Restrict Spawn Command**: Configured `/spawn` manual wild spawns to be runnable exclusively by bot owners/admins (`config.ADMIN_IDS`), blocking general group chat admins.
- **Manual Spawn Rarity Argument**: Updated `/spawn` to parse an optional rarity argument (e.g. `/spawn legendary`, `/spawn epic`), allowing bot owners to manually spawn a random Pokémon from that specific rarity tier.
- **Disable Legendary-Only Overrides**: Completely removed the group chat `legendary_only_groups` settings and spawn override checks, ensuring regular group spawns roll normal weights.

### 9. Trivia Expiry & Case-Insensitive Game Checks
- **HTML Character Escaping**: Wrapped trivia questions and answers with `html.escape` inside `initiate_trivia_game`, `trivia_timeout_task`, and `cb_trivia_answer` to prevent parser crashes on special characters.
- **Log Timeout Failures**: Configured `trivia_timeout_task` to print error details on exception instead of failing silently.
- **Case-Insensitive Group Username Checks**: Updated all checks on `message.chat.username` and `chat.username` to be case-insensitive (converting to lowercase and comparing with `"pokeempireunion"`), resolving the issue where automatic and manual scribble/nameguess games failed to start if the official group had capitalized letters (e.g. `@PokeEmpireUnion`).
- **Formatted Fine Warnings in k notation**: Updated group warnings and DM confirmation messages for bad words and spam to show `50k` and `20k` fine amounts instead of full numbers, in accordance with the `k` notation requirement.

### 10. Premium Custom Emojis
- **Automatic Interception**: Implemented dynamic session interception via `bot.session.make_request` to rewrite outgoing message texts and captions, replacing 50+ standard emojis with premium custom Telegram emojis (`<tg-emoji>`).
- **Markdown-to-HTML Translation**: If a message containing custom emojis is formatted in Markdown, the interceptor automatically translates the markdown to HTML formatting and shifts the `parse_mode` to `HTML` to ensure custom emojis render correctly.
- **Context-Aware Mapping**:
  - `🟢` (Green Circle): mapped contextually to Rarity (`5416081784641168838`) or Statuses (`5215522595922779944`).
  - `🔮` (Crystal Ball): mapped contextually to Terastal Form (`5244955049024581265`) or Epic Rarity (`5271810272640643747`).
- **Buttons Compatibility**: Strictly targets text and caption fields to ensure inline keyboard/reply buttons are not broken, as Telegram button texts do not support HTML parse mode.

### 11. Custom Rarities, Database Channel & Spawn Abuse Fixes
- **Dynamic Rarity System (`/addrarity`)**: Added `/addrarity <RarityName> <Emoji>` command allowing Bot Owners to configure new custom rarity tiers dynamically. Custom rarities are stored inside database `GlobalSetting` and updated instantly in the memory cache. All active uploaders are notified in private DM upon creation.
- **Dynamic Rarity Emoji Resolving**: Updated `get_rarity_emoji` formatting function to dynamically load and resolve custom rarity emojis on the fly.
- **New Pokémon Registration (`/addpokemon`)**: Added `/addpokemon <id> <name> <rarity> <generation> <image_url> [video_url]` to register a new Pokémon directly in the database. Successful registrations automatically post a styled announcement to the database channel.
- **Database Channel Synchronization (`/syncdatabase`)**: Added `/syncdatabase` (alias `/syncdb`) command to synchronize all existing/old database Pokémon entries and custom form media files to `@pokeempiredatabase` with rate-limiting controls.
- **Database Channel & Live Directory Chart (`@pokeempiredatabase`)**:
  - Automatically posts announcements to the database channel when custom media (Art/AMV/etc.) is uploaded via `/setpokemedia` or the callback console.
  - Automatically compiles and updates a pinned dynamic summary chart (Directory list) of all configured Pokémon and forms, chunking into multiple messages if the text exceeds 4,000 characters.
- **Manual Spawn Restrictions (`/spawn`)**: Restricted manual spawn rarity selection (e.g. `/spawn Legendary`) strictly to Bot Owners/Admins (`config.ADMIN_IDS`). General group chat administrators can trigger standard random spawns but are blocked from choosing specific rarities to prevent exploit abuse.
- **Panel UI Fix**: Imported the missing `InlineKeyboardButton` class inside `handlers/admin.py` to resolve the `NameError` causing the `/panel` button callbacks and commands to fail silently.

### 12. Pokémon Auction House (AUC)
- **Active Auction System (`/auction`)**: Added `/auction <serial_number> <starting_price> <duration_hours>` allowing trainers to put their caught Pokémon up for auction. The Pokémon is temporarily removed from their inventory during the auction.
- **Auto-Pin & Unpin**: When an auction starts in a group chat, the bot automatically pins the auction message. Once the auction ends (completed, cancelled, or expired), the bot automatically unpins it.
- **Interactive Bidding Buttons**: Added inline buttons directly on the active auction message card: `[ +1,000 ]`, `[ +5,000 ]`, `[ +10,000 ]`, and `[ 💬 Custom Bid ]`. Bidding refunds the previous highest bidder and locks the new leader's coins instantly.
- **Real-Time Card Updates**: Bidding edits the active auction message in-place to update the current bid, the leader's name, and lists a dynamic `Recent Bids:` history block with timestamps.
- **Background Settlement Task**: Started an asynchronous worker task that checks for expired auctions every 30 seconds:
  - **With Bids (Sold)**: Delivers the Pokémon to the winner, pays the seller (minus a 5% tax), removes bidding buttons, edits the caption to `🔮 AUCTION ENDED!`, and posts a beautifully styled **Auction Won!** announcement card.
  - **No Bids (Unsold)**: Returns the Pokémon to the seller, removes buttons, edits the caption to `🪙 Auction Ended — No Bids`, and posts an **Auction Ended — No Bids** announcement card.
- **Listing & Cancellation**: Added `/auctions` to list active auctions and `/cancelauction <id>` to let sellers cancel auctions with no active bids.

---

## Verification & Testing
- Staged, committed, and pushed all updates to GitHub successfully.
- Validated python compilation locally (fully clean compilation output).
- Staging and pushing completed with zero syntax errors.
