import sys, os
sys.path.append(os.getcwd())
import asyncio
from database.database import SessionLocal
from sqlalchemy import select, func
from database.models import User, UserPokemon, ActiveSpawn

async def test():
    async with SessionLocal() as db:
        u_count = await db.execute(select(func.count(User.id)))
        print("total_users:", u_count.scalar())

        c_count = await db.execute(select(func.count(UserPokemon.id)))
        print("total_catches:", c_count.scalar())

        s_count = await db.execute(select(func.count(ActiveSpawn.chat_id)))
        print("active_spawns:", s_count.scalar())

        coins_sum = await db.execute(select(func.sum(User.coins)))
        print("total_coins:", coins_sum.scalar())

        shiny_count = await db.execute(select(func.count(UserPokemon.id)).where(UserPokemon.is_shiny == True))
        print("total_shinies:", shiny_count.scalar())

if __name__ == "__main__":
    asyncio.run(test())
