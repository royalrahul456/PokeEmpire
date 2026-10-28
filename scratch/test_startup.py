import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
import logging

logging.basicConfig(level=logging.INFO)

async def test_main():
    print("--- TESTING MAIN.PY IMPORT & ROUTERS ---")
    import main
    print("Main imports OK!")

async def test_games_main():
    print("--- TESTING GAMES_MAIN.PY IMPORT & ROUTERS ---")
    import games_main
    print("Games main imports OK!")

if __name__ == "__main__":
    asyncio.run(test_main())
    asyncio.run(test_games_main())
    print("--- ALL IMPORTS & ROUTERS ARE VALID ---")
