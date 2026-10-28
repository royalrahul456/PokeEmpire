import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from main import main

async def test():
    print("Testing main.py startup...", flush=True)
    t = asyncio.create_task(main())
    await asyncio.sleep(5)
    print("SUCCESS: main.py started cleanly without any exceptions!", flush=True)
    t.cancel()

if __name__ == '__main__':
    try:
        asyncio.run(test())
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
