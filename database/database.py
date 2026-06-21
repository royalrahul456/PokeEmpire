from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy import select, text
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
        from database.models import User, Pokemon, UserPokemon, ActiveSpawn, GroupSetting, GlobalSetting, PokemonFormMedia, PvpBattle
        await conn.run_sync(Base.metadata.create_all)

    # Run migrations for existing databases
    async with engine.begin() as conn:
        # Group Settings toggles
        for col in ["scribble_enabled", "nameguess_enabled"]:
            try:
                if "postgresql" in DATABASE_URL:
                    await conn.execute(text(f"ALTER TABLE group_settings ADD COLUMN IF NOT EXISTS {col} BOOLEAN DEFAULT true"))
                else:
                    await conn.execute(text(f"ALTER TABLE group_settings ADD COLUMN {col} BOOLEAN DEFAULT true"))
                print(f"✅ Migrated database: added {col} column to group_settings")
            except Exception:
                pass

        # Pokemon table custom media column
        try:
            if "postgresql" in DATABASE_URL:
                await conn.execute(text("ALTER TABLE pokemon ADD COLUMN IF NOT EXISTS video_url VARCHAR(255)"))
            else:
                await conn.execute(text("ALTER TABLE pokemon ADD COLUMN video_url VARCHAR(255)"))
            print("✅ Migrated database: added video_url column to pokemon")
        except Exception:
            pass

        # Pokemon table new form media columns
        for col in ["dmax_url", "gmax_url", "zmove_url", "terastal_url"]:
            try:
                if "postgresql" in DATABASE_URL:
                    await conn.execute(text(f"ALTER TABLE pokemon ADD COLUMN IF NOT EXISTS {col} VARCHAR(255)"))
                else:
                    await conn.execute(text(f"ALTER TABLE pokemon ADD COLUMN {col} VARCHAR(255)"))
                print(f"✅ Migrated database: added {col} column to pokemon")
            except Exception:
                pass

        # User Pokemon table AMV indicator and serial number columns
        try:
            if "postgresql" in DATABASE_URL:
                await conn.execute(text("ALTER TABLE user_pokemon ADD COLUMN IF NOT EXISTS is_amv BOOLEAN DEFAULT false"))
            else:
                await conn.execute(text("ALTER TABLE user_pokemon ADD COLUMN is_amv BOOLEAN DEFAULT false"))
            print("✅ Migrated database: added is_amv column to user_pokemon")
        except Exception:
            pass

        try:
            if "postgresql" in DATABASE_URL:
                await conn.execute(text("ALTER TABLE user_pokemon ADD COLUMN IF NOT EXISTS form_index INTEGER DEFAULT 0"))
            else:
                await conn.execute(text("ALTER TABLE user_pokemon ADD COLUMN form_index INTEGER DEFAULT 0"))
            print("✅ Migrated database: added form_index column to user_pokemon")
        except Exception:
            pass

        try:
            if "postgresql" in DATABASE_URL:
                await conn.execute(text("ALTER TABLE user_pokemon ADD COLUMN IF NOT EXISTS serial_number VARCHAR(20)"))
            else:
                await conn.execute(text("ALTER TABLE user_pokemon ADD COLUMN serial_number VARCHAR(20)"))
            print("✅ Migrated database: added serial_number column to user_pokemon")
        except Exception:
            pass

        # Redeem Codes table reward_form_index column
        try:
            if "postgresql" in DATABASE_URL:
                await conn.execute(text("ALTER TABLE redeem_codes ADD COLUMN IF NOT EXISTS reward_form_index INTEGER DEFAULT 0"))
            else:
                await conn.execute(text("ALTER TABLE redeem_codes ADD COLUMN reward_form_index INTEGER DEFAULT 0"))
            print("✅ Migrated database: added reward_form_index column to redeem_codes")
        except Exception:
            pass

    # Migrate existing AMV data to pokemon_form_media
    async with SessionLocal() as session:
        try:
            from database.models import Pokemon, PokemonFormMedia, UserPokemon
            stmt = select(Pokemon).where(Pokemon.video_url.is_not(None))
            res = await session.execute(stmt)
            pokes_with_amv = res.scalars().all()
            for p in pokes_with_amv:
                media_stmt = select(PokemonFormMedia).where(PokemonFormMedia.pokemon_id == p.id, PokemonFormMedia.form_index == 1)
                media_res = await session.execute(media_stmt)
                if media_res.scalar_one_or_none() is None:
                    val = p.video_url
                    if not val.startswith("video:") and not val.startswith("photo:"):
                        val = f"video:{val}"
                    session.add(PokemonFormMedia(pokemon_id=p.id, form_index=1, media_value=val))
            
            up_stmt = select(UserPokemon).where(UserPokemon.is_amv == True, UserPokemon.form_index == 0)
            up_res = await session.execute(up_stmt)
            ups_to_migrate = up_res.scalars().all()
            for up in ups_to_migrate:
                up.form_index = 1
                
            await session.commit()
        except Exception as e:
            print(f"⚠️ AMV migration error: {e}")


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

    # Fix PostgreSQL sequences that may be out of sync after migration from SQLite
    # This prevents UniqueViolationError on user_pokemon.id
    if "postgresql" in DATABASE_URL:
        async with engine.begin() as conn:
            await conn.execute(text(
                "SELECT setval('user_pokemon_id_seq', "
                "COALESCE((SELECT MAX(id) FROM user_pokemon), 0) + 1, false)"
            ))
            print("✅ PostgreSQL sequences reset successfully")

async def get_db():
    """Dependency helper to retrieve an active database session."""
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
