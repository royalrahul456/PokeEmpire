import sys
import os
import asyncio

# Configure stdout to use UTF-8 encoding
sys.stdout.reconfigure(encoding='utf-8')

# Setup absolute project path
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(PROJECT_DIR)
os.chdir(PROJECT_DIR)

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select

from database.database import Base, SessionLocal, engine as sqlite_engine
from database.models import User, Pokemon, UserPokemon, ActiveSpawn, GroupSetting

async def migrate_data(postgres_url: str):
    # Ensure correct scheme and SSL parameters for asyncpg
    if postgres_url.startswith("postgresql://"):
        postgres_url = postgres_url.replace("postgresql://", "postgresql+asyncpg://")
    elif not postgres_url.startswith("postgresql+asyncpg://"):
        print("❌ Error: URL must start with postgresql:// or postgresql+asyncpg://")
        return

    if "cockroachlabs" in postgres_url:
        # CockroachDB needs its own dialect
        postgres_url = postgres_url.replace("postgresql://", "cockroachdb+asyncpg://", 1)
        postgres_url = postgres_url.replace("postgresql+asyncpg://", "cockroachdb+asyncpg://", 1)
    
    if "sslmode=" in postgres_url:
        postgres_url = postgres_url.replace("sslmode=require", "ssl=require")
        postgres_url = postgres_url.replace("sslmode=prefer", "ssl=prefer")
        postgres_url = postgres_url.replace("sslmode=verify-full", "ssl=require")
        postgres_url = postgres_url.replace("sslmode=verify-ca", "ssl=require")

    print("🔌 Connecting to PostgreSQL...")
    pg_engine = create_async_engine(postgres_url, echo=False)
    PGSession = sessionmaker(bind=pg_engine, class_=AsyncSession, expire_on_commit=False)

    print("🛠️ Creating tables in PostgreSQL if not exist...")
    async with pg_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("📚 Fetching data from SQLite...")
    async with SessionLocal() as sqlite_session:
        # Fetch all Users
        res = await sqlite_session.execute(select(User))
        users = res.scalars().all()

        # Fetch all Pokemon
        res = await sqlite_session.execute(select(Pokemon))
        pokemons = res.scalars().all()

        # Fetch all UserPokemon
        res = await sqlite_session.execute(select(UserPokemon))
        user_pokemons = res.scalars().all()

        # Fetch all ActiveSpawn
        res = await sqlite_session.execute(select(ActiveSpawn))
        active_spawns = res.scalars().all()

        # Fetch all GroupSetting
        res = await sqlite_session.execute(select(GroupSetting))
        group_settings = res.scalars().all()

    print(f"📊 SQLite Data Summary:")
    print(f"   • Users: {len(users)}")
    print(f"   • Pokemon Species: {len(pokemons)}")
    print(f"   • Caught Pokemon: {len(user_pokemons)}")
    print(f"   • Active Spawns: {len(active_spawns)}")
    print(f"   • Group Settings: {len(group_settings)}")

    print("\n✍️ Writing data to PostgreSQL...")
    async with PGSession() as pg_session:
        # 1. Pokemon Species
        print("   - Copying Pokémon species...")
        res = await pg_session.execute(select(Pokemon.id))
        existing_poke_ids = set(res.scalars().all())
        for p in pokemons:
            if p.id not in existing_poke_ids:
                pg_session.add(Pokemon(
                    id=p.id, name=p.name, rarity=p.rarity,
                    generation=p.generation, image_url=p.image_url
                ))
        await pg_session.flush()

        # 2. Users
        print("   - Copying user profiles...")
        res = await pg_session.execute(select(User.id))
        existing_user_ids = set(res.scalars().all())
        for u in users:
            if u.id not in existing_user_ids:
                pg_session.add(User(
                    id=u.id, username=u.username, nickname=u.nickname,
                    coins=u.coins, last_daily_at=u.last_daily_at,
                    last_spin_at=u.last_spin_at, has_shiny_charm=u.has_shiny_charm,
                    created_at=u.created_at
                ))
        await pg_session.flush()

        # 3. UserPokemon (Caught collection)
        print("   - Copying caught Pokémon...")
        res = await pg_session.execute(select(UserPokemon.id))
        existing_up_ids = set(res.scalars().all())
        for up in user_pokemons:
            if up.id not in existing_up_ids:
                pg_session.add(UserPokemon(
                    id=up.id, user_id=up.user_id, pokemon_id=up.pokemon_id,
                    nickname=up.nickname, is_shiny=up.is_shiny, level=up.level,
                    xp=up.xp, iv_hp=up.iv_hp, iv_atk=up.iv_atk, iv_def=up.iv_def,
                    iv_spd=up.iv_spd, caught_at=up.caught_at
                ))
        await pg_session.flush()

        # 4. Active Spawns
        print("   - Copying active spawns...")
        res = await pg_session.execute(select(ActiveSpawn.chat_id))
        existing_spawn_chats = set(res.scalars().all())
        for asp in active_spawns:
            if asp.chat_id not in existing_spawn_chats:
                pg_session.add(ActiveSpawn(
                    chat_id=asp.chat_id, pokemon_id=asp.pokemon_id,
                    is_shiny=asp.is_shiny, message_id=asp.message_id,
                    spawned_at=asp.spawned_at
                ))
        await pg_session.flush()

        # 5. Group Settings
        print("   - Copying group settings...")
        res = await pg_session.execute(select(GroupSetting.chat_id))
        existing_settings_chats = set(res.scalars().all())
        for gs in group_settings:
            if gs.chat_id not in existing_settings_chats:
                pg_session.add(GroupSetting(
                    chat_id=gs.chat_id, message_counter=gs.message_counter,
                    spawn_threshold=gs.spawn_threshold, enabled=gs.enabled
                ))
        await pg_session.commit()

    print("\n🎉 Database migration complete! All SQLite records have been copied to PostgreSQL.")

if __name__ == "__main__":
    url = input("Enter your cloud PostgreSQL database URL: ").strip()
    if not url:
        print("❌ URL cannot be empty.")
        sys.exit(1)
    
    # Run migration
    asyncio.run(migrate_data(url))
