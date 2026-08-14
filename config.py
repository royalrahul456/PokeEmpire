import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

# Bot Setup
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Check if we are running in Render with persistent volume mount
PERSISTENT_VOLUME = "/app/data_volume"
_raw_db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///pokeempire.db")

def _format_db_url(url: str) -> str:
    if url.startswith("sqlite+aiosqlite:///"):
        return url
    db_url = url
    if "cockroachlabs" in db_url:
        db_url = db_url.replace("postgresql://", "cockroachdb+asyncpg://", 1)
        db_url = db_url.replace("postgresql+asyncpg://", "cockroachdb+asyncpg://", 1)
    elif db_url.startswith("postgresql://"):
        db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)

    if "sslmode=" in db_url:
        db_url = db_url.replace("sslmode=require", "ssl=require")
        db_url = db_url.replace("sslmode=prefer", "ssl=prefer")
        db_url = db_url.replace("sslmode=verify-full", "ssl=require")
        db_url = db_url.replace("sslmode=verify-ca", "ssl=require")
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


# Admin List
_admin_ids_str = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in _admin_ids_str.split(",") if x.strip().isdigit()]

# Uploader List (can upload AMV/Art/Dmax/Gmax/Z-Move/Terastal media)
_uploader_ids_str = os.getenv("UPLOADER_IDS", "")
UPLOADER_IDS = [int(x.strip()) for x in _uploader_ids_str.split(",") if x.strip().isdigit()]

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
