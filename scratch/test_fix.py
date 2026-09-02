import re, sys

sys.stdout.reconfigure(encoding='utf-8')

HTML_TAG_PATTERN = re.compile(r'</?(?:b|i|u|s|code|pre|a|blockquote|tg-emoji|span)\b[^>]*>', re.IGNORECASE)

EMOJI_MAPPING = {'🪙': '5382164415019768638'}

def replace_emojis(text):
    for emoji, eid in EMOJI_MAPPING.items():
        if emoji in text:
            text = text.replace(emoji, f'<tg-emoji emoji-id="{eid}">{emoji}</tg-emoji>')
    return text

def test_process(text, parse_mode):
    if HTML_TAG_PATTERN.search(text):
        text = replace_emojis(text)
        return text, 'HTML'
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = replace_emojis(text)
    return text, 'HTML'

print('Test HTML text:', test_process('<b>Coins</b>: 500 🪙', 'Markdown'))
print('Test Markdown text:', test_process('**Coins**: 500 🪙', 'Markdown'))
