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
            data = json.load(f)
            if isinstance(data, list):
                return [str(w).strip().lower() for w in data if isinstance(w, str) and w.strip()]
            return []
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
    if not word or not isinstance(word, str):
        return False
    word = word.strip().lower()
    if not word or len(word) < 2:
        return False
    words = load_ban_words()
    if word in words:
        return False
    words.append(word)
    _save_ban_words(words)
    return True

def remove_ban_word(word: str) -> bool:
    if not word or not isinstance(word, str):
        return False
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
    if not text or not isinstance(text, str):
        return None
    words = load_ban_words()
    if not words:
        return None
    text_lower = text.lower()
    for w in words:
        w_clean = str(w).strip().lower()
        if not w_clean or len(w_clean) < 2:
            continue
        if w_clean in text_lower:
            return w_clean
    return None
