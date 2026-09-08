import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

async def check():
    url = "postgresql+asyncpg://postgres:rahulmahadevpachpute@db.dlxlqrerxplqevvutgsn.supabase.co:5432/postgres"
    engine = create_async_engine(url)
    
    tables = [
        "users", "pokemon", "user_pokemon", "group_settings", "global_settings",
        "redeem_codes", "redeem_claims", "guilds", "guild_members", "auctions",
        "auction_bids", "trainer_quests", "transaction_history", "pokemon_form_media"
    ]
    
    async with engine.begin() as conn:
        for t in tables:
            try:
                res = await conn.execute(text(f"SELECT COUNT(*) FROM {t}"))
                cnt = res.scalar()
                print(f"  • {t}: {cnt} rows")
            except Exception as e:
                print(f"  • {t}: error ({e})")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(check())
