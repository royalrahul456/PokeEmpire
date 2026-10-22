import os
import json
import time
from config import DATA_DIR

CLAIMS_FILE = os.path.join(DATA_DIR, "claims.json")
VIP_CLAIMS_FILE = os.path.join(DATA_DIR, "vip_claims.json")

def _load_claims(file_path: str = CLAIMS_FILE) -> dict:
    if not os.path.exists(file_path):
        return {}
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_claims(claims: dict, file_path: str = CLAIMS_FILE):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(claims, f, indent=4)
    except Exception as e:
        print(f"Error saving claims to {file_path}: {e}")

def check_claim_cooldown(user_id: int) -> int:
    """
    Returns the remaining seconds of the 24-hour claim cooldown for a user.
    If the user can claim, returns 0.
    """
    claims = _load_claims(CLAIMS_FILE)
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
    claims = _load_claims(CLAIMS_FILE)
    claims[str(user_id)] = time.time()
    _save_claims(claims, CLAIMS_FILE)


def check_vip_claim_cooldown(user_id: int) -> int:
    """
    Returns remaining seconds of the 24-hour VIP claim cooldown.
    Returns 0 if user is eligible to claim.
    """
    claims = _load_claims(VIP_CLAIMS_FILE)
    user_str = str(user_id)
    if user_str not in claims:
        return 0

    last_claim_time = claims[user_str]
    now = time.time()
    elapsed = now - last_claim_time
    cooldown_seconds = 24 * 3600

    if elapsed >= cooldown_seconds:
        return 0
    else:
        return int(cooldown_seconds - elapsed)


def update_vip_claim_cooldown(user_id: int):
    """Updates the user's last VIP claim time to the current timestamp."""
    claims = _load_claims(VIP_CLAIMS_FILE)
    claims[str(user_id)] = time.time()
    _save_claims(claims, VIP_CLAIMS_FILE)
