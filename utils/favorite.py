import os
import json
from typing import Optional

FAVORITES_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "user_favorites.json")

def get_favorite_id(user_id: int) -> Optional[int]:
    """Get the database ID of the user's favorite cover Pokémon."""
    if not os.path.exists(FAVORITES_FILE):
        return None
    try:
        with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            val = data.get(str(user_id))
            return int(val) if val is not None else None
    except Exception:
        return None

def set_favorite_id(user_id: int, up_id: Optional[int]):
    """Set or clear (if up_id is None) the favorite cover Pokémon for a user."""
    os.makedirs(os.path.dirname(FAVORITES_FILE), exist_ok=True)
    data = {}
    if os.path.exists(FAVORITES_FILE):
        try:
            with open(FAVORITES_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            pass
    
    u_str = str(user_id)
    if up_id is None:
        if u_str in data:
            del data[u_str]
    else:
        data[u_str] = up_id
        
    try:
        with open(FAVORITES_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception:
        pass
