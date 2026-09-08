import asyncio
import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import create_async_engine

# Live DB URL
url = "postgresql+asyncpg://neondb_owner:npg_eanbgOJq19Kv@ep-weathered-cell-ad5waxtl-pooler.c-2.us-east-1.aws.neon.tech/neondb?ssl=require"

BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "live_db_backups")

async def dump_data():
    os.makedirs(BACKUP_DIR, exist_ok=True)
    print(f"📦 Exporting 100% of live database tables into backup directory: {BACKUP_DIR}...")
    
    engine = create_async_engine(url, connect_args={"statement_cache_size": 0})
    
    tables = [
        "users",
        "pokemon",
        "user_pokemon",
        "group_settings",
        "global_settings",
        "redeem_codes",
        "redeem_claims",
        "guilds",
        "guild_members",
        "auctions",
        "auction_bids",
        "chat_message_stats",
        "trainer_quests",
        "transaction_history",
        "mystery_event_state",
        "bug_reports",
        "pokemon_form_media"
    ]
    
    summary = {}
    
    async with engine.begin() as conn:
        for t in tables:
            try:
                res = await conn.execute(text(f"SELECT * FROM {t}"))
                rows = [dict(row._mapping) for row in res.fetchall()]
                
                # Convert datetime & non-serializable objects to string
                for row in rows:
                    for k, v in row.items():
                        if isinstance(v, datetime):
                            row[k] = v.isoformat()
                            
                filepath = os.path.join(BACKUP_DIR, f"{t}.json")
                with open(filepath, "w", encoding="utf-8") as f:
                    json.dump(rows, f, indent=2, ensure_ascii=False)
                    
                summary[t] = len(rows)
                print(f"  ✅ {t}: {len(rows)} records exported -> {os.path.basename(filepath)}")
            except Exception as e:
                print(f"  ⚠️ Could not export {t}: {e}")
                
    print("\n🎉 COMPLETE LIVE DATABASE BACKUP SUCCESSFUL!")
    print("--------------------------------------------------")
    for t, count in summary.items():
        print(f"   • {t}: {count} rows")
    print("--------------------------------------------------")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(dump_data())
