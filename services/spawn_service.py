import os
import json
import random
import asyncio
from typing import Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from database.models import Pokemon, ActiveSpawn
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from utils.settings import load_spawn_settings

RARITY_PROBABILITIES = {
    "Common": 70,
    "Rare": 20,
    "Epic": 7,
    "Legendary": 2,
    "Mythical": 1
}

_chat_spawn_locks: Dict[int, asyncio.Lock] = {}

class SpawnService:
    @staticmethod
    async def trigger_spawn(db: AsyncSession, chat_id: int, bot: Bot, rarity: str = None) -> bool:
        """Rolls rarity, selects a random Pokémon, rolls shiny status, and spawns it in the group."""
        if chat_id not in _chat_spawn_locks:
            _chat_spawn_locks[chat_id] = asyncio.Lock()
            
        spawn_lock = _chat_spawn_locks[chat_id]
        async with spawn_lock:
            settings = load_spawn_settings()
        
            if rarity:
                selected_rarity = rarity
            else:
                # 1. Roll rarity tier
                probs = settings.get("group_rarity_probabilities", RARITY_PROBABILITIES)
                rarities = list(probs.keys())
                weights = [probs.get(r, RARITY_PROBABILITIES.get(r, 0)) for r in rarities]
                selected_rarity = random.choices(rarities, weights=weights, k=1)[0]

            # 2. Get Pokémon from in-memory cache
            from utils.pokemon_cache import get_cached_pokemon_by_rarity, get_all_cached_pokemon
            pokemon_list = get_cached_pokemon_by_rarity(selected_rarity)
            if not pokemon_list:
                pokemon_list = get_all_cached_pokemon()
                if not pokemon_list:
                    return False

            selected_pokemon = random.choice(pokemon_list)

            # 3. Roll shiny rate (disabled for automatic wild spawns)
            is_shiny = False

            # 4. Build spawn text & keyboards
            status_text = "✨ <b>SHINY POKÉMON</b> ✨" if is_shiny else "🌳 <b>Wild Encounter</b>"
            caption = (
                f"⚡ <b>A WILD POKÉMON APPEARED!</b> ⚡\n"
                f"◈ ────────────────── ◈\n"
                f"🌿 <i>A wild Pokémon emerged from the tall grass!</i>\n\n"
                f"✨ <b>Status:</b> {status_text}\n"
                f"💎 <b>Rarity:</b> <code>{selected_rarity}</code>\n"
                f"◈ ────────────────── ◈\n"
                f"👉 <i>Type <code>/catch &lt;name&gt;</code> to catch it!</i>"
            )

            hint_keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔍 Hint (2,000 coins)", callback_data="spawn_hint")]
            ])

            message_id = None

            # 5. Post spawn photo to the chat
            spawn_photo = selected_pokemon.image_url
            if is_shiny:
                from database.models import PokemonFormMedia
                s_media_stmt = select(PokemonFormMedia.media_value).where(
                    PokemonFormMedia.pokemon_id == selected_pokemon.id,
                    PokemonFormMedia.form_index == 6
                )
                s_media_res = await db.execute(s_media_stmt)
                s_media = s_media_res.scalar_one_or_none()
                if s_media:
                    # Parse prefix
                    from handlers.admin import parse_stored_media_value
                    _, s_mval = parse_stored_media_value(s_media)
                    if s_mval:
                        spawn_photo = s_mval

            try:
                msg = await bot.send_photo(
                    chat_id=chat_id,
                    photo=spawn_photo,
                    caption=caption,
                    reply_markup=hint_keyboard,
                    parse_mode="HTML"
                )
                message_id = msg.message_id
            except Exception as e:
                print(f"Error sending spawn photo to chat {chat_id}: {e}")
                # Fallback: send a text-only spawn message so players can still catch
                try:
                    fallback = (
                        f"⚡ <b>A WILD POKÉMON APPEARED!</b> ⚡\n"
                        f"◈ ────────────────── ◈\n"
                        f"🌿 A wild <b>{selected_rarity}</b> Pokémon appeared!\n"
                        f"◈ ────────────────── ◈\n"
                        f"👉 <i>Type <code>/catch &lt;name&gt;</code> to catch it!</i>"
                    )
                    msg = await bot.send_message(chat_id=chat_id, text=fallback, reply_markup=hint_keyboard, parse_mode="HTML")
                    message_id = msg.message_id
                except Exception:
                    pass

            if not message_id:
                return False

            # 6. Perform DB operations in a single fast transaction
            # Remove any active spawn in this chat
            await db.execute(delete(ActiveSpawn).where(ActiveSpawn.chat_id == chat_id))

            # Insert new active spawn record with message_id already set
            active = ActiveSpawn(
                chat_id=chat_id,
                pokemon_id=selected_pokemon.id,
                is_shiny=is_shiny,
                message_id=message_id
            )
            db.add(active)
            await db.commit()

            # Trigger background despawn timeout task
            asyncio.create_task(spawn_timeout_task(chat_id, message_id, bot))

            return True

async def spawn_timeout_task(chat_id: int, message_id: int, bot: Bot):
    await asyncio.sleep(60)
    
    from database.database import SessionLocal
    from database.models import ActiveSpawn
    from sqlalchemy import select, delete
    
    async with SessionLocal() as db:
        stmt = select(ActiveSpawn).where(ActiveSpawn.chat_id == chat_id)
        res = await db.execute(stmt)
        active = res.scalar_one_or_none()
        
        if active and active.message_id == message_id:
            # Pokémon fled! Delete active spawn record
            await db.execute(delete(ActiveSpawn).where(ActiveSpawn.chat_id == chat_id))
            await db.commit()
            
            # Delete the spawn message
            try:
                await bot.delete_message(chat_id=chat_id, message_id=message_id)
            except Exception:
                pass
                
            # Announce fleeing
            try:
                await bot.send_message(
                    chat_id=chat_id,
                    text="🏃‍♂️ **The wild Pokémon fled!** You were too slow."
                )
            except Exception:
                pass

