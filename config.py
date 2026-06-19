import os
from dotenv import load_dotenv

# Load variables from .env file
load_dotenv()

# Bot Setup
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# Resolve relative SQLite database URL to absolute path relative to this config file's directory
_raw_db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///pokeempire.db")
if _raw_db_url.startswith("sqlite+aiosqlite:///"):
    _db_rel_path = _raw_db_url.replace("sqlite+aiosqlite:///", "")
    _base_dir = os.path.dirname(os.path.abspath(__file__))
    if not os.path.isabs(_db_rel_path):
        DATABASE_URL = f"sqlite+aiosqlite:///{os.path.join(_base_dir, _db_rel_path)}"
    else:
        DATABASE_URL = _raw_db_url
else:
    DATABASE_URL = _raw_db_url

# Admin List
_admin_ids_str = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(x.strip()) for x in _admin_ids_str.split(",") if x.strip().isdigit()]

# Game Configuration Defaults
SHINY_RATE = float(os.getenv("SHINY_RATE", "0.002"))
HUNT_COOLDOWN = int(os.getenv("HUNT_COOLDOWN", "30"))
WORK_COOLDOWN = int(os.getenv("WORK_COOLDOWN", "3600"))
DAILY_REWARD_COINS = int(os.getenv("DAILY_REWARD_COINS", "250"))
DAILY_REWARD_GEMS = int(os.getenv("DAILY_REWARD_GEMS", "5"))

# Optional Telegram proxy (e.g. http://proxy.server:3128)
_raw_proxy = os.getenv("TELEGRAM_PROXY", None)
if _raw_proxy:
    # Strip any inline comments and whitespaces
    _clean_proxy = _raw_proxy.split("#")[0].strip()
    TELEGRAM_PROXY = _clean_proxy if _clean_proxy else None
else:
    TELEGRAM_PROXY = None


# Directories
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DATABASE_PATH = os.path.join(BASE_DIR, "pokeempire.db")
