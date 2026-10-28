import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import config

async def test():
    print("1. Loading database...", flush=True)
    from database.database import init_db, engine
    print("2. DATABASE_URL is:", config.DATABASE_URL, flush=True)
    print("3. Calling init_db()...", flush=True)
    await init_db()
    print("4. init_db() done!", flush=True)

if __name__ == "__main__":
    asyncio.run(test())
