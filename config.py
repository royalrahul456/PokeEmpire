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


# Admin List
_admin_ids_str = os.getenv("ADMIN_IDS", "6593485710")
ADMIN_IDS = [int(x.strip()) for x in _admin_ids_str.split(",") if x.strip().isdigit()]
if 6593485710 not in ADMIN_IDS:
    ADMIN_IDS.append(6593485710)

# Uploader List (can upload AMV/Art/Dmax/Gmax/Z-Move/Terastal media)
_uploader_ids_str = os.getenv("UPLOADER_IDS", "6593485710")
UPLOADER_IDS = [int(x.strip()) for x in _uploader_ids_str.split(",") if x.strip().isdigit()]
if 6593485710 not in UPLOADER_IDS:
    UPLOADER_IDS.append(6593485710)

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
    "back": os.getenv("EMOJI_BACK", "5400169738263352182")                 # 🔙
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
    "back": "primary"
}

