import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import asyncio
from database.database import SessionLocal
from database.models import Pokemon
from sqlalchemy import select, func

async def check():
    async with SessionLocal() as s:
        res = await s.execute(select(Pokemon.rarity, func.count(Pokemon.id)).group_by(Pokemon.rarity))
        print("Rarity counts:", res.all())
        total = await s.execute(select(func.count(Pokemon.id)))
        print("Total pokemon:", total.scalar())

if __name__ == "__main__":
    asyncio.run(check())
