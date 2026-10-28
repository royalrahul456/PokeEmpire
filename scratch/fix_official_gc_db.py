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
from sqlalchemy import select, update
from database.database import SessionLocal
from database.models import GroupSetting
from utils.group_monitor import group_settings_cache

async def fix_gc():
    gc_id = -1004441222762
    print(f"Updating GroupSetting in database for Official GC Chat {gc_id}...", flush=True)

    async with SessionLocal() as db:
        stmt = select(GroupSetting).where(GroupSetting.chat_id == gc_id)
        res = await db.execute(stmt)
        setting = res.scalar_one_or_none()
        
        if not setting:
            setting = GroupSetting(
                chat_id=gc_id,
                message_counter=0,
                spawn_threshold=50,
                enabled=True,
                scribble_enabled=True,
                nameguess_enabled=True
            )
            db.add(setting)
        else:
            setting.enabled = True
            setting.scribble_enabled = True
            setting.nameguess_enabled = True
            setting.spawn_threshold = 50

        await db.commit()
        print("✅ Official GC settings updated in DB:")
        print(f"   enabled = {setting.enabled}")
        print(f"   scribble_enabled = {setting.scribble_enabled}")
        print(f"   nameguess_enabled = {setting.nameguess_enabled}")
        print(f"   spawn_threshold = {setting.spawn_threshold}")

    # Clear in-memory cache if any
    group_settings_cache.pop(gc_id, None)
    print("✅ Cleared in-memory cache for official GC.")

if __name__ == '__main__':
    asyncio.run(fix_gc())
