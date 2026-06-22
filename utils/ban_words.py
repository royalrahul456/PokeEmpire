import os
import json
from config import DATA_DIR

BAN_WORDS_FILE = os.path.join(DATA_DIR, "ban_words.json")

def load_ban_words() -> list:
    if not os.path.exists(BAN_WORDS_FILE):
        # Default empty list or basic starting list if desired
        return []
    try:
        with open(BAN_WORDS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def _save_ban_words(words: list):
    os.makedirs(os.path.dirname(BAN_WORDS_FILE), exist_ok=True)
    try:
        with open(BAN_WORDS_FILE, "w", encoding="utf-8") as f:
            json.dump(words, f, indent=4)
    except Exception as e:
        print(f"Error saving ban words: {e}")

def add_ban_word(word: str) -> bool:
    word = word.strip().lower()
    if not word:
        return False
    words = load_ban_words()
    if word in words:
        return False
    words.append(word)
    _save_ban_words(words)
    return True

def remove_ban_word(word: str) -> bool:
    word = word.strip().lower()
    if not word:
        return False
    words = load_ban_words()
    if word not in words:
        return False
    words.remove(word)
    _save_ban_words(words)
    return True

def check_text_for_ban_words(text: str) -> str or None:
    """
    Checks if a string contains any of the banned words (case-insensitive).
    Returns the first banned word found, or None.
    """
    if not text:
        return None
    words = load_ban_words()
    text_lower = text.lower()
    for w in words:
        # Check as a substring or with word boundary
        # A simple substring check is more secure against basic bypasses
        if w in text_lower:
            return w
    return None
