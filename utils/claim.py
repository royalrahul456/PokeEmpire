import os
import json
import time
from config import DATA_DIR

CLAIMS_FILE = os.path.join(DATA_DIR, "claims.json")

def _load_claims() -> dict:
    if not os.path.exists(CLAIMS_FILE):
        return {}
    try:
        with open(CLAIMS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_claims(claims: dict):
    os.makedirs(os.path.dirname(CLAIMS_FILE), exist_ok=True)
    try:
        with open(CLAIMS_FILE, "w", encoding="utf-8") as f:
            json.dump(claims, f, indent=4)
    except Exception as e:
        print(f"Error saving claims: {e}")

def check_claim_cooldown(user_id: int) -> int:
    """
    Returns the remaining seconds of the 24-hour claim cooldown for a user.
    If the user can claim, returns 0.
    """
    claims = _load_claims()
    user_str = str(user_id)
    if user_str not in claims:
        return 0
    
    last_claim_time = claims[user_str]
    now = time.time()
    elapsed = now - last_claim_time
    cooldown_seconds = 24 * 3600 # 24 hours
    
    if elapsed >= cooldown_seconds:
        return 0
    else:
        return int(cooldown_seconds - elapsed)

def update_claim_cooldown(user_id: int):
    """
    Updates the user's last claim time to the current timestamp.
    """
    claims = _load_claims()
    claims[str(user_id)] = time.time()
    _save_claims(claims)
