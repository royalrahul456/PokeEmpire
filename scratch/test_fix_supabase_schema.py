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
from sqlalchemy import text
from database.database import engine

async def migrate_supabase_columns():
    print("Connecting to Supabase PostgreSQL to run column migrations...", flush=True)
    
    migrations = [
        # group_settings columns
        "ALTER TABLE group_settings ADD COLUMN IF NOT EXISTS scribble_enabled BOOLEAN DEFAULT true;",
        "ALTER TABLE group_settings ADD COLUMN IF NOT EXISTS nameguess_enabled BOOLEAN DEFAULT true;",
        
        # users columns
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS current_streak INTEGER DEFAULT 0;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS best_streak INTEGER DEFAULT 0;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_secured_date VARCHAR(20);",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_catch_date VARCHAR(20);",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS catches_today INTEGER DEFAULT 0;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_mines_date VARCHAR(20);",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_mines_count INTEGER DEFAULT 0;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS trainer_level INTEGER DEFAULT 1;",
        "ALTER TABLE users ADD COLUMN IF NOT EXISTS trainer_xp INTEGER DEFAULT 0;",
        
        # active_mines_games
        "CREATE TABLE IF NOT EXISTS active_mines_games (chat_id BIGINT PRIMARY KEY, user_id BIGINT, bet_amount INTEGER, mines_count INTEGER, grid TEXT, revealed TEXT, status VARCHAR(20), created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);",
        "ALTER TABLE active_mines_games ADD COLUMN IF NOT EXISTS last_activity_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;",
        
        # pokemon
        "ALTER TABLE pokemon ADD COLUMN IF NOT EXISTS video_url VARCHAR(255);",
        "ALTER TABLE pokemon ADD COLUMN IF NOT EXISTS dmax_url VARCHAR(255);",
        "ALTER TABLE pokemon ADD COLUMN IF NOT EXISTS gmax_url VARCHAR(255);",
        "ALTER TABLE pokemon ADD COLUMN IF NOT EXISTS zmove_url VARCHAR(255);",
        "ALTER TABLE pokemon ADD COLUMN IF NOT EXISTS terastal_url VARCHAR(255);",
        
        # user_pokemon
        "ALTER TABLE user_pokemon ADD COLUMN IF NOT EXISTS is_amv BOOLEAN DEFAULT false;",
        "ALTER TABLE user_pokemon ADD COLUMN IF NOT EXISTS form_index INTEGER DEFAULT 0;",
        "ALTER TABLE user_pokemon ADD COLUMN IF NOT EXISTS serial_number VARCHAR(20);",
        
        # redeem_codes
        "ALTER TABLE redeem_codes ADD COLUMN IF NOT EXISTS reward_form_index INTEGER DEFAULT 0;"
    ]

    for query in migrations:
        try:
            async with engine.begin() as conn:
                await conn.execute(text(query))
                print(f"✅ Executed: {query.strip()}", flush=True)
        except Exception as e:
            print(f"⚠️ Query skipped for '{query.strip()[:40]}...': {e}", flush=True)

    print("\n🎉 All Supabase column migrations completed successfully!", flush=True)

if __name__ == '__main__':
    asyncio.run(migrate_supabase_columns())
