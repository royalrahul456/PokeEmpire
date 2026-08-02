"""
migrate_to_postgres.py
────────────────────────────────────────────────────────────────
Migrates ALL 12 tables from local SQLite database (pokeempire.db)
to PostgreSQL / CockroachDB dynamically preserving all fields.
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
    PokemonFormMedia, PvpBattle, Auction, AuctionBid
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
    ("Auction Bids", AuctionBid, AuctionBid.id)
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

    print("🔌 Connecting to target database...")
    pg_engine = create_async_engine(postgres_url, echo=False)
    PGSession = sessionmaker(bind=pg_engine, class_=AsyncSession, expire_on_commit=False)

    print("🛠️  Ensuring tables exist in target database...")
    async with pg_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("\n📚 Reading data from local SQLite...\n")
    sqlite_data = {}
    async with SessionLocal() as sqlite_session:
        for name, cls, pk_col in MODELS:
            res = await sqlite_session.execute(select(cls))
            sqlite_data[cls] = res.scalars().all()
            print(f"   • {name:20s}: {len(sqlite_data[cls])}")

    print("\n✍️  Writing data to target database...\n")
    async with PGSession() as db:
        for name, cls, pk_col in MODELS:
            items = sqlite_data[cls]
            print(f"   - Copying {name} ({len(items)} items)...")
            
            if pk_col is not None:
                existing_pks = set((await db.execute(select(pk_col))).scalars().all())
            else:
                existing_pks = set()

            for item in items:
                d = model_to_dict(item)
                if pk_col is not None:
                    pk_val = getattr(item, pk_col.name)
                    if pk_val in existing_pks:
                        continue
                
                db.add(cls(**d))
            await db.flush()

        await db.commit()

    print("\n🎉 Database migration complete! All 12 tables have been copied to PostgreSQL / CockroachDB.")

if __name__ == "__main__":
    url = input("Enter target database URL: ").strip()
    if not url:
        print("❌ URL cannot be empty.")
        sys.exit(1)
    asyncio.run(migrate_data(url))
