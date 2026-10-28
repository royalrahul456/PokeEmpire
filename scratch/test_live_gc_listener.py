import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import asyncio
from aiogram import Bot
import config

async def test_live_send():
    gc_id = -1004441222762
    print(f"Connecting as @PokeEmpireBot to send test message to official GC {gc_id}...", flush=True)

    bot = Bot(config.BOT_TOKEN)
    try:
        me = await bot.get_me()
        print(f"✅ Bot get_me: @{me.username} ({me.id})", flush=True)

        # 1. Clear webhook first
        await bot.delete_webhook(drop_pending_updates=True)
        print("✅ Webhook cleared.", flush=True)

        # 2. Try sending test text message to official GC
        print(f"Sending test text message to {gc_id}...", flush=True)
        msg1 = await bot.send_message(
            chat_id=gc_id,
            text="⚡ <b>PokeEmpire Bot Status Test</b> ⚡\nBot is online and responding!",
            parse_mode="HTML"
        )
        print(f"✅ Text Message SENT SUCCESSFULLY! Message ID: {msg1.message_id}", flush=True)

        # 3. Try sending test photo message to official GC
        print(f"Sending test photo message to {gc_id}...", flush=True)
        test_photo = "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/25.png"
        msg2 = await bot.send_photo(
            chat_id=gc_id,
            photo=test_photo,
            caption="⚡ <b>Pikachu Test Photo</b>\nPhoto sending verified!",
            parse_mode="HTML"
        )
        print(f"✅ Photo Message SENT SUCCESSFULLY! Message ID: {msg2.message_id}", flush=True)

    except Exception as e:
        import traceback
        print(f"❌ Telegram API Error sending message to GC {gc_id}: {e}", flush=True)
        traceback.print_exc()
    finally:
        await bot.session.close()

if __name__ == '__main__':
    asyncio.run(test_live_send())
