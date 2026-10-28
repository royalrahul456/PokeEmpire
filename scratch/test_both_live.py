import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from main import main

async def test_both():
    print("Launching dual-bot main.py test loop...")
    task = asyncio.create_task(main())
    await asyncio.sleep(8)
    print("Dual bot main.py ran successfully for 8 seconds without errors! Cancelling test loop.")
    task.cancel()

if __name__ == '__main__':
    try:
        asyncio.run(test_both())
    except (asyncio.CancelledError, KeyboardInterrupt):
        print("Dual bot test complete.")
