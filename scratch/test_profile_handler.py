import asyncio
from database.database import SessionLocal
from database.models import User, UserPokemon, Pokemon
from sqlalchemy import select, func, distinct
import html

# Mock helper functions
def get_progress_bar(value, total, length=10, fill_char="▰", empty_char="▱"):
    filled = int(round((value / total) * length))
    return fill_char * filled + empty_char * (length - filled)

async def test():
    async with SessionLocal() as db:
        # Fetch first user from DB
        res = await db.execute(select(User).limit(1))
        user = res.scalar_one_or_none()
        if not user:
            print("No users in database")
            return
            
        user_id = user.id
        print("Testing for User ID:", user_id)
        
        # Count total caught Pokémon
        count_stmt = select(func.count(UserPokemon.id)).where(UserPokemon.user_id == user_id)
        count_res = await db.execute(count_stmt)
        total_caught = count_res.scalar() or 0
        print("total_caught:", total_caught)

        # Count unique caught Pokémon
        unique_stmt = select(func.count(distinct(UserPokemon.pokemon_id))).where(UserPokemon.user_id == user_id)
        unique_res = await db.execute(unique_stmt)
        unique_caught = unique_res.scalar() or 0
        print("unique_caught:", unique_caught)

        # Count shiny Pokémon
        shiny_stmt = select(func.count(UserPokemon.id)).where(UserPokemon.user_id == user_id, UserPokemon.is_shiny == True)
        shiny_res = await db.execute(shiny_stmt)
        total_shiny = shiny_res.scalar() or 0
        print("total_shiny:", total_shiny)

        # Count total species in database
        total_species_stmt = select(func.count(Pokemon.id))
        total_species_res = await db.execute(total_species_stmt)
        total_species = total_species_res.scalar() or 1
        print("total_species:", total_species)

        # Calculate percentage
        dex_pct = (unique_caught / total_species) * 100
        dex_bar = get_progress_bar(unique_caught, total_species, 10, fill_char="▰", empty_char="▱")
        print("dex_pct:", dex_pct)

        # Count caught by rarity
        rarity_stmt = select(Pokemon.rarity, func.count(UserPokemon.id)).join(UserPokemon).where(UserPokemon.user_id == user_id).group_by(Pokemon.rarity)
        rarity_res = await db.execute(rarity_stmt)
        rarity_counts = {r: count for r, count in rarity_res.all()}
        print("rarity_counts:", rarity_counts)

        commons = rarity_counts.get("Common", 0)
        uncommons = rarity_counts.get("Uncommon", 0)
        mediums = rarity_counts.get("Medium", 0)
        rares = rarity_counts.get("Rare", 0)
        epics = rarity_counts.get("Epic", 0)
        legendaries = rarity_counts.get("Legendary", 0)
        mythicals = rarity_counts.get("Mythical", 0)

        # Count form-based (AMV/Art=1, Dmax=2, Gmax=3, Z-Move=4, Terastal=5)
        form_counts_stmt = select(UserPokemon.form_index, func.count(distinct(UserPokemon.pokemon_id))).where(
            UserPokemon.user_id == user_id, UserPokemon.form_index > 0
        ).group_by(UserPokemon.form_index)
        form_counts_res = await db.execute(form_counts_stmt)
        form_counts = {fi: cnt for fi, cnt in form_counts_res.all()}
        amv_count = form_counts.get(1, 0)
        dmax_count = form_counts.get(2, 0)
        gmax_count = form_counts.get(3, 0)
        zmove_count = form_counts.get(4, 0)
        terastal_count = form_counts.get(5, 0)

        # Formatted coins
        formatted_coins = f"{user.coins:,}"
        user_nickname = user.nickname if user.nickname else "Trainer"

        # Calculate global rank position based on catches
        rank_stmt = (
            select(func.count())
            .select_from(
                select(User.id)
                .join(UserPokemon, UserPokemon.user_id == User.id)
                .group_by(User.id)
                .having(func.count(UserPokemon.id) > total_caught)
                .subquery()
            )
        )
        rank_res = await db.execute(rank_stmt)
        rank_position = (rank_res.scalar() or 0) + 1
        print("rank_position:", rank_position)

        profile_card = (
            f"╭──「 🏆 Trainer Profile 」\n"
            f"├─➩ 🏓 User: {html.escape(user_nickname)}\n"
            f"├─➩ 🆔 ID: <code>{user.id}</code>\n"
            f"├─➩ 💰 Balance: <code>{formatted_coins} coins</code>\n"
            f"├─➩ ⚡ Pokémon: {unique_caught} (Total Catches: {total_caught})\n"
            f"├─➩ 🌍 Pokédex: {unique_caught}/{total_species} ({dex_pct:.3f}%)\n"
            f"├─➩ 🎁 Progress:\n"
            f"╰         {dex_bar}\n\n"
            f"╭─ Rarity Breakdown ─\n"
            f"├─➩ ⚪️ Common: {commons}\n"
            f"├─➩ 🟢 Uncommon: {uncommons}\n"
            f"├─➩ 🔵 Medium: {mediums}\n"
            f"├─➩ 🟣 Rare: {rares}\n"
            f"├─➩ 🔮 Epic: {epics}\n"
            f"├─➩ 🌟 Legendary: {legendaries}\n"
            f"├─➩ 🌌 Mythical: {mythicals}\n"
            f"├─➩ ✨ Shiny: {total_shiny}\n"
            f"╰───────────────────\n\n"
            f"╭─ Forms Breakdown ─\n"
            f"├─➩ 🎬 AMV / Art: {amv_count}\n"
            f"├─➩ ⚡ Dmax: {dmax_count}\n"
            f"├─➩ 💥 Gmax: {gmax_count}\n"
            f"├─➩ 🌀 Z-Move: {zmove_count}\n"
            f"├─➩ 🔮 Terastal: {terastal_count}\n"
            f"╰───────────────────\n\n"
            f"╭─ Global Rank ─\n"
            f"├─➩ 🏆 Position: #{rank_position}\n"
            f"╰───────────────────"
        )
        print("SUCCESS! profile_card content:")
        print(profile_card)

if __name__ == '__main__':
    asyncio.run(test())
