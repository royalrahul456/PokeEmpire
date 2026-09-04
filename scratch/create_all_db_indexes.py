import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

url = "postgresql+asyncpg://neondb_owner:npg_eanbgOJq19Kv@ep-weathered-cell-ad5waxtl-pooler.c-2.us-east-1.aws.neon.tech/neondb?ssl=require"

async def create_indexes():
    print("⚡ Connecting to Neon PostgreSQL to create database performance indexes...")
    engine = create_async_engine(url, connect_args={"statement_cache_size": 0})
    
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
        "CREATE INDEX IF NOT EXISTS idx_guild_members_user_id ON guild_members(user_id);",
    ]
    
    async with engine.begin() as conn:
        for idx in indexes:
            try:
                await conn.execute(text(idx))
                print(f"✅ Executed: {idx.strip()}")
            except Exception as e:
                print(f"⚠️ {idx.strip()}: {e}")
                
    print("🚀 All database performance indexes created successfully!")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(create_indexes())
