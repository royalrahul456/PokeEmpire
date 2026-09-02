import sys, os
sys.path.append(os.getcwd())
import asyncio
from database.database import SessionLocal
from database.models import User, UserPokemon, ActiveSpawn
from sqlalchemy import select, func

async def test():
    async with SessionLocal() as db:
        try:
            u_count = await db.execute(select(func.count(User.id)))
            total_users = u_count.scalar() or 0
            print("Total users:", total_users)

            c_count = await db.execute(select(func.count(UserPokemon.id)))
            total_catches = c_count.scalar() or 0
            print("Total catches:", total_catches)

            s_count = await db.execute(select(func.count(ActiveSpawn.chat_id)))
            active_spawns = s_count.scalar() or 0
            print("Active spawns:", active_spawns)

            coins_sum = await db.execute(select(func.sum(User.coins)))
            total_coins = coins_sum.scalar() or 0
            print("Total coins:", total_coins)

            shiny_count = await db.execute(select(func.count(UserPokemon.id)).where(UserPokemon.is_shiny == True))
            total_shinies = shiny_count.scalar() or 0
            print("Total shinies:", total_shinies)
        except Exception as e:
            print("Database query failed with error:", e)

if __name__ == "__main__":
    asyncio.run(test())
