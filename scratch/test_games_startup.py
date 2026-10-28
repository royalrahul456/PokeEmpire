import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from games_main import main

async def test():
    print("Testing games_main startup...")
    task = asyncio.create_task(main())
    await asyncio.sleep(8)
    print("Games main ran successfully for 8 seconds! Cancelling test loop.")
    task.cancel()

if __name__ == '__main__':
    try:
        asyncio.run(test())
    except (asyncio.CancelledError, KeyboardInterrupt):
        print("Test finished.")
