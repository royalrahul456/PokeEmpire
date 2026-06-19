from sqlalchemy import Column, Integer, BigInteger, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from database.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(BigInteger, primary_key=True)  # Telegram User ID
    username = Column(String(100), nullable=True)
    nickname = Column(String(100), nullable=True)
    coins = Column(Integer, default=500, nullable=False)
    last_daily_at = Column(DateTime, nullable=True)
    last_spin_at = Column(DateTime, nullable=True)
    has_shiny_charm = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    pokemon_collection = relationship("UserPokemon", back_populates="user", cascade="all, delete-orphan")

class Pokemon(Base):
    __tablename__ = "pokemon"

    id = Column(Integer, primary_key=True)  # PokeAPI ID (e.g. 1 for Bulbasaur)
    name = Column(String(100), unique=True, nullable=False)  # Lowercase name
    rarity = Column(String(50), nullable=False)  # Common, Rare, Epic, Legendary, Mythical
    generation = Column(Integer, default=1, nullable=False)
    image_url = Column(String(255), nullable=False)

    # Relationships
    user_captures = relationship("UserPokemon", back_populates="pokemon")
    active_spawns = relationship("ActiveSpawn", back_populates="pokemon")

class UserPokemon(Base):
    __tablename__ = "user_pokemon"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    pokemon_id = Column(Integer, ForeignKey("pokemon.id", ondelete="CASCADE"), nullable=False)
    nickname = Column(String(100), nullable=True)
    is_shiny = Column(Boolean, default=False, nullable=False)
    level = Column(Integer, default=1, nullable=False)
    xp = Column(Integer, default=0, nullable=False)
    iv_hp = Column(Integer, default=0, nullable=False)
    iv_atk = Column(Integer, default=0, nullable=False)
    iv_def = Column(Integer, default=0, nullable=False)
    iv_spd = Column(Integer, default=0, nullable=False)
    caught_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    user = relationship("User", back_populates="pokemon_collection")
    pokemon = relationship("Pokemon", back_populates="user_captures")

class ActiveSpawn(Base):
    __tablename__ = "active_spawn"

    chat_id = Column(BigInteger, primary_key=True)  # Group Chat ID
    pokemon_id = Column(Integer, ForeignKey("pokemon.id", ondelete="CASCADE"), nullable=False)
    is_shiny = Column(Boolean, default=False, nullable=False)
    message_id = Column(BigInteger, nullable=True)  # ID of spawn message
    spawned_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    pokemon = relationship("Pokemon", back_populates="active_spawns")

class GroupSetting(Base):
    __tablename__ = "group_settings"

    chat_id = Column(BigInteger, primary_key=True)  # Group Chat ID
    message_counter = Column(Integer, default=0, nullable=False)
    spawn_threshold = Column(Integer, default=100, nullable=False)  # Threshold (30-300)
    enabled = Column(Boolean, default=True, nullable=False)
