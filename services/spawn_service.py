import os
import json
import random
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

class SpawnService:
    @staticmethod
    async def trigger_spawn(db: AsyncSession, chat_id: int, bot: Bot, rarity: str = None) -> bool:
        """Rolls rarity, selects a random Pokémon, rolls shiny status, and spawns it in the group."""
        
        settings = load_spawn_settings()
        
        if rarity:
            selected_rarity = rarity
        else:
            # 1. Roll rarity tier
            probs = settings.get("group_rarity_probabilities", RARITY_PROBABILITIES)
            rarities = list(probs.keys())
            weights = [probs.get(r, RARITY_PROBABILITIES.get(r, 0)) for r in rarities]
            selected_rarity = random.choices(rarities, weights=weights, k=1)[0]

        # 2. Query Pokémon matching that rarity tier
        stmt = select(Pokemon).where(Pokemon.rarity == selected_rarity)
        res = await db.execute(stmt)
        pokemon_list = res.scalars().all()

        # Fallback in case DB seeding hasn't completed
        if not pokemon_list:
            stmt = select(Pokemon)
            res = await db.execute(stmt)
            pokemon_list = res.scalars().all()
            if not pokemon_list:
                return False

        selected_pokemon = random.choice(pokemon_list)

        # 3. Roll shiny rate (1 in 500)
        is_shiny = random.randint(1, 500) == 1

        # 4. Build spawn text & keyboards
        status_text = "✨ **SHINY** ✨" if is_shiny else "🌳 **Normal**"
        caption = (
            f"🌳 **WILD ENCOUNTER** 🌳\n"
            f"A wild Pokémon appeared in the tall grass!\n\n"
            f"✨ **Status**: {status_text}\n"
            f"✨ **Rarity**: `{selected_rarity}`\n\n"
            f"👉 Guess the Pokémon and catch it with:\n"
            f"`/catch <name>`\n"
            f"───────────────"
        )

        hint_keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔍 Hint (2,000 coins)", callback_data="spawn_hint")]
        ])

        message_id = None

        # 5. Post spawn photo to the chat
        try:
            msg = await bot.send_photo(
                chat_id=chat_id,
                photo=selected_pokemon.image_url,
                caption=caption,
                reply_markup=hint_keyboard,
                parse_mode="Markdown"
            )
            message_id = msg.message_id
        except Exception as e:
            print(f"Error sending spawn photo to chat {chat_id}: {e}")
            # Fallback: send a text-only spawn message so players can still catch
            try:
                r_emoji = "⭐" if selected_rarity == "Legendary" else "✨"
                fallback = (
                    f"🌳 **WILD ENCOUNTER** 🌳\n"
                    f"A wild **{selected_rarity}** Pokémon appeared!\n\n"
                    f"{r_emoji} **Rarity**: `{selected_rarity}`\n\n"
                    f"👉 `/catch <name>` to catch it!\n"
                    f"───────────────"
                )
                msg = await bot.send_message(chat_id=chat_id, text=fallback, reply_markup=hint_keyboard, parse_mode="Markdown")
                message_id = msg.message_id
            except Exception:
                pass

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
        if message_id:
            import asyncio
            asyncio.create_task(spawn_timeout_task(chat_id, message_id, bot))

        return True

async def spawn_timeout_task(chat_id: int, message_id: int, bot: Bot):
    import asyncio
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

