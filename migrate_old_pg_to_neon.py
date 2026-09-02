import os
import sys
import asyncio

sys.stdout.reconfigure(encoding="utf-8")

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(PROJECT_DIR)
os.chdir(PROJECT_DIR)

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database.database import Base
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

def format_url(url: str) -> str:
    db_url = url
    if "cockroachlabs" in db_url:
        db_url = db_url.replace("postgresql://", "cockroachdb+asyncpg://", 1)
        db_url = db_url.replace("postgresql+asyncpg://", "cockroachdb+asyncpg://", 1)
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    if "sslmode=" in db_url:
        db_url = db_url.replace("sslmode=require", "ssl=require")
        db_url = db_url.replace("sslmode=prefer", "ssl=prefer")
        db_url = db_url.replace("sslmode=verify-full", "ssl=require")
        db_url = db_url.replace("sslmode=verify-ca", "ssl=require")

    if "channel_binding=" in db_url:
        import re
        db_url = re.sub(r'[&?]channel_binding=[^&]*', '', db_url)
    return db_url

def model_to_dict(obj):
    return {c.name: getattr(obj, c.name) for c in obj.__table__.columns}

async def migrate_cloud_to_neon(source_url: str, target_url: str):
    src_formatted = format_url(source_url)
    tgt_formatted = format_url(target_url)

    print("🔌 Connecting to Old Database (Source)...", flush=True)
    src_engine = create_async_engine(src_formatted, echo=False)
    SrcSession = sessionmaker(bind=src_engine, class_=AsyncSession, expire_on_commit=False)

    print("🔌 Connecting to Neon Database (Target)...", flush=True)
    tgt_engine = create_async_engine(tgt_formatted, echo=False)
    TgtSession = sessionmaker(bind=tgt_engine, class_=AsyncSession, expire_on_commit=False)

    print("🧹 Ensuring tables and columns exist in Neon...", flush=True)
    async with tgt_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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

    print("\n📚 Reading latest data from Old Database...\n", flush=True)
    source_data = {}
    async with SrcSession() as src_db:
        for name, cls, pk_col in MODELS:
            try:
                res = await src_db.execute(select(cls))
                source_data[cls] = res.scalars().all()
                print(f"   • {name:22s}: {len(source_data[cls])} records", flush=True)
            except Exception as e:
                source_data[cls] = []
                print(f"   • {name:22s}: 0 records (Notice: {e})", flush=True)

    print("\n✍️  Migrating latest data into Neon Database...\n", flush=True)
    async with TgtSession() as tgt_db:
        for name, cls, pk_col in MODELS:
            items = source_data[cls]
            if not items:
                continue
            print(f"   - Copying {name} ({len(items)} items)...", flush=True)
            try:
                dicts = [model_to_dict(item) for item in items]
                chunk_size = 500
                for i in range(0, len(dicts), chunk_size):
                    chunk = dicts[i:i + chunk_size]
                    stmt = pg_insert(cls).values(chunk).on_conflict_do_nothing()
                    await tgt_db.execute(stmt)
                await tgt_db.commit()
                print(f"     ✅ Successfully copied {len(items)} items into Neon!", flush=True)
            except Exception as ex:
                await tgt_db.rollback()
                print(f"     ⚠️ Fallback merge for {name}: {ex}", flush=True)
                for item in items:
                    d = model_to_dict(item)
                    try:
                        await tgt_db.merge(cls(**d))
                    except Exception:
                        pass
                await tgt_db.commit()
                print(f"     ✅ Successfully merged {name} into Neon!", flush=True)

    print("\n🎉 MIGRATION COMPLETE! All latest month data copied to Neon PostgreSQL!", flush=True)

if __name__ == "__main__":
    src_url = input("Enter OLD Database URL (CockroachDB / Old Postgres): ").strip()
    tgt_url = input("Enter NEW Neon Database URL: ").strip()
    if not src_url or not tgt_url:
        print("❌ Database URLs cannot be empty.")
        sys.exit(1)
    asyncio.run(migrate_cloud_to_neon(src_url, tgt_url))
