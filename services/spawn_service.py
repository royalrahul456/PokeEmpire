import random
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from database.models import Pokemon, ActiveSpawn
from aiogram import Bot

RARITY_PROBABILITIES = {
    "Common": 70,
    "Rare": 20,
    "Epic": 7,
    "Legendary": 2,
    "Mythical": 1
}

class SpawnService:
    @staticmethod
    async def trigger_spawn(db: AsyncSession, chat_id: int, bot: Bot) -> bool:
        """Rolls rarity, selects a random Pokémon, rolls shiny status, and spawns it in the group."""
        
        # 1. Roll rarity tier (Group chats only spawn Legendary rarity)
        if chat_id < 0:
            selected_rarity = "Legendary"
        else:
            rarities = list(RARITY_PROBABILITIES.keys())
            weights = [RARITY_PROBABILITIES[r] for r in rarities]
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

        # 4. Remove any active spawn in this chat
        await db.execute(delete(ActiveSpawn).where(ActiveSpawn.chat_id == chat_id))

        # 5. Insert new active spawn record
        active = ActiveSpawn(
            chat_id=chat_id,
            pokemon_id=selected_pokemon.id,
            is_shiny=is_shiny
        )
        db.add(active)
        await db.commit()

        # 6. Build spawn text
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

        # 7. Post spawn photo to the chat
        try:
            msg = await bot.send_photo(
                chat_id=chat_id,
                photo=selected_pokemon.image_url,
                caption=caption,
                parse_mode="Markdown"
            )
            # Update the active spawn record with the message ID
            active.message_id = msg.message_id
            await db.commit()
            return True
        except Exception as e:
            print(f"Error sending spawn message to chat {chat_id}: {e}")
            return False
        return False
