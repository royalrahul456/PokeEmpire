import sys
sys.stdout.reconfigure(encoding='utf-8')

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

try:
    btn = InlineKeyboardButton(
        text="Add to Group",
        url="https://t.me/test",
        icon_custom_emoji_id="5382164415019768638",
        style="primary"
    )
    print("✅ InlineKeyboardButton instantiated directly with icon_custom_emoji_id & style!")
    print("Dump:", btn.model_dump(exclude_none=True))
except Exception as e:
    print("⚠️ Direct instantiation error:", e)
    btn = InlineKeyboardButton(text="Add to Group", url="https://t.me/test")
    dump = btn.model_dump(exclude_none=True)
    dump["icon_custom_emoji_id"] = "5382164415019768638"
    dump["style"] = "primary"
    print("✅ Custom dictionary payload constructed:", dump)
