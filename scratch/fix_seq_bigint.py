import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

url = "postgresql+asyncpg://neondb_owner:npg_eanbgOJq19Kv@ep-weathered-cell-ad5waxtl-pooler.c-2.us-east-1.aws.neon.tech/neondb?ssl=require"

async def run():
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        seq_stmts = [
            "ALTER SEQUENCE IF EXISTS user_pokemon_id_seq AS BIGINT MAXVALUE 9223372036854775807",
            "SELECT setval('user_pokemon_id_seq', COALESCE((SELECT MAX(id) FROM user_pokemon), 0) + 1, false)",
            "ALTER SEQUENCE IF EXISTS guilds_id_seq AS BIGINT MAXVALUE 9223372036854775807",
            "SELECT setval('guilds_id_seq', COALESCE((SELECT MAX(id) FROM guilds), 0) + 1, false)",
            "ALTER SEQUENCE IF EXISTS guild_members_id_seq AS BIGINT MAXVALUE 9223372036854775807",
            "SELECT setval('guild_members_id_seq', COALESCE((SELECT MAX(id) FROM guild_members), 0) + 1, false)",
            "ALTER SEQUENCE IF EXISTS auctions_id_seq AS BIGINT MAXVALUE 9223372036854775807",
            "SELECT setval('auctions_id_seq', COALESCE((SELECT MAX(id) FROM auctions), 0) + 1, false)",
            "ALTER SEQUENCE IF EXISTS auction_bids_id_seq AS BIGINT MAXVALUE 9223372036854775807",
            "SELECT setval('auction_bids_id_seq', COALESCE((SELECT MAX(id) FROM auction_bids), 0) + 1, false)",
            "ALTER SEQUENCE IF EXISTS redeem_codes_id_seq AS BIGINT MAXVALUE 9223372036854775807",
            "SELECT setval('redeem_codes_id_seq', COALESCE((SELECT MAX(id) FROM redeem_codes), 0) + 1, false)",
            "ALTER SEQUENCE IF EXISTS redeem_claims_id_seq AS BIGINT MAXVALUE 9223372036854775807",
            "SELECT setval('redeem_claims_id_seq', COALESCE((SELECT MAX(id) FROM redeem_claims), 0) + 1, false)"
        ]
        for s in seq_stmts:
            try:
                res = await conn.execute(text(s))
                print(f"✅ Executed: {s}")
            except Exception as e:
                print(f"⚠️ {s}: {e}")

if __name__ == "__main__":
    asyncio.run(run())
