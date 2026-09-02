import sys
import os
import asyncio
from unittest.mock import AsyncMock, MagicMock
from aiogram.types import CallbackQuery, User as TGUser, Message
from sqlalchemy import select

PROJECT_DIR = r"c:\Users\Rahul Pachute\Downloads\coding\PokeEmpire"
sys.path.append(PROJECT_DIR)
os.chdir(PROJECT_DIR)
sys.stdout.reconfigure(encoding='utf-8')

async def test():
    from database.database import SessionLocal
    from handlers.start import cb_dm_dex
    
    # Mock CallbackQuery
    callback = MagicMock(spec=CallbackQuery)
    callback.from_user = MagicMock(spec=TGUser)
    callback.from_user.id = 6593485710
    callback.from_user.username = "royalrahul"
    callback.from_user.first_name = "Rahul"
    callback.data = "dm_dex_1"
    
    callback.message = MagicMock(spec=Message)
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    
    async with SessionLocal() as session:
        try:
            print("Running cb_dm_dex...")
            await cb_dm_dex(callback, session)
            print("Call completed successfully!")
            print("edit_text called with:")
            for call in callback.message.edit_text.call_args_list:
                print(call)
        except Exception as e:
            print("CRASHED WITH ERROR:")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test())
