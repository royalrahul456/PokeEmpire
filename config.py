import os
import sys
from dotenv import load_dotenv

# Polyfill imghdr for Python 3.13+ compatibility
try:
    import imghdr
except ImportError:
    import imghdr  # Will import imghdr.py polyfill in current directory

# Load variables from .env file
load_dotenv()

# Bot Setup
BOT_TOKEN = os.getenv("BOT_TOKEN", "")

WEBAPP_URL = os.getenv("WEBAPP_URL", "https://royalrahul456.github.io/PokeEmpire/webapp/")

# Default Supabase IPv4 Pooler PostgreSQL URL (Transaction Mode on port 6543 for unlimited connections)
SUPABASE_DB_URL = "postgresql://postgres.dlxlqrerxplqevvutgsn:rahulmahadevpachpute@aws-0-ap-southeast-2.pooler.supabase.com:6543/postgres"

# Check if we are running in Render with persistent volume mount
PERSISTENT_VOLUME = "/app/data_volume"
_env_db = os.getenv("DATABASE_URL", "")

# Auto-migrate away from expired CockroachDB/Neon URLs or empty DATABASE_URL to Supabase IPv4 Pooler
if not _env_db or "cockroachlabs" in _env_db or "neon.tech" in _env_db or _env_db == "sqlite+aiosqlite:///pokeempire.db":
    _raw_db_url = SUPABASE_DB_URL
else:
    _raw_db_url = _env_db

def _format_db_url(url: str) -> str:
    if url.startswith("sqlite+aiosqlite:///"):
        return url
    db_url = url

    # Clean up any previously duplicated port fragments
    while ":6543:6543" in db_url or ":6543:5432" in db_url or ":5432:6543" in db_url:
        db_url = db_url.replace(":6543:6543", ":6543")
        db_url = db_url.replace(":6543:5432", ":6543")
        db_url = db_url.replace(":5432:6543", ":6543")

    # Auto-convert direct IPv6 host to IPv4 pooler host for cloud hosts like Render
    if "db.dlxlqrerxplqevvutgsn.supabase.co" in db_url:
        db_url = db_url.replace("db.dlxlqrerxplqevvutgsn.supabase.co", "aws-0-ap-southeast-2.pooler.supabase.com")
        db_url = db_url.replace("postgres:rahulmahadevpachpute", "postgres.dlxlqrerxplqevvutgsn:rahulmahadevpachpute")

    # Force port 6543 for Supabase pooler
    if "pooler.supabase.com" in db_url:
        db_url = db_url.replace(":5432", ":6543")

    if "cockroachlabs" in db_url:
        db_url = db_url.replace("postgresql://", "cockroachdb+asyncpg://", 1)
        db_url = db_url.replace("postgresql+asyncpg://", "cockroachdb+asyncpg://", 1)
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    elif db_url.startswith("postgres://"):
        db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)

    if "sslmode=" in db_url:
        db_url = db_url.replace("sslmode=require", "ssl=require")
        db_url = db_url.replace("sslmode=prefer", "ssl=prefer")
        db_url = db_url.replace("sslmode=verify-full", "ssl=require")
        db_url = db_url.replace("sslmode=verify-ca", "ssl=require")
    
    if "channel_binding=" in db_url:
        import re
        db_url = re.sub(r'[&?]channel_binding=[^&]*', '', db_url)

    return db_url

if os.path.exists(PERSISTENT_VOLUME) and os.path.isdir(PERSISTENT_VOLUME):
    if _raw_db_url.startswith("sqlite+aiosqlite:///"):
        DATABASE_URL = "sqlite+aiosqlite:////app/data_volume/pokeempire.db"
    else:
        DATABASE_URL = _format_db_url(_raw_db_url)
