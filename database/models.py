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
    current_streak = Column(Integer, default=0, nullable=False)
    best_streak = Column(Integer, default=0, nullable=False)
    last_secured_date = Column(String(20), nullable=True)
    last_catch_date = Column(String(20), nullable=True)
    catches_today = Column(Integer, default=0, nullable=False)
    trainer_level = Column(Integer, default=1, nullable=False)
    trainer_xp = Column(Integer, default=0, nullable=False)
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
    video_url = Column(String(255), nullable=True)
    dmax_url = Column(String(255), nullable=True)
    gmax_url = Column(String(255), nullable=True)
    zmove_url = Column(String(255), nullable=True)
    terastal_url = Column(String(255), nullable=True)

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
    is_amv = Column(Boolean, default=False, nullable=False)
    form_index = Column(Integer, default=0, nullable=False)
    serial_number = Column(String(20), nullable=True)
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
    scribble_enabled = Column(Boolean, default=True, nullable=False)
    nameguess_enabled = Column(Boolean, default=True, nullable=False)

class GlobalSetting(Base):
    __tablename__ = "global_settings"

    key = Column(String(100), primary_key=True)
    value = Column(String(1000), nullable=False)


class RedeemCode(Base):
    __tablename__ = "redeem_codes"

    id = Column(Integer, primary_key=True, autoincrement=True)
    code = Column(String(50), unique=True, nullable=False)
    reward_type = Column(String(20), nullable=False)  # "coins" or "pokemon"
    reward_value = Column(Integer, nullable=True)     # coin amount or pokemon_id
    reward_is_shiny = Column(Boolean, default=False, nullable=False)
    reward_is_amv = Column(Boolean, default=False, nullable=False)
    reward_form_index = Column(Integer, default=0, nullable=False)
    usage_limit = Column(Integer, default=1, nullable=False)
    usage_count = Column(Integer, default=0, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)


class RedeemClaim(Base):
    __tablename__ = "redeem_claims"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    code_id = Column(Integer, ForeignKey("redeem_codes.id", ondelete="CASCADE"), nullable=False)
    claimed_at = Column(DateTime, default=func.now(), nullable=False)


class PokemonFormMedia(Base):
    __tablename__ = "pokemon_form_media"

    pokemon_id = Column(Integer, ForeignKey("pokemon.id", ondelete="CASCADE"), primary_key=True)
    form_index = Column(Integer, primary_key=True)
    media_value = Column(String(255), nullable=False)


class PvpBattle(Base):
    __tablename__ = "pvp_battles"
    id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(BigInteger, nullable=False)
    message_id = Column(BigInteger, nullable=False)
    challenger_id = Column(BigInteger, nullable=False)
    opponent_id = Column(BigInteger, nullable=False)
    bet = Column(Integer, default=0, nullable=False)
    format_type = Column(Integer, default=3, nullable=False)  # 3 or 6 Pokemon
    status = Column(String(50), default="WAITING", nullable=False)
    draft_json = Column(String(4000), nullable=True)
    created_at = Column(DateTime, default=func.now(), nullable=False)


class Auction(Base):
    __tablename__ = "auctions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    seller_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    pokemon_id = Column(Integer, ForeignKey("pokemon.id", ondelete="CASCADE"), nullable=False)
    nickname = Column(String(100), nullable=True)
    is_shiny = Column(Boolean, default=False, nullable=False)
    is_amv = Column(Boolean, default=False, nullable=False)
    form_index = Column(Integer, default=0, nullable=False)
    serial_number = Column(String(20), nullable=True)
    level = Column(Integer, default=1, nullable=False)
    xp = Column(Integer, default=0, nullable=False)
    iv_hp = Column(Integer, default=0, nullable=False)
    iv_atk = Column(Integer, default=0, nullable=False)
    iv_def = Column(Integer, default=0, nullable=False)
    iv_spd = Column(Integer, default=0, nullable=False)

    starting_price = Column(Integer, nullable=False)
    current_bid = Column(Integer, default=0, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)
    status = Column(String(20), default="ACTIVE", nullable=False)  # "ACTIVE", "COMPLETED", "CANCELLED"
    channel_message_id = Column(BigInteger, nullable=True)
    channel_chat_id = Column(BigInteger, nullable=True)

    # Relationships
    pokemon = relationship("Pokemon")
    seller = relationship("User", foreign_keys=[seller_id])


class AuctionBid(Base):
    __tablename__ = "auction_bids"

    id = Column(Integer, primary_key=True, autoincrement=True)
    auction_id = Column(Integer, ForeignKey("auctions.id", ondelete="CASCADE"), nullable=False)
    bidder_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Integer, nullable=False)
    bid_at = Column(DateTime, default=func.now(), nullable=False)

    # Relationships
    bidder = relationship("User", foreign_keys=[bidder_id])


class ChatMessageStat(Base):
    __tablename__ = "chat_message_stats"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    chat_id = Column(BigInteger, nullable=False, index=True)
    daily_count = Column(Integer, default=0, nullable=False)
    weekly_count = Column(Integer, default=0, nullable=False)
    monthly_count = Column(Integer, default=0, nullable=False)
    overall_count = Column(Integer, default=0, nullable=False)
    last_daily_reset = Column(String(20), nullable=True)   # "YYYY-MM-DD"
    last_weekly_reset = Column(String(20), nullable=True)  # "YYYY-WW"
    last_monthly_reset = Column(String(20), nullable=True) # "YYYY-MM"

    # Relationships
    user = relationship("User", foreign_keys=[user_id])


class Guild(Base):
    __tablename__ = "guilds"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    tag = Column(String(10), unique=True, nullable=False)
    owner_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    treasury = Column(Integer, default=0, nullable=False)
    level = Column(Integer, default=1, nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    owner = relationship("User", foreign_keys=[owner_id])


class GuildMember(Base):
    __tablename__ = "guild_members"

    id = Column(Integer, primary_key=True, autoincrement=True)
    guild_id = Column(Integer, ForeignKey("guilds.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    role = Column(String(20), default="member", nullable=False)  # "leader", "co_leader", "member"
    joined_at = Column(DateTime, default=func.now(), nullable=False)

    guild = relationship("Guild")
    user = relationship("User", foreign_keys=[user_id])


class TrainerQuest(Base):
    __tablename__ = "trainer_quests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    quest_key = Column(String(50), nullable=False)
    progress = Column(Integer, default=0, nullable=False)
    target = Column(Integer, nullable=False)
    is_claimed = Column(Boolean, default=False, nullable=False)
    period = Column(String(20), default="daily", nullable=False)  # "daily", "weekly"
    created_at = Column(DateTime, default=func.now(), nullable=False)


class TransactionHistory(Base):
    __tablename__ = "transaction_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(BigInteger, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    amount = Column(Integer, nullable=False)  # positive for gain, negative for spent
    category = Column(String(50), nullable=False)
    description = Column(String(255), nullable=False)
    created_at = Column(DateTime, default=func.now(), nullable=False)

    user = relationship("User", foreign_keys=[user_id])


class MysteryEventState(Base):
    __tablename__ = "mystery_event_state"

    key = Column(String(50), primary_key=True)
    value = Column(String(500), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)




