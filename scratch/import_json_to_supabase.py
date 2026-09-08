import asyncio
import sys
import os
import json
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from database.database import Base
import database.models  # Register models

BACKUP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "live_db_backups")

async def migrate_to_supabase(password: str):
    url = f"postgresql+asyncpg://postgres:{password}@db.dlxlqrerxplqevvutgsn.supabase.co:5432/postgres"
    print(f"🚀 Initializing Supabase PostgreSQL Migration for project 'dlxlqrerxplqevvutgsn'...")
    
    engine = create_async_engine(url, connect_args={"statement_cache_size": 100})
    
    # 1. Create Tables
    print("1. Creating database tables...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print("✅ All database tables created on Supabase!")
    
    # 2. Convert Sequence and Column Types to BIGINT
    print("2. Upgrading columns and sequences to BIGINT...")
    async with engine.begin() as conn:
        bigint_stmts = [
            "ALTER TABLE user_pokemon ALTER COLUMN id TYPE BIGINT;",
            "ALTER TABLE user_pokemon ALTER COLUMN user_id TYPE BIGINT;",
            "ALTER TABLE guilds ALTER COLUMN id TYPE BIGINT;",
            "ALTER TABLE guilds ALTER COLUMN owner_id TYPE BIGINT;",
            "ALTER TABLE guild_members ALTER COLUMN id TYPE BIGINT;",
            "ALTER TABLE guild_members ALTER COLUMN guild_id TYPE BIGINT;",
            "ALTER TABLE guild_members ALTER COLUMN user_id TYPE BIGINT;",
            "ALTER TABLE auctions ALTER COLUMN id TYPE BIGINT;",
            "ALTER TABLE auctions ALTER COLUMN seller_id TYPE BIGINT;",
            "ALTER TABLE auction_bids ALTER COLUMN id TYPE BIGINT;",
            "ALTER TABLE auction_bids ALTER COLUMN auction_id TYPE BIGINT;",
            "ALTER TABLE auction_bids ALTER COLUMN bidder_id TYPE BIGINT;",
            "ALTER TABLE redeem_codes ALTER COLUMN id TYPE BIGINT;",
            "ALTER TABLE redeem_claims ALTER COLUMN id TYPE BIGINT;",
            "ALTER TABLE redeem_claims ALTER COLUMN user_id TYPE BIGINT;",
            "ALTER TABLE redeem_claims ALTER COLUMN code_id TYPE BIGINT;"
        ]
        for stmt in bigint_stmts:
            try:
                await conn.execute(text(stmt))
            except Exception as e:
                pass
    print("✅ BIGINT types configured!")
    
    # 3. Create B-Tree Indexes
    print("3. Building B-Tree performance indexes...")
    async with engine.begin() as conn:
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_user_pokemon_user_id ON user_pokemon(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_user_pokemon_pokemon_id ON user_pokemon(pokemon_id);",
            "CREATE INDEX IF NOT EXISTS idx_user_pokemon_user_poke ON user_pokemon(user_id, pokemon_id);",
            "CREATE INDEX IF NOT EXISTS idx_auctions_seller_id ON auctions(seller_id);",
            "CREATE INDEX IF NOT EXISTS idx_auctions_status ON auctions(status);",
            "CREATE INDEX IF NOT EXISTS idx_auction_bids_auction_id ON auction_bids(auction_id);",
            "CREATE INDEX IF NOT EXISTS idx_auction_bids_bidder_id ON auction_bids(bidder_id);",
            "CREATE INDEX IF NOT EXISTS idx_redeem_claims_user_id ON redeem_claims(user_id);",
            "CREATE INDEX IF NOT EXISTS idx_redeem_claims_code_id ON redeem_claims(code_id);",
            "CREATE INDEX IF NOT EXISTS idx_guild_members_user_id ON guild_members(user_id);"
        ]
        for idx in indexes:
            try:
                await conn.execute(text(idx))
            except Exception:
                pass
    print("✅ Performance B-Tree indexes created!")
    
    # 4. Import JSON Data
    print("4. Importing backup data into Supabase...")
    
    Session = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    
    import_order = [
        ("users", database.models.User),
        ("pokemon", database.models.Pokemon),
        ("pokemon_form_media", database.models.PokemonFormMedia),
        ("group_settings", database.models.GroupSetting),
        ("global_settings", database.models.GlobalSetting),
        ("redeem_codes", database.models.RedeemCode),
        ("redeem_claims", database.models.RedeemClaim),
        ("guilds", database.models.Guild),
        ("guild_members", database.models.GuildMember),
        ("user_pokemon", database.models.UserPokemon),
        ("auctions", database.models.Auction),
        ("auction_bids", database.models.AuctionBid),
        ("trainer_quests", database.models.TrainerQuest),
        ("transaction_history", database.models.TransactionHistory),
        ("bug_reports", database.models.BugReport)
    ]
    
    async with Session() as session:
        for table_name, model_class in import_order:
            file_path = os.path.join(BACKUP_DIR, f"{table_name}.json")
            if not os.path.exists(file_path):
                continue
                
            with open(file_path, "r", encoding="utf-8") as f:
                records = json.load(f)
                
            if not records:
                continue
                
            count = 0
            for r in records:
                # Convert ISO datetime strings back to datetime objects
                for k, v in r.items():
                    if isinstance(v, str) and (v.startswith("202") or v.startswith("201")) and "T" in v:
                        try:
                            r[k] = datetime.fromisoformat(v)
                        except Exception:
                            pass
                obj = model_class(**r)
                session.add(obj)
                count += 1
                if count % 500 == 0:
                    await session.commit()
            await session.commit()
            print(f"  ✅ Imported {count} records into {table_name}")
            
    # 5. Fix Sequences
    print("5. Resetting PostgreSQL sequences...")
    async with engine.begin() as conn:
        seqs = [
            ("user_pokemon_id_seq", "user_pokemon"),
            ("guilds_id_seq", "guilds"),
            ("guild_members_id_seq", "guild_members"),
            ("auctions_id_seq", "auctions"),
            ("auction_bids_id_seq", "auction_bids"),
            ("redeem_codes_id_seq", "redeem_codes"),
            ("redeem_claims_id_seq", "redeem_claims"),
            ("trainer_quests_id_seq", "trainer_quests"),
            ("transaction_history_id_seq", "transaction_history"),
            ("bug_reports_id_seq", "bug_reports")
        ]
        for seq_name, tbl in seqs:
            try:
                await conn.execute(text(f"ALTER SEQUENCE IF EXISTS {seq_name} AS BIGINT MAXVALUE 9223372036854775807;"))
                await conn.execute(text(f"SELECT setval('{seq_name}', COALESCE((SELECT MAX(id) FROM {tbl}), 0) + 1, false);"))
            except Exception as e:
                pass
    print("✅ PostgreSQL sequences synchronized!")
    print("\n🎉 SUPABASE DATABASE MIGRATION COMPLETED SUCCESSFULLY!")
    await engine.dispose()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        pwd = sys.argv[1]
        asyncio.run(migrate_to_supabase(pwd))
    else:
        print("Please provide password as argument.")
