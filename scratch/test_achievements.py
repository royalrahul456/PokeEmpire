import sys
import os
import asyncio

# Add current directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from utils.streak import DATA_FILE

print(f"DEBUG: DATA_FILE path is: {DATA_FILE}")
expected_path = os.path.join(config.DATA_DIR, "user_streaks.json")
if DATA_FILE == expected_path:
    print("✅ Success: DATA_FILE resolved to config.DATA_DIR correctly!")
else:
    print(f"❌ Error: DATA_FILE resolved to {DATA_FILE}, expected {expected_path}")

def get_achievement_bar(current: int, target: int) -> str:
    fraction = min(1.0, max(0.0, current / target))
    filled_length = int(fraction * 8)
    empty_length = 8 - filled_length
    return f"[{'█' * filled_length}{'░' * empty_length}]"

# Test progress bar logic
print("\nTesting Progress Bar Calculations:")
test_cases = [
    (1307, 5000),   # Legend
    (1307, 10000),  # Grand Master
    (1307, 25000),  # Mythic Snatchers
    (0, 100),       # First Blood (no progress)
    (100, 100),     # First Blood (unlocked)
    (99, 100),      # First Blood (nearly unlocked)
]

for current, target in test_cases:
    bar = get_achievement_bar(current, target)
    print(f"Current: {current:5d} | Target: {target:5d} | Bar: {bar}")

print("\nAll checks completed!")
