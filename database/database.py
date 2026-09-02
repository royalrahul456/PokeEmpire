import sys
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy import select, text
from config import DATABASE_URL

def safe_print(msg: str):
    try:
        print(msg)
    except Exception:
        try:
            print(msg.encode('ascii', 'ignore').decode('ascii'))
        except Exception:
            pass

# Configure the Async Engine with pooling options for PostgreSQL / CockroachDB
if "postgresql" in DATABASE_URL or "cockroachdb" in DATABASE_URL:
    engine = create_async_engine(
        DATABASE_URL,
        pool_size=20,
        max_overflow=30,
        pool_recycle=1800,
        pool_timeout=30,
        pool_pre_ping=True
    )
else:
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
    """Initialize the database, creating all tables and seeding Pokémon list. Falls back to SQLite if cloud DB fails."""
    global engine, SessionLocal
    try:
        async with engine.begin() as conn:
            from database.models import User, Pokemon, UserPokemon, ActiveSpawn, GroupSetting, GlobalSetting, PokemonFormMedia, PvpBattle, Auction, AuctionBid, ChatMessageStat, Guild, GuildMember, TrainerQuest, TransactionHistory, MysteryEventState, BugReport
            await conn.run_sync(Base.metadata.create_all)
    except Exception as e:
        safe_print(f"⚠️ Primary Database connection failed ({e}). Falling back to local SQLite database...")
        fallback_url = "sqlite+aiosqlite:///pokeempire.db"
        engine = create_async_engine(fallback_url, connect_args={"check_same_thread": False}, pool_pre_ping=True)
        SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
        async with engine.begin() as conn:
            from database.models import User, Pokemon, UserPokemon, ActiveSpawn, GroupSetting, GlobalSetting, PokemonFormMedia, PvpBattle, Auction, AuctionBid, ChatMessageStat, Guild, GuildMember, TrainerQuest, TransactionHistory, MysteryEventState, BugReport
            await conn.run_sync(Base.metadata.create_all)

    # Run migrations for existing databases in a single fast batched query
    async with engine.begin() as conn:
        try:
            if "postgresql" in DATABASE_URL or "cockroachdb" in DATABASE_URL:
                ddl_statements = [
                    "ALTER TABLE group_settings ADD COLUMN IF NOT EXISTS scribble_enabled BOOLEAN DEFAULT true",
                    "ALTER TABLE group_settings ADD COLUMN IF NOT EXISTS nameguess_enabled BOOLEAN DEFAULT true",
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS current_streak INTEGER DEFAULT 0",
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS best_streak INTEGER DEFAULT 0",
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_secured_date VARCHAR(20)",
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS last_catch_date VARCHAR(20)",
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS catches_today INTEGER DEFAULT 0",
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS trainer_level INTEGER DEFAULT 1",
                    "ALTER TABLE users ADD COLUMN IF NOT EXISTS trainer_xp INTEGER DEFAULT 0",
                    "ALTER TABLE pokemon ADD COLUMN IF NOT EXISTS video_url VARCHAR(255)",
                    "ALTER TABLE pokemon ADD COLUMN IF NOT EXISTS dmax_url VARCHAR(255)",
                    "ALTER TABLE pokemon ADD COLUMN IF NOT EXISTS gmax_url VARCHAR(255)",
                    "ALTER TABLE pokemon ADD COLUMN IF NOT EXISTS zmove_url VARCHAR(255)",
                    "ALTER TABLE pokemon ADD COLUMN IF NOT EXISTS terastal_url VARCHAR(255)",
                    "ALTER TABLE user_pokemon ADD COLUMN IF NOT EXISTS is_amv BOOLEAN DEFAULT false",
                    "ALTER TABLE user_pokemon ADD COLUMN IF NOT EXISTS form_index INTEGER DEFAULT 0",
                    "ALTER TABLE user_pokemon ADD COLUMN IF NOT EXISTS serial_number VARCHAR(20)",
                    "ALTER TABLE redeem_codes ADD COLUMN IF NOT EXISTS reward_form_index INTEGER DEFAULT 0"
                ]
                for ddl in ddl_statements:
                    try:
                        await conn.execute(text(ddl))
                    except Exception:
                        pass
                safe_print("✅ Database schema columns verified & migrated successfully!")
            else:
                for col in ["scribble_enabled", "nameguess_enabled"]:
                    try: await conn.execute(text(f"ALTER TABLE group_settings ADD COLUMN {col} BOOLEAN DEFAULT true"))
                    except Exception: pass
                streak_cols = [("current_streak", "INTEGER DEFAULT 0"), ("best_streak", "INTEGER DEFAULT 0"), ("last_secured_date", "VARCHAR(20)"), ("last_catch_date", "VARCHAR(20)"), ("catches_today", "INTEGER DEFAULT 0"), ("trainer_level", "INTEGER DEFAULT 1"), ("trainer_xp", "INTEGER DEFAULT 0")]
                for col, col_type in streak_cols:
                    try: await conn.execute(text(f"ALTER TABLE users ADD COLUMN {col} {col_type}"))
                    except Exception: pass
                try: await conn.execute(text("ALTER TABLE pokemon ADD COLUMN video_url VARCHAR(255)"))
                except Exception: pass
                for col in ["dmax_url", "gmax_url", "zmove_url", "terastal_url"]:
                    try: await conn.execute(text(f"ALTER TABLE pokemon ADD COLUMN {col} VARCHAR(255)"))
                    except Exception: pass
                for col, col_type in [("is_amv", "BOOLEAN DEFAULT false"), ("form_index", "INTEGER DEFAULT 0"), ("serial_number", "VARCHAR(20)")]:
                    try: await conn.execute(text(f"ALTER TABLE user_pokemon ADD COLUMN {col} {col_type}"))
                    except Exception: pass
                try: await conn.execute(text("ALTER TABLE redeem_codes ADD COLUMN reward_form_index INTEGER DEFAULT 0"))
                except Exception: pass
        except Exception as ex:
            safe_print(f"Schema migration check completed: {ex}")

    # Migrate existing AMV data to pokemon_form_media
    async with SessionLocal() as session:
        try:
            from database.models import Pokemon, PokemonFormMedia, UserPokemon
            stmt = select(Pokemon).where(Pokemon.video_url.is_not(None))
            res = await session.execute(stmt)
            pokes_with_amv = res.scalars().all()
            existing_media = set((await session.execute(select(PokemonFormMedia.pokemon_id).where(PokemonFormMedia.form_index == 1))).scalars().all())
            for p in pokes_with_amv:
                if p.id not in existing_media:
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
            safe_print(f"⚠️ AMV migration error: {e}")


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
                safe_print(f"🌱 Seeding Pokémon from backup file: {json_path}")
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
                safe_print("🌱 Seeding fallback starter list...")
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

    # Fix PostgreSQL sequences that may be out of sync after migration from CockroachDB / SQLite
    if "postgresql" in DATABASE_URL or "cockroachdb" in DATABASE_URL:
        async with engine.begin() as conn:
            try:
                await conn.execute(text("ALTER SEQUENCE IF EXISTS user_pokemon_id_seq AS BIGINT MAXVALUE 9223372036854775807"))
                await conn.execute(text("SELECT setval('user_pokemon_id_seq', COALESCE((SELECT MAX(id) FROM user_pokemon), 0) + 1, false)"))
                safe_print("✅ PostgreSQL sequences reset successfully")
            except Exception as ex:
                safe_print(f"Sequence reset check completed: {ex}")

async def get_db():
    """Dependency helper to retrieve an active database session."""
    async with SessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
