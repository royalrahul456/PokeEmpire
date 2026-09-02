import sys, os
sys.path.append(os.getcwd())
import asyncio
from database.database import SessionLocal
from utils.settings import load_all_settings_into_cache, get_custom_cover, global_settings_cache

async def test():
    await load_all_settings_into_cache()
    print("global_settings_cache keys:", list(global_settings_cache.keys()))
    print("custom cover start:", get_custom_cover("start"))

if __name__ == "__main__":
    asyncio.run(test())
