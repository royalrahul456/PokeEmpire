# -*- coding: utf-8 -*-
import re
from aiogram import Bot
from aiogram.enums import ParseMode
from aiogram.methods import (
    SendMessage,
    EditMessageText,
    SendPhoto,
    SendVideo,
    SendAnimation,
    SendAudio,
    SendDocument,
    EditMessageCaption
)

# Standard emoji to Premium Custom Emoji ID mapping
EMOJI_MAPPING = {
    # Coins & Money
    "🪙": "5382164415019768638",
    "💰": "5287231198098117669",
    "💳": "5445353829304387411",
    "💸": "5864068125112144897",
    "👑": "5433758796289685818",
    "🏆": "5188344996356448758",
    "🥇": "5440539497383087970",
    "🥈": "5447203607294265305",
    "🥉": "5453902265922376865",

    # Success, Stats & Statuses
    "🎉": "5461151367559141950",
    "🔥": "5424972470023104089",
    "⭐": "5438496463044752972",
    "⭐️": "5438496463044752972",
    "✨": "5325547803936572038",
    "✨️": "5325547803936572038",
    "🧬": "5431884253518375171",
    "💥": "5240492311716054039",
    "⚠️": "5420323339723881652",
    "⏳": "5269539162654010758",
    "⏱️": "5382194935057372936",
    "⏱": "5382194935057372936",
    "🔴": "5411225014148014586",
    "❌": "5210952531676504517",
    "⛔": "5260293700088511294",

    # Games
    "❓": "5436113877181941026",
    "💡": "5323743114513373152",
    "✏️": "5213305971891248967",
    "✏": "5213305971891248967",
    "💬": "5224617957971206703",
    "🔀": "5222151079080246525",
    "🧠": "5377510010500699911",
    "💭": "5411199759740325999",
    "💣": "5454225015534805938",
    "💎": "5197350061012436657",
    "🎰": "5255765065096774716",
    "🎡": "5841461384361023405",

    # Shop & Utils
    "📦": "5449800250032143374",
    "🎁": "5203996991054432397",
    "🛒": "5312361253610475399",
    "🌲": "5906705309136589768",
    "📢": "5789428375261023681",
    "📖": "5449660075184508972",

    # Rarities
    "🎱": "5289940334619406906",
    "🔵": "4965219701572503640",
    "🟣": "5197368799954738967",
    "🟡": "6005661956931850799",
    "🌌": "5812392946917445652",

    # Forms
    "📺": "5371074616187969568",
    "🖼️": "5895427227528467580",
    "🖼": "5895427227528467580",
    "⚡": "5411590687663608498",
    "⚡️": "5411590687663608498",
    "🌀": "5825951969692357786"
}

ALL_EMOJIS_SET = set(EMOJI_MAPPING.keys()) | {"🟢", "🔮"}

def markdown_to_html(text: str) -> str:
    """Converts basic Markdown formatting (bold, italic, code, links) to Telegram HTML format."""
    if not isinstance(text, str) or not text:
        return text
    
    # Escape HTML tags first as we're translating from plain text markdown
    text = text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    
    # Bold **text** or __text__
    text = re.sub(r'\*\*(.*?)\*\*|__(.*?)__', lambda m: f"<b>{m.group(1) or m.group(2)}</b>", text)
    
    # Italic *text* or _text_
    text = re.sub(r'\*(.*?)\*|_(.*?)_', lambda m: f"<i>{m.group(1) or m.group(2)}</i>", text)
    
    # Monospace `text`
    text = re.sub(r'`(.*?)`', lambda m: f"<code>{m.group(1)}</code>", text)
    
    # Links [label](url)
    text = re.sub(r'\[(.*?)\]\((.*?)\)', lambda m: f'<a href="{m.group(2)}">{m.group(1)}</a>', text)
    
    return text

def replace_emojis(text: str) -> str:
    """Replaces standard Unicode emojis in a text string with their custom <tg-emoji> equivalent tags."""
    if not isinstance(text, str) or not text:
        return text
    
    # 1. Contextual Replacements first
    # 🟢 (Green Circle)
    if "🟢" in text:
        if "Uncommon" in text:
            eid = "5416081784641168838"  # Rarities version
        else:
            eid = "5215522595922779944"  # Statuses/stats version
        text = text.replace("🟢", f'<tg-emoji emoji-id="{eid}">🟢</tg-emoji>')

    # 🔮 (Crystal Ball)
    if "🔮" in text:
        if "Terastal" in text or "Form 6.5" in text:
            eid = "5244955049024581265"  # Terastal Form version
        else:
            eid = "5271810272640643747"  # Epic Rarity version
        text = text.replace("🔮", f'<tg-emoji emoji-id="{eid}">🔮</tg-emoji>')

    # 2. Iterate through mapping
    for emoji, eid in EMOJI_MAPPING.items():
        if emoji in text:
            tag = f'<tg-emoji emoji-id="{eid}">{emoji}</tg-emoji>'
            text = text.replace(emoji, tag)
            
    return text

def process_text_or_caption(text: str, parse_mode, bot_instance) -> tuple[str, str]:
    """Helper to process text/caption, convert markdown to HTML if needed, and insert custom emojis."""
    if not text:
        return text, parse_mode
        
    has_target = any(em in text for em in ALL_EMOJIS_SET)
    if not has_target:
        return text, parse_mode
        
    current_mode = parse_mode
    is_markdown = False
    
    if current_mode is None:
        bot_default_mode = getattr(bot_instance, "default", None) and bot_instance.default.parse_mode
        if bot_default_mode in (ParseMode.MARKDOWN, ParseMode.MARKDOWN_V2, "Markdown", "MarkdownV2"):
            is_markdown = True
    elif isinstance(current_mode, str) and current_mode.lower() in ("markdown", "markdownv2"):
        is_markdown = True
    elif current_mode in (ParseMode.MARKDOWN, ParseMode.MARKDOWN_V2):
        is_markdown = True
    elif type(current_mode).__name__ == "Default":
        bot_default_mode = getattr(bot_instance, "default", None) and bot_instance.default.parse_mode
        if bot_default_mode in (ParseMode.MARKDOWN, ParseMode.MARKDOWN_V2, "Markdown", "MarkdownV2"):
            is_markdown = True
            
    if is_markdown:
        text = markdown_to_html(text)
        current_mode = "HTML"
        
    text = replace_emojis(text)
    return text, current_mode

def patch_bot_emojis(bot: Bot):
    """Intercepts bot execution requests to dynamically replace standard emojis with custom premium ones."""
    original_make_request = bot.session.make_request
    
    async def new_make_request(bot_instance, method, timeout=None):
        parse_mode = getattr(method, "parse_mode", None)
        
        if isinstance(method, (SendMessage, EditMessageText)):
            if method.text and isinstance(method.text, str):
                method.text, new_mode = process_text_or_caption(method.text, parse_mode, bot_instance)
                method.parse_mode = new_mode
        elif isinstance(method, (SendPhoto, SendVideo, SendAnimation, SendAudio, SendDocument, EditMessageCaption)):
            if method.caption and isinstance(method.caption, str):
                method.caption, new_mode = process_text_or_caption(method.caption, parse_mode, bot_instance)
                method.parse_mode = new_mode
        
        return await original_make_request(bot_instance, method, timeout=timeout)
        
    bot.session.make_request = new_make_request
