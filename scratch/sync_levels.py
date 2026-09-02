import os
import sys
import asyncio

sys.stdout.reconfigure(encoding='utf-8')
os.environ["DATABASE_URL"] = "postgresql://neondb_owner:npg_eanbgOJq19Kv@ep-weathered-cell-ad5waxtl-pooler.c-2.us-east-1.aws.neon.tech/neondb?sslmode=require"
sys.path.append(os.path.abspath("."))

from database.database import SessionLocal, init_db
from utils.trainer_level import sync_retroactive_levels

async def run():
    await init_db()
    async with SessionLocal() as db:
        await sync_retroactive_levels(db)

if __name__ == "__main__":
    asyncio.run(run())