else:
    if _raw_db_url.startswith("sqlite+aiosqlite:///"):
        _db_rel_path = _raw_db_url.replace("sqlite+aiosqlite:///", "")
        _base_dir = os.path.dirname(os.path.abspath(__file__))
        if not os.path.isabs(_db_rel_path):
            DATABASE_URL = f"sqlite+aiosqlite:///{os.path.join(_base_dir, _db_rel_path)}"
        else:
            DATABASE_URL = _raw_db_url
    else:
        DATABASE_URL = _format_db_url(_raw_db_url)


# Owner List
OWNER_IDS = [6593485710]

# Developer List
_dev_ids_str = os.getenv("DEV_IDS", os.getenv("DEVELOPER_IDS", "8984041700"))
DEV_IDS = [int(x.strip()) for x in _dev_ids_str.split(",") if x.strip().isdigit()]
if 8984041700 not in DEV_IDS:
    DEV_IDS.append(8984041700)

# Admin / Bot Controller List
_admin_ids_str = os.getenv("ADMIN_IDS", "6593485710")
ADMIN_IDS = [int(x.strip()) for x in _admin_ids_str.split(",") if x.strip().isdigit()]
for _id in OWNER_IDS + DEV_IDS:
    if _id not in ADMIN_IDS:
        ADMIN_IDS.append(_id)

# Uploader List (can upload AMV/Art/Dmax/Gmax/Z-Move/Terastal media)
_uploader_ids_str = os.getenv("UPLOADER_IDS", "6593485710,8984041700")
UPLOADER_IDS = [int(x.strip()) for x in _uploader_ids_str.split(",") if x.strip().isdigit()]
for _id in OWNER_IDS + DEV_IDS:
    if _id not in UPLOADER_IDS:
        UPLOADER_IDS.append(_id)

# Game Configuration Defaults
SHINY_RATE = float(os.getenv("SHINY_RATE", "0.002"))
HUNT_COOLDOWN = int(os.getenv("HUNT_COOLDOWN", "30"))
WORK_COOLDOWN = int(os.getenv("WORK_COOLDOWN", "3600"))
DAILY_REWARD_COINS = int(os.getenv("DAILY_REWARD_COINS", "250"))
DAILY_REWARD_GEMS = int(os.getenv("DAILY_REWARD_GEMS", "5"))
ENABLE_PREMIUM_EMOJIS = os.getenv("ENABLE_PREMIUM_EMOJIS", "true").lower() == "true"

# Optional Telegram proxy (e.g. http://proxy.server:3128)
_raw_proxy = os.getenv("TELEGRAM_PROXY", None)
if _raw_proxy:
    # Strip any inline comments and whitespaces
    _clean_proxy = _raw_proxy.split("#")[0].strip()
    TELEGRAM_PROXY = _clean_proxy if _clean_proxy else None
else:
    TELEGRAM_PROXY = None


# Directories
if os.path.exists(PERSISTENT_VOLUME) and os.path.isdir(PERSISTENT_VOLUME):
    BASE_DIR = PERSISTENT_VOLUME
    DATA_DIR = "/app/data_volume/data"
    DATABASE_PATH = "/app/data_volume/pokeempire.db"
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    DATABASE_PATH = os.path.join(BASE_DIR, "pokeempire.db")
UPDATES_CHANNEL = os.getenv("UPDATES_CHANNEL", "@pokeempireupdates")
DATABASE_CHANNEL = os.getenv("DATABASE_CHANNEL", "@pokeempiredatabase")
AUCTION_CHANNEL = os.getenv("AUCTION_CHANNEL", "@PokeEmpireAuctions")

