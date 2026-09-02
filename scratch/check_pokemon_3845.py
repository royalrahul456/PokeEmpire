import asyncio
import os
import sys
from sqlalchemy import select

# Adjust path to import from PokeEmpire
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.database import init_db, SessionLocal
from database.models import Pokemon

async def main():
    async with SessionLocal() as db:
        # Get count of total pokemon
        from sqlalchemy import func
        count_res = await db.execute(select(func.count(Pokemon.id)))
        print(f"Total Pokémon: {count_res.scalar()}")
        
        # Check if ID 3845 exists
        stmt = select(Pokemon).where(Pokemon.id == 3845)
        res = await db.execute(stmt)
        p = res.scalar_one_or_none()
        if p:
            print(f"Found Pokémon 3845: Name={p.name}, Gen={p.generation}, Rarity={p.rarity}, Image={p.image_url}")
        else:
            print("Pokémon 3845 not found. Let's list some custom or high-ID Pokémon:")
            stmt = select(Pokemon).order_by(Pokemon.id.desc()).limit(10)
            res = await db.execute(stmt)
            for row in res.scalars().all():
                print(f"ID={row.id}, Name={row.name}, Gen={row.generation}, Rarity={row.rarity}")

if __name__ == "__main__":
    asyncio.run(main())
