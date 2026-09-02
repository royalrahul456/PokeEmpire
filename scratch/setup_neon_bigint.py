import os
import sys
import asyncio

sys.stdout.reconfigure(encoding='utf-8')
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

url = "postgresql+asyncpg://neondb_owner:npg_eanbgOJq19Kv@ep-weathered-cell-ad5waxtl-pooler.c-2.us-east-1.aws.neon.tech/neondb?ssl=require"

async def run():
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        stmts = [
            "ALTER TABLE users ALTER COLUMN id TYPE BIGINT USING id::BIGINT",
            "ALTER TABLE user_pokemon ALTER COLUMN id TYPE BIGINT USING id::BIGINT",
            "ALTER TABLE user_pokemon ALTER COLUMN user_id TYPE BIGINT USING user_id::BIGINT",
            "ALTER TABLE guilds ALTER COLUMN id TYPE BIGINT USING id::BIGINT",
            "ALTER TABLE guilds ALTER COLUMN owner_id TYPE BIGINT USING owner_id::BIGINT",
            "ALTER TABLE guild_members ALTER COLUMN id TYPE BIGINT USING id::BIGINT",
            "ALTER TABLE guild_members ALTER COLUMN guild_id TYPE BIGINT USING guild_id::BIGINT",
            "ALTER TABLE guild_members ALTER COLUMN user_id TYPE BIGINT USING user_id::BIGINT",
            "ALTER TABLE auctions ALTER COLUMN id TYPE BIGINT USING id::BIGINT",
            "ALTER TABLE auctions ALTER COLUMN seller_id TYPE BIGINT USING seller_id::BIGINT",
            "ALTER TABLE auction_bids ALTER COLUMN id TYPE BIGINT USING id::BIGINT",
            "ALTER TABLE auction_bids ALTER COLUMN auction_id TYPE BIGINT USING auction_id::BIGINT",
            "ALTER TABLE auction_bids ALTER COLUMN bidder_id TYPE BIGINT USING bidder_id::BIGINT",
            "ALTER TABLE redeem_codes ALTER COLUMN id TYPE BIGINT USING id::BIGINT",
            "ALTER TABLE redeem_claims ALTER COLUMN id TYPE BIGINT USING id::BIGINT",
            "ALTER TABLE redeem_claims ALTER COLUMN code_id TYPE BIGINT USING code_id::BIGINT",
            "ALTER TABLE redeem_claims ALTER COLUMN user_id TYPE BIGINT USING user_id::BIGINT",
            "ALTER TABLE pvp_battles ALTER COLUMN id TYPE BIGINT USING id::BIGINT"
        ]
        for s in stmts:
            try:
                await conn.execute(text(s))
                print(f"✅ Executed: {s}")
            except Exception as e:
                print(f"⚠️ {s}: {e}")

if __name__ == "__main__":
    asyncio.run(run())
