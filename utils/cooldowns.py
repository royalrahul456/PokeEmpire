from datetime import datetime, timedelta
from typing import Dict, Tuple

class CooldownManager:
    def __init__(self):
        # Maps (user_id, action) -> expiry_datetime
        self._cooldowns: Dict[Tuple[int, str], datetime] = {}

    def get_remaining_time(self, user_id: int, action: str) -> float:
        """Returns remaining seconds for action cooldown. Returns 0.0 if expired or not set."""
        key = (user_id, action)
        expiry = self._cooldowns.get(key)
        if not expiry:
            return 0.0
        
        now = datetime.now()
        if now >= expiry:
            # Clean up expired entry
            self._cooldowns.pop(key, None)
            return 0.0
            
        return (expiry - now).total_seconds()

    def set_cooldown(self, user_id: int, action: str, seconds: int):
        """Sets a cooldown for a specific user action."""
        key = (user_id, action)
        self._cooldowns[key] = datetime.now() + timedelta(seconds=seconds)

    def trigger_action(self, user_id: int, action: str, seconds: int) -> Tuple[bool, int]:
        """Tries to trigger an action. If on cooldown, returns (False, seconds_remaining).
        Otherwise sets the cooldown and returns (True, 0).
        """
        remaining = self.get_remaining_time(user_id, action)
        if remaining > 0.0:
            return False, int(remaining) + 1
        
        self.set_cooldown(user_id, action, seconds)
        return True, 0

    def clear_cooldown(self, user_id: int, action: str):
        """Clears a cooldown immediately (e.g. if an operation fails and shouldn't penalize)."""
        self._cooldowns.pop((user_id, action), None)

# Global singleton instance
cooldowns = CooldownManager()
