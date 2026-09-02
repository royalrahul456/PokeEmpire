import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from database.database import SessionLocal
from database.models import Pokemon
from sqlalchemy import select

async def check():
    async with SessionLocal() as s:
        res = await s.execute(select(Pokemon.name, Pokemon.image_url, Pokemon.video_url).limit(10))
        for row in res.all():
            print(row)

if __name__ == "__main__":
    asyncio.run(check())
