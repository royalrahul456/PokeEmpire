import asyncio
import os
import sys
from sqlalchemy import select

# Adjust path to import from PokeEmpire
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.database import init_db, SessionLocal
from database.models import Pokemon, RedeemCode, RedeemClaim, User, UserPokemon

async def main():
    async with SessionLocal() as db:
        # Create a test user if not exists
        test_user_id = 99999999
        stmt = select(User).where(User.id == test_user_id)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()
        if not user:
            user = User(id=test_user_id, username="test_trainer", nickname="Test Trainer", coins=1000)
            db.add(user)
            await db.flush()
            print("Created test user!")
            
        # Get first pokemon from database
        stmt = select(Pokemon).limit(1)
        res = await db.execute(stmt)
        pokemon = res.scalar_one_or_none()
        if not pokemon:
            print("No Pokémon found in database to test with!")
            return
            
        print(f"Testing with Pokémon: ID={pokemon.id}, Name={pokemon.name}")
        
        # 1. Simulate `/gen` for Pokémon
        import string
        import random
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=8))
        print(f"Generated test code: {code}")
        
        new_code = RedeemCode(
            code=code,
            reward_type="pokemon",
            reward_value=pokemon.id,
            reward_is_shiny=False,
            reward_is_amv=False,
            reward_form_index=0,
            usage_limit=1
        )
        db.add(new_code)
        await db.commit()
        print("Successfully registered redeem code in DB!")
        
        # 2. Simulate `/redeem` for this code
        # Check claim
        stmt = select(RedeemCode).where(RedeemCode.code == code)
        res = await db.execute(stmt)
        db_code = res.scalar_one_or_none()
        
        assert db_code is not None, "Code not found in DB!"
        assert db_code.usage_count < db_code.usage_limit, "Code limit reached!"
        
        # Check if already claimed
        claim_stmt = select(RedeemClaim).where(RedeemClaim.code_id == db_code.id, RedeemClaim.user_id == test_user_id)
        claim_res = await db.execute(claim_stmt)
        assert claim_res.scalar_one_or_none() is None, "Already claimed!"
        
        # Claim
        claim = RedeemClaim(user_id=test_user_id, code_id=db_code.id)
        db.add(claim)
        
        db_code.usage_count += 1
        
        # Grant Pokémon (standard level 1)
        new_poke = UserPokemon(
            user_id=test_user_id,
            pokemon_id=db_code.reward_value,
            is_shiny=db_code.reward_is_shiny,
            is_amv=db_code.reward_is_amv,
            form_index=db_code.reward_form_index,
            level=1,
            xp=0
        )
        db.add(new_poke)
        await db.commit()
        print("Successfully claimed redeem code in DB!")
        
        # Clean up test entries
        await db.delete(new_poke)
        await db.delete(claim)
        await db.delete(db_code)
        await db.commit()
        print("Test database clean-up complete!")

if __name__ == "__main__":
    asyncio.run(main())
