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
from sqlalchemy import select, text
from database.database import SessionLocal
from database.models import GroupSetting, ActiveSpawn

async def check_official_gc():
    gc_id = -1004441222762
    print(f"Checking Database state for Official GC Chat {gc_id}...", flush=True)

    async with SessionLocal() as db:
        # 1. GroupSetting
        stmt = select(GroupSetting).where(GroupSetting.chat_id == gc_id)
        res = await db.execute(stmt)
        setting = res.scalar_one_or_none()
        if setting:
            print(f"✅ GroupSetting found:")
            print(f"   enabled: {setting.enabled}")
            print(f"   message_counter: {setting.message_counter}")
            print(f"   spawn_threshold: {setting.spawn_threshold}")
            print(f"   scribble_enabled: {setting.scribble_enabled}")
            print(f"   nameguess_enabled: {setting.nameguess_enabled}")
        else:
            print(f"⚠️ No GroupSetting entry found for chat {gc_id}! (It will auto-create on first message)")

        # 2. ActiveSpawn
        sp_stmt = select(ActiveSpawn).where(ActiveSpawn.chat_id == gc_id)
        sp_res = await db.execute(sp_stmt)
        active = sp_res.scalar_one_or_none()
        if active:
            print(f"✅ ActiveSpawn found: pokemon_id={active.pokemon_id}, msg_id={active.message_id}")
        else:
            print(f"ℹ️ No ActiveSpawn currently active in chat {gc_id}.")

if __name__ == '__main__':
    asyncio.run(check_official_gc())
