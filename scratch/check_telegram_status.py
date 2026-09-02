import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')
import config
from aiogram import Bot

async def check_webhook():
    bot = Bot(token=config.BOT_TOKEN)
    try:
        me = await bot.get_me()
        print(f"🤖 Bot Name: {me.first_name} (@{me.username})")
        
        webhook_info = await bot.get_webhook_info()
        print(f"🔗 Webhook Info:")
        print(f"   URL: '{webhook_info.url}'")
        print(f"   Has Custom Certificate: {webhook_info.has_custom_certificate}")
        print(f"   Pending Update Count: {webhook_info.pending_update_count}")
        print(f"   Last Error Message: {webhook_info.last_error_message}")
        print(f"   Last Error Date: {webhook_info.last_error_date}")
        
        if webhook_info.url:
            print("\n⚠️ A Webhook is currently active on Telegram! Deleting webhook so long-polling works...")
            await bot.delete_webhook(drop_pending_updates=True)
            print("✅ Webhook deleted! Bot is now ready for long-polling updates.")
        else:
            print("\n✅ Webhook is clear. Long-polling is active.")
            
    except Exception as e:
        print(f"❌ Error checking Telegram status: {e}")
    finally:
        await bot.session.close()

if __name__ == "__main__":
    asyncio.run(check_webhook())
