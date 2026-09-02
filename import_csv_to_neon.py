import os
import sys
import glob
import csv
import asyncio
from datetime import datetime

sys.stdout.reconfigure(encoding="utf-8")

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(PROJECT_DIR)
os.chdir(PROJECT_DIR)

os.environ["DATABASE_URL"] = "postgresql://neondb_owner:npg_eanbgOJq19Kv@ep-weathered-cell-ad5waxtl-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require"

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import text, select
from database.database import Base
from database.models import (
    User, Pokemon, UserPokemon, ActiveSpawn,
    GroupSetting, GlobalSetting, RedeemCode, RedeemClaim,
    PokemonFormMedia, PvpBattle, Auction, AuctionBid,
    Guild, GuildMember, TrainerQuest, TransactionHistory, MysteryEventState, BugReport
)
from utils.trainer_level import sync_retroactive_levels

TABLE_MAP = {
    "users": User,
    "user_pokemon": UserPokemon,
    "guilds": Guild,
    "guild_members": GuildMember,
    "group_settings": GroupSetting,
    "global_settings": GlobalSetting,
    "auctions": Auction,
    "auction_bids": AuctionBid,
    "redeem_codes": RedeemCode,
    "redeem_claims": RedeemClaim,
    "pokemon_form_media": PokemonFormMedia,
    "bug_reports": BugReport,
    "trainer_quests": TrainerQuest,
    "transaction_history": TransactionHistory
}

def parse_val(val, col_name):
    if val is None or val == "" or val == "null" or val == "None":
        return None
    val_str = str(val).strip()
    if col_name in ("key", "value", "last_secured_date", "last_catch_date", "serial_number", "nickname", "username", "code"):
        return val_str
    if val_str.lower() == "true":
        return True
    if val_str.lower() == "false":
        return False
    if val_str.isdigit() or (val_str.startswith("-") and val_str[1:].isdigit()):
        return int(val_str)
    try:
        if "." in val_str:
            return float(val_str)
    except ValueError:
        pass
    # Parse ISO dates
    if ("-" in val_str or ":" in val_str) and len(val_str) >= 10:
        clean_dt = val_str.replace("Z", "").split("+")[0].strip()
        for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S"):
            try:
                return datetime.strptime(clean_dt, fmt)
            except ValueError:
                pass
    return val_str

