import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import asyncio

async def test():
    print("Testing imports and main/games_main syntax after git pull...", flush=True)
    import main
    import games_main
    print("✅ Successfully imported main.py and games_main.py!", flush=True)

if __name__ == '__main__':
    asyncio.run(test())
