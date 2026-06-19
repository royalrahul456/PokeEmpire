from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy import select
from config import DATABASE_URL

# Configure the SQLite Async Engine
engine = create_async_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    pool_pre_ping=True
)

# Create a session factory
SessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

# 30+ Pokémon seed list
SEED_POKEMON = [
    # Common (11)
    (1, "bulbasaur", "Common", 1),
    (4, "charmander", "Common", 1),
    (7, "squirtle", "Common", 1),
    (10, "caterpie", "Common", 1),
    (16, "pidgey", "Common", 1),
    (19, "rattata", "Common", 1),
    (41, "zubat", "Common", 1),
    (43, "oddish", "Common", 1),
    (50, "diglett", "Common", 1),
    (52, "meowth", "Common", 1),
    (54, "psyduck", "Common", 1),
    # Rare (7)
    (25, "pikachu", "Rare", 1),
    (133, "eevee", "Rare", 1),
    (58, "growlithe", "Rare", 1),
    (63, "abra", "Rare", 1),
    (92, "gastly", "Rare", 1),
    (66, "machop", "Rare", 1),
    (77, "ponyta", "Rare", 1),
    # Epic (7)
    (3, "venusaur", "Epic", 1),
    (6, "charizard", "Epic", 1),
    (9, "blastoise", "Epic", 1),
    (130, "gyarados", "Epic", 1),
    (143, "snorlax", "Epic", 1),
    (148, "dragonair", "Epic", 1),
    (94, "gengar", "Epic", 1),
    # Legendary (5)
    (144, "articuno", "Legendary", 1),
    (145, "zapdos", "Legendary", 1),
    (146, "moltres", "Legendary", 1),
    (150, "mewtwo", "Legendary", 1),
    (249, "lugia", "Legendary", 2),
    # Mythical (2)
    (151, "mew", "Mythical", 1),
    (251, "celebi", "Mythical", 2)
]

async def init_db():
    """Initialize the SQLite database, creating all tables and seeding Pokémon list if empty."""
    async with engine.begin() as conn:
        from database.models import User, Pokemon, UserPokemon, ActiveSpawn, GroupSetting
        await conn.run_sync(Base.metadata.create_all)

    # Seed the Pokémon table if empty
    async with SessionLocal() as session:
        from database.models import Pokemon
        stmt = select(Pokemon).limit(1)
        res = await session.execute(stmt)
        if res.scalar_one_or_none() is None:
            import os
            import json
            import config
            
            json_path = os.path.join(config.DATA_DIR, "pokemon_seeds.json")
            if os.path.exists(json_path):
                print(f"🌱 Seeding Pokémon from backup file: {json_path}")
                with open(json_path, "r", encoding="utf-8") as f:
                    poke_records = json.load(f)
                for r in poke_records:
                    db_poke = Pokemon(
                        id=r["id"],
                        name=r["name"],
                        rarity=r["rarity"],
                        generation=r["generation"],
                        image_url=r["image_url"]
                    )
                    session.add(db_poke)
            else:
                print("🌱 Seeding fallback starter list...")
                for p_id, name, rarity, gen in SEED_POKEMON:
                    img_url = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/other/official-artwork/{p_id}.png"
                    db_poke = Pokemon(
                        id=p_id,
                        name=name,
                        rarity=rarity,
                        generation=gen,
                        image_url=img_url
                    )
                    session.add(db_poke)
            await session.commit()

async def get_db():
    """Dependency helper to retrieve an active database session."""
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
