import sys, os
sys.path.append(os.getcwd())
import asyncio
from aiogram.filters import Command
from aiogram.types import Message, Chat, User

async def test():
    cmd = Command("panel", "ownerpanel", "adminpanel")
    msg = Message(message_id=1, date=123, chat=Chat(id=1, type="private"), from_user=User(id=1, is_bot=False, first_name="Test"), text="/panel")
    bot = None
    res = await cmd(msg, bot)
    print("Filter result for /panel:", res)

if __name__ == "__main__":
    asyncio.run(test())
