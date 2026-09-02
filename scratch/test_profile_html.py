import sys
import os
import html

# Adjust path to import from PokeEmpire
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from utils.emoji_patch import replace_emojis, process_text_or_caption
from aiogram import Bot

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
    f"├─➩ ⚪️ Common: {commons}\n"
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

print(f"Original length: {len(profile_card)}")

bot = Bot(token="123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ")
processed_text, mode = process_text_or_caption(profile_card, "HTML", bot)

print(f"Processed length: {len(processed_text)}")
print(f"Processed parse mode: {mode}")

# Check HTML tag nesting / correctness using simple stack
import re
tags = re.findall(r'<(/?[a-zA-Z0-9_-]+)(?:\s+[^>]*?)?>', processed_text)
stack = []
errors = []
for tag in tags:
    if tag.startswith('/'):
        tag_name = tag[1:]
        if not stack:
            errors.append(f"Error: closing tag </{tag_name}> with no open tag")
        elif stack[-1] != tag_name:
            errors.append(f"Error: closing tag </{tag_name}> doesn't match open tag <{stack[-1]}>")
            stack.pop()
        else:
            stack.pop()
    else:
        tag_name = tag.split()[0]
        stack.append(tag_name)

if stack:
    errors.append(f"Error: unclosed tags: {stack}")

if errors:
    print("Verification failed! Errors found:")
    for err in errors:
        print(" - " + err)
else:
    print("HTML tags are properly nested and closed!")

# Write the processed text to a file in UTF-8
with open("scratch/processed_profile.txt", "w", encoding="utf-8") as f:
    f.write(processed_text)
print("Wrote processed text to scratch/processed_profile.txt")
