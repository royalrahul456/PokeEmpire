import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass

import asyncio
import logging
from aiogram import Bot, Dispatcher
from main import main

print("==================================================")
print("  PREPARING LIVE DUAL-BOT POLLING TEST FOR GROUPS  ")
print("==================================================")
print("1. Please check @BotFather -> Bot Settings -> Group Privacy -> Turn OFF!")
print("2. Type any command (/profile, /pokedex, /start, /balance, /catch) in your group chat!")
print("==================================================")
