import os
import json
from typing import Optional

FAVORITES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "user_favorites.json")

def get_favorite_id(user_id: int) -> Optional[str]:
    """Get the string ID (e.g. '6' or '6.1') of the user's favorite cover Pokémon."""
    if not os.path.exists(FAVORITES_FILE):
        return None
    try:
        with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            val = data.get(str(user_id))
            return str(val) if val is not None else None
    except Exception:
        return None

def set_favorite_id(user_id: int, fav_val: Optional[str]):
    """Set or clear (if fav_val is None) the favorite cover Pokémon for a user."""
    os.makedirs(os.path.dirname(FAVORITES_FILE), exist_ok=True)
    data = {}
    if os.path.exists(FAVORITES_FILE):
        try:
            with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    
    u_str = str(user_id)
    if fav_val is None:
        if u_str in data:
            del data[u_str]
    else:
        data[u_str] = str(fav_val)
        
    try:
        with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception:
        pass