# Telegram Custom Emoji IDs for Native Inline Buttons (configurable)
CUSTOM_EMOJI_IDS = {
    "add_to_group": os.getenv("EMOJI_ADD_TO_GROUP", "5372926953978341366"), # 👥 / ➕
    "updates": os.getenv("EMOJI_UPDATES", "5789428375261023681"),          # 📢
    "support": os.getenv("EMOJI_SUPPORT", "5377599075237502153"),          # 🎫 / 🎟️
    "help": os.getenv("EMOJI_HELP", "5436113877181941026"),                # ❓
    "stats": os.getenv("EMOJI_STATS", "5231200819986047254"),               # 📊
    "profile": os.getenv("EMOJI_PROFILE", "5373012449597335010"),          # 👤
    "pokedex": os.getenv("EMOJI_POKEDEX", "5188344996356448758"),          # 🏆
    "quests": os.getenv("EMOJI_QUESTS", "5453991094435997597"),            # ⚔️
    "guilds": os.getenv("EMOJI_GUILDS", "5449918202718985124"),            # 🏰
    "bag": os.getenv("EMOJI_BAG", "5409234219496907243"),                  # 🎒
    "leaderboard": os.getenv("EMOJI_LEADERBOARD", "5282950412784117735"),  # 📈
    "battle": os.getenv("EMOJI_BATTLE", "5251203410396458957"),            # 🛡️
    "trade": os.getenv("EMOJI_TRADE", "6122764622509380932"),              # 🔄
    "redeem": os.getenv("EMOJI_REDEEM", "5203996991054432397"),            # 🎁
    "shop": os.getenv("EMOJI_SHOP", "5312361253610475399"),                # 🛒
    "games": os.getenv("EMOJI_GAMES", "5255765065096774716"),              # 🎰
    "streak": os.getenv("EMOJI_STREAK", "5424972470023104089"),            # 🔥
    "panel": os.getenv("EMOJI_PANEL", "5433758796289685818"),              # 👑
    "tools": os.getenv("EMOJI_TOOLS", "5461047575379466857"),              # 🛠️
    "back": os.getenv("EMOJI_BACK", "5400169738263352182"),                 # 🔙
    "catch": os.getenv("EMOJI_CATCH", "5188344996356448758"),              # ⚾ / 🏆
    "auction": os.getenv("EMOJI_AUCTION", "5203996991054432397"),          # 🔨
    "confirm": os.getenv("EMOJI_CONFIRM", "5424972470023104089"),          # ✅
    "cancel": os.getenv("EMOJI_CANCEL", "5400169738263352182"),            # ❌
    "refresh": os.getenv("EMOJI_REFRESH", "5461047575379466857"),          # 🔄
    "claim": os.getenv("EMOJI_CLAIM", "5203996991054432397"),              # 🎁
    "prev": os.getenv("EMOJI_PREV", "5400169738263352182"),                # ◀️
    "next": os.getenv("EMOJI_NEXT", "5400169738263352182"),                # ▶️
    "hint": os.getenv("EMOJI_HINT", "5436113877181941026"),                # 🔍
    "buy": os.getenv("EMOJI_BUY", "5312361253610475399"),                  # 🛒
    "info": os.getenv("EMOJI_INFO", "5436113877181941026"),                # ℹ️
}

# Native Telegram Button Color Styles ("primary" = blue, "success" = green, "danger" = red)
BUTTON_STYLES = {
    "add_to_group": os.getenv("STYLE_ADD_TO_GROUP", "primary"),
    "updates": os.getenv("STYLE_UPDATES", "primary"),
    "support": os.getenv("STYLE_SUPPORT", "primary"),
    "help": os.getenv("STYLE_HELP", "danger"),
    "stats": os.getenv("STYLE_STATS", "success"),
    "profile": "primary",
    "pokedex": "success",
    "quests": "danger",
    "guilds": "primary",
    "bag": "success",
    "leaderboard": "primary",
    "battle": "danger",
    "trade": "primary",
    "redeem": "success",
    "shop": "primary",
    "games": "primary",
    "streak": "danger",
    "panel": "danger",
    "tools": "primary",
    "back": "primary",
    "catch": "success",
    "auction": "primary",
    "confirm": "success",
    "cancel": "danger",
    "refresh": "primary",
    "claim": "success",
    "prev": "primary",
    "next": "primary",
    "hint": "primary",
    "buy": "success",
    "info": "primary",
}

