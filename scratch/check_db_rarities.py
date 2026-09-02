import asyncio
from sqlalchemy import select, func
from database.database import SessionLocal
from database.models import Pokemon

async def check():
    async with SessionLocal() as db:
        stmt = select(Pokemon.rarity, func.count(Pokemon.id)).group_by(Pokemon.rarity)
        res = await db.execute(stmt)
        for rarity, count in res.all():
            print(f"Rarity: {rarity} | Count: {count}")

if __name__ == '__main__':
    asyncio.run(check())
