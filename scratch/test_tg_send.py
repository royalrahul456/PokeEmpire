import asyncio
import sys
import os
import html
from aiogram import Bot

# Adjust path to import from PokeEmpire
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.emoji_patch import process_text_or_caption, patch_bot_emojis

async def main():
    bot_token = "8733227680:AAGuWXY9eIAFfMG8YSZZ2WUzM1E25e5melU"
    admin_id = 6593485710

    bot = Bot(token=bot_token)
    patch_bot_emojis(bot)

    user_nickname = "Rahul Pachute ⚡"
    user_id = 123456789
    formatted_coins = "1,500,000"
    unique_caught = 150
    total_caught = 450
    total_species = 1025
    dex_pct = (unique_caught / total_species) * 100
    dex_bar = "▰▰▰▱▱▱▱▱▱▱"
    current_streak = 5
    best_streak = 12
    fav_name = "Charizard (Form 1)"
    commons = 50
    uncommons = 40
    mediums = 30
    rares = 20
    epics = 8
    legendaries = 1
    mythicals = 1
    total_shiny = 5
    amv_count = 10
    dmax_count = 5
    gmax_count = 2
    zmove_count = 1
    terastal_count = 1
    rank_position = 15

    profile_card = (
        f"╭──「 🏆 Trainer Profile 」\n"
        f"├─➩ 🏓 User: {html.escape(user_nickname)}\n"
        f"├─➩ 🆔 ID: <code>{user_id}</code>\n"
        f"├─➩ 💰 Balance: <code>{formatted_coins} coins</code>\n"
        f"├─➩ ⚡ Pokémon: {unique_caught} (Total Catches: {total_caught})\n"
        f"├─➩ 🌍 Pokédex: {unique_caught}/{total_species} ({dex_pct:.3f}%)\n"
        f"├─➩ 🎁 Progress:\n"
        f"╰         {dex_bar}\n\n"
        f"╭─ Cover & Streaks ─\n"
        f"├─➩ ⭐ Favorite: <code>{html.escape(fav_name)}</code>\n"
        f"├─➩ 🔥 Current Streak: <code>{current_streak} days</code>\n"
        f"├─➩ 🏆 Best Streak: <code>{best_streak} days</code>\n"
        f"╰───────────────────\n\n"
        f"╭─ Rarity Breakdown ─\n"
        f"├─➩ ⚪ Common: {commons}\n"
        f"├─➩ 🟢 Uncommon: {uncommons}\n"
        f"├─➩ 🔵 Medium: {mediums}\n"
        f"├─➩ 🟣 Rare: {rares}\n"
        f"├─➩ 🔮 Epic: {epics}\n"
        f"├─➩ 🌟 Legendary: {legendaries}\n"
        f"├─➩ 🌌 Mythical: {mythicals}\n"
        f"├─➩ ✨ Shiny: {total_shiny}\n"
        f"╰───────────────────\n\n"
        f"╭─ Forms Breakdown ─\n"
        f"├─➩ 🎬 AMV / Art: {amv_count}\n"
        f"├─➩ ⚡ Dmax: {dmax_count}\n"
        f"├─➩ 💥 Gmax: {gmax_count}\n"
        f"├─➩ 🌀 Z-Move: {zmove_count}\n"
        f"├─➩ 🔮 Terastal: {terastal_count}\n"
        f"╰───────────────────\n\n"
        f"╭─ Global Rank ─\n"
        f"├─➩ 🏆 Position: #{rank_position}\n"
        f"╰───────────────────"
    )

    print("Attempting to send as a photo with caption...")
    photo_url = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/890.png"
    try:
        await bot.send_photo(chat_id=admin_id, photo=photo_url, caption=profile_card, parse_mode="HTML")
        print("Success sending photo!")
    except Exception as e:
        print(f"Failed to send photo: {e}")

    print("\nAttempting to send as a text message...")
    try:
        await bot.send_message(chat_id=admin_id, text=profile_card, parse_mode="HTML")
        print("Success sending text message!")
    except Exception as e:
        print(f"Failed to send text message: {e}")

    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
