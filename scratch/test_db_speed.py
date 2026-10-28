import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import time
from database.database import init_db
import config

async def main():
    print(f"DATABASE_URL: {config.DATABASE_URL}")
    t0 = time.time()
    print("Initializing DB...")
    await init_db()
    print(f"DB initialized in {time.time() - t0:.2f} seconds.")

if __name__ == '__main__':
    asyncio.run(main())
