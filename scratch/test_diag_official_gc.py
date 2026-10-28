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

async def test_official_gc_permissions():
    gc_id = -1004441222762
    print(f"==================================================")
    print(f"      OFFICIAL GC DIAGNOSTICS FOR CHAT {gc_id}")
    print(f"==================================================")

    # 1. Check Main Bot (@PokeEmpireBot)
    print("\n[1/2] Checking Main Bot (@PokeEmpireBot)...")
    try:
        b1 = Bot(config.BOT_TOKEN)
        me1 = await b1.get_me()
        print(f"  Authenticated as @{me1.username} (ID: {me1.id})")
        
        try:
            chat = await b1.get_chat(gc_id)
            print(f"  Group Chat Title: '{chat.title}', Type: '{chat.type}'")
            member1 = await b1.get_chat_member(chat_id=gc_id, user_id=me1.id)
            print(f"  Bot Member Status in GC: '{member1.status}'")
            if hasattr(member1, "can_send_messages"):
                print(f"    can_send_messages: {member1.can_send_messages}")
            if hasattr(member1, "can_send_media_messages"):
                print(f"    can_send_media_messages: {member1.can_send_media_messages}")
        except Exception as chat_err:
            print(f"  ❌ Telegram API Error accessing chat {gc_id}: {chat_err}")
            
        await b1.session.close()
    except Exception as e:
        print(f"  ❌ Main Bot Error: {e}")

    # 2. Check Games Bot (@PokeXArenaBot)
    print("\n[2/2] Checking Games Bot (@PokeXArenaBot)...")
    try:
        b2 = Bot(config.GAMES_BOT_TOKEN)
        me2 = await b2.get_me()
        print(f"  Authenticated as @{me2.username} (ID: {me2.id})")
        
        try:
            member2 = await b2.get_chat_member(chat_id=gc_id, user_id=me2.id)
            print(f"  Games Bot Member Status in GC: '{member2.status}'")
        except Exception as chat_err:
            print(f"  ❌ Telegram API Error accessing chat {gc_id}: {chat_err}")
            
        await b2.session.close()
    except Exception as e:
        print(f"  ❌ Games Bot Error: {e}")

    print("\n==================================================")

if __name__ == '__main__':
    asyncio.run(test_official_gc_permissions())
