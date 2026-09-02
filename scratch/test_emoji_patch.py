# -*- coding: utf-8 -*-
import asyncio
import re
from aiogram import Bot
from aiogram.methods import SendMessage
from aiogram.enums import ParseMode

# The mapping from the user's latest request
EMOJI_MAPPING = {
    "🪙": "5382164415019768638",
    "💰": "5287231198098117669",
    "💳": "5445353829304387411",
    "💸": "5864068125112144897",
    "👑": "5433758796289685818",
    "🏆": "5188344996356448758",
    "🥇": "5440539497383087970",
    "🥈": "5447203607294265305",
    "🥉": "5453902265922376865",
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
    "📦": "5449800250032143374",
    "🎁": "5203996991054432397",
    "🛒": "5312361253610475399",
    "🌲": "5906705309136589768",
    "📢": "5789428375261023681",
    "📖": "5449660075184508972",
    "🎱": "5289940334619406906",
    "🔵": "4965219701572503640",
    "🟣": "5197368799954738967",
    "🟡": "6005661956931850799",
    "🌌": "5812392946917445652",
    "📺": "5371074616187969568",
    "🖼️": "5895427227528467580",
    "🖼": "5895427227528467580",
    "⚡": "5411590687663608498",
    "⚡️": "5411590687663608498",
    "🌀": "5825951969692357786"
}

ALL_EMOJIS_SET = set(EMOJI_MAPPING.keys()) | {"🟢", "🔮"}

def safe_print(msg):
    print(msg.encode('ascii', errors='backslashreplace').decode('ascii'))

def markdown_to_html(text: str) -> str:
    if not isinstance(text, str) or not text:
        return text
    # Escape HTML tags since we are translating from markdown literal characters
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
    if not isinstance(text, str) or not text:
        return text
    
    # Contextual replacement for 🟢 (Green Circle)
    if "🟢" in text:
        if "Uncommon" in text:
            eid = "5416081784641168838"  # Rarities version
        else:
            eid = "5215522595922779944"  # Statuses version
        text = text.replace("🟢", f'<tg-emoji emoji-id="{eid}">🟢</tg-emoji>')

    # Contextual replacement for 🔮 (Crystal Ball)
    if "🔮" in text:
        if "Terastal" in text or "Form 6.5" in text:
            eid = "5244955049024581265"  # Terastal Form version
        else:
            eid = "5271810272640643747"  # Epic Rarity version
        text = text.replace("🔮", f'<tg-emoji emoji-id="{eid}">🔮</tg-emoji>')

    for emoji, eid in EMOJI_MAPPING.items():
        if emoji in text:
            tag = f'<tg-emoji emoji-id="{eid}">{emoji}</tg-emoji>'
            text = text.replace(emoji, tag)
    return text

def process_text_or_caption(text: str, parse_mode, bot_instance) -> tuple[str, str]:
    if not text:
        return text, parse_mode
    
    # Check if text contains any target emojis
    has_target = any(em in text for em in ALL_EMOJIS_SET)
    if not has_target:
        return text, parse_mode
        
    # Resolve parse_mode to determine if it is markdown
    current_mode = parse_mode
    is_markdown = False
    
    if current_mode is None:
        # Fall back to bot default if defined
        bot_default_mode = getattr(bot_instance, "default", None) and bot_instance.default.parse_mode
        if bot_default_mode in (ParseMode.MARKDOWN, ParseMode.MARKDOWN_V2, "Markdown", "MarkdownV2"):
            is_markdown = True
    elif isinstance(current_mode, str) and current_mode.lower() in ("markdown", "markdownv2"):
        is_markdown = True
    elif current_mode in (ParseMode.MARKDOWN, ParseMode.MARKDOWN_V2):
        is_markdown = True
    elif type(current_mode).__name__ == "Default":
        # The default property value
        bot_default_mode = getattr(bot_instance, "default", None) and bot_instance.default.parse_mode
        if bot_default_mode in (ParseMode.MARKDOWN, ParseMode.MARKDOWN_V2, "Markdown", "MarkdownV2"):
            is_markdown = True
            
    if is_markdown:
        text = markdown_to_html(text)
        current_mode = "HTML"
        
    # Replace emojis
    text = replace_emojis(text)
    return text, current_mode

def patch_bot_emojis(bot: Bot):
    original_make_request = bot.session.make_request
    
    async def new_make_request(bot_instance, method, timeout=None):
        safe_print(f"Intercepted make_request: {type(method).__name__}")
        
        # Get parse_mode attribute if it exists
        parse_mode = getattr(method, "parse_mode", None)
                
        if isinstance(method, SendMessage):
            if method.text:
                new_text, new_mode = process_text_or_caption(method.text, parse_mode, bot_instance)
                method.text = new_text
                method.parse_mode = new_mode
        elif hasattr(method, "caption") and method.caption:
            new_caption, new_mode = process_text_or_caption(method.caption, parse_mode, bot_instance)
            method.caption = new_caption
            method.parse_mode = new_mode
            
        try:
            return await original_make_request(bot_instance, method, timeout)
        except Exception as e:
            safe_print(f"Original call raised: {type(e).__name__}")
            raise e
            
    bot.session.make_request = new_make_request

async def test():
    bot = Bot(token="123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11")
    # Patch default properties' parse_mode
    bot.default.parse_mode = ParseMode.MARKDOWN
    patch_bot_emojis(bot)
    
    # 1. Text with markdown formatting and standard emoji
    msg1 = SendMessage(chat_id=123456, text="Hello **world**! \U0001FA99 Here is a *bold* test. \U0001F534 Status is enabled.")
    safe_print(f"Msg 1 before: {msg1.text} | Parse Mode: {msg1.parse_mode}")
    
    try:
        await bot(msg1)
    except Exception:
        pass
        
    safe_print(f"Msg 1 after: {msg1.text} | Parse Mode: {msg1.parse_mode}")
    
    # 2. Text with Uncommon context and green circle
    msg2 = SendMessage(chat_id=123456, text="Rarity: \U0001F7E2 Uncommon")
    try:
        await bot(msg2)
    except Exception:
        pass
    safe_print(f"Msg 2 after: {msg2.text}")

if __name__ == "__main__":
    asyncio.run(test())
