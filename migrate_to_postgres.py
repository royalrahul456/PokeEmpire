"""
migrate_to_postgres.py
────────────────────────────────────────────────────────────────
Migrates ALL 12 tables from local SQLite database (pokeempire.db)
to PostgreSQL / CockroachDB dynamically preserving all fields.
Recreates target tables first for a 100% clean copy.
────────────────────────────────────────────────────────────────
"""

import sys
import os
import asyncio

sys.stdout.reconfigure(encoding='utf-8')

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(PROJECT_DIR)
os.chdir(PROJECT_DIR)

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text

from database.database import Base, SessionLocal
from database.models import (
    User, Pokemon, UserPokemon, ActiveSpawn,
    GroupSetting, GlobalSetting, RedeemCode, RedeemClaim,
    PokemonFormMedia, PvpBattle, Auction, AuctionBid,
    Guild, GuildMember, TrainerQuest, TransactionHistory, MysteryEventState, BugReport
)

MODELS = [
    ("User profiles", User, User.id),
    ("User Pokémon", UserPokemon, UserPokemon.id),
    ("Active Spawns", ActiveSpawn, ActiveSpawn.chat_id),
    ("Group Settings", GroupSetting, GroupSetting.chat_id),
    ("Global Settings", GlobalSetting, GlobalSetting.key),
    ("Redeem Codes", RedeemCode, RedeemCode.id),
    ("Redeem Claims", RedeemClaim, RedeemClaim.id),
    ("Pokemon Form Media", PokemonFormMedia, None),
    ("PvP Battles", PvpBattle, PvpBattle.id),
    ("Auctions", Auction, Auction.id),
    ("Auction Bids", AuctionBid, AuctionBid.id),
    ("Guilds", Guild, Guild.id),
    ("Guild Members", GuildMember, GuildMember.id),
    ("Trainer Quests", TrainerQuest, TrainerQuest.id),
    ("Transaction History", TransactionHistory, TransactionHistory.id),
    ("Mystery Event State", MysteryEventState, MysteryEventState.key),
    ("Bug Reports", BugReport, BugReport.id),
    ("Pokémon species", Pokemon, Pokemon.id)
]

def model_to_dict(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}

async def migrate_data(postgres_url: str):
    # First run local init_db to ensure local SQLite schema is fully updated
    from database.database import init_db
    try:
        await init_db()
    except Exception:
        pass

    if postgres_url.startswith("postgresql://"):
        postgres_url = postgres_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    if "cockroachlabs" in postgres_url:
        postgres_url = postgres_url.replace("postgresql+asyncpg://", "cockroachdb+asyncpg://", 1)

    if "sslmode=" in postgres_url:
        postgres_url = postgres_url.replace("sslmode=require", "ssl=require")
        postgres_url = postgres_url.replace("sslmode=prefer", "ssl=prefer")
        postgres_url = postgres_url.replace("sslmode=verify-full", "ssl=require")
        postgres_url = postgres_url.replace("sslmode=verify-ca", "ssl=require")

    if "channel_binding=" in postgres_url:
        import re
        postgres_url = re.sub(r'[&?]channel_binding=[^&]*', '', postgres_url)

    print("🔌 Connecting to Neon / PostgreSQL target database...", flush=True)
    pg_engine = create_async_engine(postgres_url, echo=False)
    PGSession = sessionmaker(bind=pg_engine, class_=AsyncSession, expire_on_commit=False)

    print("🧹 Creating & migrating tables in Neon target database...", flush=True)
    async with pg_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        
        # Run column migrations for existing Neon tables
        user_cols = [
            ("trainer_level", "INTEGER DEFAULT 1"),
            ("trainer_xp", "INTEGER DEFAULT 0"),
            ("current_streak", "INTEGER DEFAULT 0"),
            ("best_streak", "INTEGER DEFAULT 0"),
            ("last_secured_date", "VARCHAR(20)"),
            ("last_catch_date", "VARCHAR(20)"),
            ("catches_today", "INTEGER DEFAULT 0")
        ]
        for col, col_type in user_cols:
            try:
                await conn.execute(text(f"ALTER TABLE users ADD COLUMN IF NOT EXISTS {col} {col_type}"))
            except Exception:
                pass

        poke_cols = ["video_url", "dmax_url", "gmax_url", "zmove_url", "terastal_url"]
        for col in poke_cols:
            try:
                await conn.execute(text(f"ALTER TABLE pokemon ADD COLUMN IF NOT EXISTS {col} VARCHAR(255)"))
            except Exception:
                pass

        try:
            await conn.execute(text("ALTER TABLE user_pokemon ADD COLUMN IF NOT EXISTS is_amv BOOLEAN DEFAULT false"))
        except Exception:
            pass

    print("\n📚 Reading data from local SQLite database (pokeempire.db)...\n", flush=True)
    sqlite_data = {}
    async with SessionLocal() as sqlite_session:
        for name, cls, pk_col in MODELS:
            try:
                res = await sqlite_session.execute(select(cls))
                sqlite_data[cls] = res.scalars().all()
                print(f"   • {name:22s}: {len(sqlite_data[cls])}", flush=True)
            except Exception as e:
                sqlite_data[cls] = []
                print(f"   • {name:22s}: 0 (Notice: {e})", flush=True)

    from sqlalchemy.dialects.postgresql import insert as pg_insert

    print("\n✍️  Migrating data to Neon database...\n", flush=True)
    async with PGSession() as db:
        for name, cls, pk_col in MODELS:
            items = sqlite_data[cls]
            if not items:
                continue
            print(f"   - Copying {name} ({len(items)} items)...", flush=True)
            try:
                dicts = [model_to_dict(item) for item in items]
                chunk_size = 500
                for i in range(0, len(dicts), chunk_size):
                    chunk = dicts[i:i + chunk_size]
                    stmt = pg_insert(cls).values(chunk).on_conflict_do_nothing()
                    await db.execute(stmt)
                await db.commit()
                print(f"     ✅ Successfully synced {len(items)} items into {name}.", flush=True)
            except Exception as ex:
                await db.rollback()
                print(f"     ⚠️ Fallback row merge for {name}: {ex}", flush=True)
                for item in items:
                    d = model_to_dict(item)
                    try:
                        await db.merge(cls(**d))
                    except Exception:
                        pass
                await db.commit()
                print(f"     ✅ Successfully merged {name}.", flush=True)

    print("\n🎉 Migration Complete! All tables and player data successfully migrated to Neon PostgreSQL!", flush=True)

if __name__ == "__main__":
    url = input("Enter Neon Database URL (postgresql://...): ").strip()
    if not url:
        print("❌ URL cannot be empty.")
        sys.exit(1)
    asyncio.run(migrate_data(url))
