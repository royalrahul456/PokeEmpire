import asyncio
import sys
import os
from aiogram import Bot

# Adjust path to import from PokeEmpire
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Reconfigure stdout to use UTF-8
if sys.platform.startswith('win'):
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from utils.emoji_patch import EMOJI_MAPPING

async def main():
    bot_token = "8733227680:AAGuWXY9eIAFfMG8YSZZ2WUzM1E25e5melU"
    admin_id = 6593485710

    bot = Bot(token=bot_token)
    
    print("Testing each emoji replacement individually...")
    success_count = 0
    fail_count = 0
    for emoji, eid in EMOJI_MAPPING.items():
        text = f"Testing emoji: <tg-emoji emoji-id=\"{eid}\">{emoji}</tg-emoji> ({emoji} -> {eid})"
        try:
            await bot.send_message(chat_id=admin_id, text=text, parse_mode="HTML")
            print(f"✅ Success: {emoji} ({eid})")
            success_count += 1
        except Exception as e:
            print(f"❌ FAILED: {emoji} ({eid}) -> {e}")
            fail_count += 1
            
    print(f"\nSummary: Successes: {success_count}, Failures: {fail_count}")
    await bot.session.close()

if __name__ == "__main__":
    asyncio.run(main())
