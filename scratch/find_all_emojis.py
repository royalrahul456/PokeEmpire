import os
import re
import sys
import unicodedata

# Define directories to scan
DIRS_TO_SCAN = ['handlers', 'utils', 'services', 'database', 'main.py']

def scan_file(filepath):
    found_emojis = set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except Exception:
        try:
            with open(filepath, 'r', encoding='cp1252') as f:
                content = f.read()
        except Exception:
            return found_emojis

    # Find all matches of emojis or non-ascii symbols
    for char in content:
        code = ord(char)
        # Skip standard ASCII
        if code < 128:
            continue
        
        # Skip common Latin-1 characters (like smart quotes, degrees, copyright, registered, currency, etc. up to 0xFF)
        if code <= 0xFF:
            continue

        cat = unicodedata.category(char)
        # We want to look for symbols (S), punctuation (P), marks (M), etc.
        # But exclude standard layout formatting characters or standard quotes.
        # Let's check name for typical emoji/symbol indicators.
        try:
            name = unicodedata.name(char)
        except ValueError:
            name = "UNKNOWN"

        # Exclude standard CJK or non-symbol characters
        # Emojis generally live in symbols, punctuation, or other symbols
        if cat.startswith('S') or cat.startswith('P') or cat.startswith('M') or code >= 0x2000:
            # Let's filter out standard layout symbols like EM DASH (0x2014), smart quotes, bullets etc.
            if code in (0x2013, 0x2014, 0x2018, 0x2019, 0x201C, 0x201D, 0x2022, 0x2026, 0x2190, 0x2192, 0x2500, 0x2502):
                continue
            found_emojis.add(char)
                
    return found_emojis

def main():
    all_found = {}
    for root_dir in DIRS_TO_SCAN:
        if os.path.isfile(root_dir):
            emojis = scan_file(root_dir)
            if emojis:
                all_found[root_dir] = emojis
        elif os.path.exists(root_dir):
            for root, _, files in os.walk(root_dir):
                for file in files:
                    if file.endswith('.py'):
                        filepath = os.path.join(root, file)
                        emojis = scan_file(filepath)
                        if emojis:
                            relpath = os.path.relpath(filepath)
                            all_found[relpath] = emojis

    # Aggregate by emoji
    emoji_to_files = {}
    for filepath, emojis in all_found.items():
        for em in emojis:
            emoji_to_files.setdefault(em, []).append(filepath)

    output_lines = []
    output_lines.append("=== EMOJI SCAN RESULTS ===")
    for em, files in sorted(emoji_to_files.items()):
        try:
            name = unicodedata.name(em)
        except ValueError:
            name = "UNKNOWN"
        output_lines.append(f"EMOJI: {em} | HEX: \\U{ord(em):08X} | NAME: {name} | FILES: {len(files)} ({', '.join(files[:3])})")

    # Write output as UTF-8 to a file
    output_path = os.path.join('scratch', 'found_emojis.txt')
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(output_lines))
    print(f"Success! Output written to {output_path}")

if __name__ == '__main__':
    main()
