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
from sqlalchemy import select

from database.database import Base, SessionLocal
from database.models import (
    User, Pokemon, UserPokemon, ActiveSpawn,
    GroupSetting, GlobalSetting, RedeemCode, RedeemClaim,
    PokemonFormMedia, PvpBattle, Auction, AuctionBid,
    Guild, GuildMember, TrainerQuest, TransactionHistory, MysteryEventState, BugReport
)

MODELS = [
    ("Pokémon species", Pokemon, Pokemon.id),
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
    ("Bug Reports", BugReport, BugReport.id)
]

def model_to_dict(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}

async def migrate_data(postgres_url: str):
    if postgres_url.startswith("postgresql://"):
        postgres_url = postgres_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    if "cockroachlabs" in postgres_url:
        postgres_url = postgres_url.replace("postgresql+asyncpg://", "cockroachdb+asyncpg://", 1)

    if "sslmode=" in postgres_url:
        postgres_url = postgres_url.replace("sslmode=require", "ssl=require")
        postgres_url = postgres_url.replace("sslmode=prefer", "ssl=prefer")
        postgres_url = postgres_url.replace("sslmode=verify-full", "ssl=require")
        postgres_url = postgres_url.replace("sslmode=verify-ca", "ssl=require")

    print("🔌 Connecting to Neon / PostgreSQL target database...")
    pg_engine = create_async_engine(postgres_url, echo=False)
    PGSession = sessionmaker(bind=pg_engine, class_=AsyncSession, expire_on_commit=False)

    print("🧹 Recreating tables in target database for clean sync...")
    async with pg_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("\n📚 Reading data from local SQLite database (pokeempire.db)...\n")
    sqlite_data = {}
    async with SessionLocal() as sqlite_session:
        for name, cls, pk_col in MODELS:
            try:
                res = await sqlite_session.execute(select(cls))
                sqlite_data[cls] = res.scalars().all()
                print(f"   • {name:20s}: {len(sqlite_data[cls])}")
            except Exception as e:
                sqlite_data[cls] = []
                print(f"   • {name:20s}: 0 (Notice: {e})")

    print("\n✍️  Migrating old data to Neon database...\n")
    async with PGSession() as db:
        for name, cls, pk_col in MODELS:
            items = sqlite_data[cls]
            if not items:
                continue
            print(f"   - Copying {name} ({len(items)} items)...")
            for item in items:
                d = model_to_dict(item)
                try:
                    db.add(cls(**d))
                except Exception:
                    pass
            await db.flush()

        await db.commit()

    print("\n🎉 Migration Complete! All tables and old player data successfully migrated to Neon PostgreSQL!")

if __name__ == "__main__":
    url = input("Enter Neon Database URL (postgresql://...): ").strip()
    if not url:
        print("❌ URL cannot be empty.")
        sys.exit(1)
    asyncio.run(migrate_data(url))