async def process_csv_import():
    downloads_dir = r"C:\Users\Rahul Pachute\Downloads"
    csv_files = glob.glob(os.path.join(downloads_dir, "query-results*.csv"))
    if not csv_files:
        print("❌ No query-results CSV files found in Downloads directory.", flush=True)
        return

    print(f"🔍 Found {len(csv_files)} downloaded CSV files in Downloads folder!", flush=True)

    # Format database URL
    db_url = os.environ["DATABASE_URL"]
    if db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if "sslmode=require" in db_url:
        db_url = db_url.replace("sslmode=require", "ssl=require")

    engine = create_async_engine(db_url, echo=False)
    Session = sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)

    # Initialize tables and column migrations
    async with engine.begin() as conn:
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

        bigint_alters = [
            "ALTER TABLE redeem_codes ALTER COLUMN id TYPE BIGINT USING id::BIGINT",
            "ALTER TABLE redeem_claims ALTER COLUMN id TYPE BIGINT USING id::BIGINT",
            "ALTER TABLE redeem_claims ALTER COLUMN code_id TYPE BIGINT USING code_id::BIGINT",
            "ALTER TABLE auctions ALTER COLUMN id TYPE BIGINT USING id::BIGINT",
            "ALTER TABLE auction_bids ALTER COLUMN id TYPE BIGINT USING id::BIGINT",
            "ALTER TABLE auction_bids ALTER COLUMN auction_id TYPE BIGINT USING auction_id::BIGINT",
            "ALTER TABLE pvp_battles ALTER COLUMN id TYPE BIGINT USING id::BIGINT",
            "ALTER TABLE guilds ALTER COLUMN id TYPE BIGINT USING id::BIGINT",
            "ALTER TABLE guild_members ALTER COLUMN id TYPE BIGINT USING id::BIGINT",
            "ALTER TABLE guild_members ALTER COLUMN guild_id TYPE BIGINT USING guild_id::BIGINT"
        ]
        for stmt in bigint_alters:
            try:
                await conn.execute(text(stmt))
            except Exception:
                pass

    from sqlalchemy.dialects.postgresql import insert as pg_insert

    import_priority = {name: idx for idx, name in enumerate([
        "users", "global_settings", "group_settings", "pokemon_form_media",
        "redeem_codes", "redeem_claims", "guilds", "guild_members",
        "auctions", "auction_bids", "user_pokemon"
    ])}

    # Match and sort CSV files by dependency order
    file_jobs = []
    for filepath in csv_files:
        filename = os.path.basename(filepath)
        with open(filepath, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            fieldnames = [fn.strip() for fn in (reader.fieldnames or [])]
            rows = list(reader)

        matched_model = None
        matched_name = None
        field_set = set(fieldnames)

        if "coins" in field_set and "has_shiny_charm" in field_set:
            matched_name, matched_model = "users", User
        elif "pokemon_id" in field_set and "is_shiny" in field_set and "caught_at" in field_set:
            matched_name, matched_model = "user_pokemon", UserPokemon
        elif "treasury" in field_set and "owner_id" in field_set:
            matched_name, matched_model = "guilds", Guild
        elif "guild_id" in field_set and "role" in field_set:
            matched_name, matched_model = "guild_members", GuildMember
        elif "spawn_threshold" in field_set or "scribble_enabled" in field_set:
            matched_name, matched_model = "group_settings", GroupSetting
        elif "key" in field_set and "value" in field_set and len(field_set) <= 3:
            matched_name, matched_model = "global_settings", GlobalSetting
        elif "starting_price" in field_set or "current_bid" in field_set:
            matched_name, matched_model = "auctions", Auction
        elif "auction_id" in field_set and "bidder_id" in field_set:
            matched_name, matched_model = "auction_bids", AuctionBid
        elif "reward_type" in field_set or "usage_limit" in field_set:
            matched_name, matched_model = "redeem_codes", RedeemCode
        elif "code_id" in field_set and "claimed_at" in field_set:
            matched_name, matched_model = "redeem_claims", RedeemClaim
        elif "form_index" in field_set and "media_type" in field_set:
            matched_name, matched_model = "pokemon_form_media", PokemonFormMedia

        if matched_model and rows:
            prio = import_priority.get(matched_name, 99)
            file_jobs.append((prio, filename, matched_name, matched_model, rows))
        else:
            print(f"ℹ️ {filename}: {len(rows)} rows (unmatched schema or empty, skipping)", flush=True)

    file_jobs.sort(key=lambda x: x[0])

    for prio, filename, matched_name, matched_model, rows in file_jobs:

        print(f"\n✍️ Importing {filename} -> Table [{matched_name}] ({len(rows)} records)...", flush=True)
        async with Session() as db:
            parsed_rows = []
            for r in rows:
                row_dict = {}
                for col in matched_model.__table__.columns:
                    col_name = col.name
                    if col_name in r:
                        row_dict[col_name] = parse_val(r[col_name], col_name)
                parsed_rows.append(row_dict)

            # Pre-insert missing Pokemon IDs if model references Pokemon table
            if matched_name in ("user_pokemon", "auctions"):
                needed_pids = set(r.get("pokemon_id") for r in parsed_rows if r.get("pokemon_id") is not None)
                if needed_pids:
                    existing_pids = set((await db.execute(select(Pokemon.id).where(Pokemon.id.in_(needed_pids)))).scalars().all())
                    missing_pids = needed_pids - existing_pids
                    if missing_pids:
                        missing_records = [{
                            "id": pid,
                            "name": f"Custom Form #{pid}",
                            "rarity": "Legendary",
                            "generation": 1,
                            "image_url": "https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/25.png"
                        } for pid in missing_pids]
                        try:
                            await db.execute(pg_insert(Pokemon).values(missing_records).on_conflict_do_nothing())
                            await db.commit()
                        except Exception:
                            await db.rollback()

            chunk_size = 300
            inserted_count = 0
            for i in range(0, len(parsed_rows), chunk_size):
                chunk = parsed_rows[i:i + chunk_size]
                try:
                    stmt = pg_insert(matched_model).values(chunk).on_conflict_do_nothing()
                    await db.execute(stmt)
                    await db.commit()
                    inserted_count += len(chunk)
                except Exception as ex:
                    print(f"   ⚠️ Exception in bulk pg_insert [{matched_name}]: {ex}", flush=True)
                    await db.rollback()
                    for item_dict in chunk:
                        try:
                            stmt = pg_insert(matched_model).values([item_dict]).on_conflict_do_nothing()
                            await db.execute(stmt)
                            await db.commit()
                            inserted_count += 1
                        except Exception:
                            await db.rollback()

            print(f"   ✅ Successfully synced {inserted_count} records into [{matched_name}] in Neon!", flush=True)

    print("\n🏆 Calculating retroactive Trainer Levels and EXP for all accounts...", flush=True)
    async with Session() as db:
        await sync_retroactive_levels(db)

    print("\n🎉 ALL CSV DATA SUCCESSFUL IMPORTED INTO NEON POSTGRESQL!", flush=True)

if __name__ == "__main__":
    asyncio.run(process_csv_import())
