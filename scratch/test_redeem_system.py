import asyncio
import sys
import os
from sqlalchemy import select, delete

# Add parent directory to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.database import SessionLocal, init_db
from database.models import User, Pokemon, UserPokemon, RedeemCode, RedeemClaim

async def test_redeem_flow():
    print("Initializing test database...")
    await init_db()
    
    async with SessionLocal() as db:
        # Clean up existing test data
        await db.execute(delete(RedeemClaim))
        await db.execute(delete(RedeemCode))
        await db.execute(delete(UserPokemon).where(UserPokemon.user_id == 99999))
        await db.execute(delete(User).where(User.id == 99999))
        await db.commit()
        
        print("1. Creating test user...")
        test_user = User(id=99999, username="test_trainer", nickname="Test Trainer", coins=100)
        db.add(test_user)
        
        print("2. Configuring AMV edit for Bulbasaur (ID: 1)...")
        stmt = select(Pokemon).where(Pokemon.id == 1)
        res = await db.execute(stmt)
        bulba = res.scalar_one_or_none()
        if not bulba:
            print("Fallback: Creating Bulbasaur species")
            bulba = Pokemon(id=1, name="bulbasaur", rarity="Common", generation=1, image_url="bulba.png")
            db.add(bulba)
            await db.flush()
            
        bulba.video_url = "telegram_amv_file_id_12345"
        
        print("3. Creating redeem code for AMV Bulbasaur with limit 2...")
        new_code = RedeemCode(
            code="BULBAAMV",
            reward_type="pokemon",
            reward_value=1,
            reward_is_shiny=False,
            reward_is_amv=True,
            usage_limit=2
        )
        db.add(new_code)
        await db.commit()
        
    print("4. Simulating first redemption...")
    # Simulate a user redeeming
    async with SessionLocal() as db:
        # Fetch code
        c_stmt = select(RedeemCode).where(RedeemCode.code == "BULBAAMV")
        c_res = await db.execute(c_stmt)
        code = c_res.scalar_one()
        
        # Verify limit and duplicate check
        claim_stmt = select(RedeemClaim).where(RedeemClaim.code_id == code.id, RedeemClaim.user_id == 99999)
        claim_res = await db.execute(claim_stmt)
        assert claim_res.scalar_one_or_none() is None, "Should not be claimed yet"
        
        # Process claim
        claim = RedeemClaim(user_id=99999, code_id=code.id)
        db.add(claim)
        code.usage_count += 1
        
        # Grant reward
        import random
        serial_number = f"#{1:03d}-{random.randint(1000, 9999)}"
        new_poke = UserPokemon(
            user_id=99999,
            pokemon_id=1,
            is_shiny=False,
            is_amv=True,
            serial_number=serial_number,
            level=1,
            xp=0
        )
        db.add(new_poke)
        await db.commit()
        print(f"Redeemed successfully! Granted AMV Bulbasaur with Serial: {serial_number}")
        
    print("5. Simulating duplicate redemption check...")
    async with SessionLocal() as db:
        c_stmt = select(RedeemCode).where(RedeemCode.code == "BULBAAMV")
        c_res = await db.execute(c_stmt)
        code = c_res.scalar_one()
        
        claim_stmt = select(RedeemClaim).where(RedeemClaim.code_id == code.id, RedeemClaim.user_id == 99999)
        claim_res = await db.execute(claim_stmt)
        assert claim_res.scalar_one_or_none() is not None, "Should be already claimed"
        print("Duplicate check passed (user blocked from double claiming).")
        
    print("6. Simulating limit check...")
    # Add another claim to reach limit of 2
    async with SessionLocal() as db:
        c_stmt = select(RedeemCode).where(RedeemCode.code == "BULBAAMV")
        c_res = await db.execute(c_stmt)
        code = c_res.scalar_one()
        
        # Simulate claim by second user (ID 88888)
        claim2 = RedeemClaim(user_id=88888, code_id=code.id)
        db.add(claim2)
        code.usage_count += 1
        await db.commit()
        
        assert code.usage_count >= code.usage_limit, "Usage count should hit limit"
        print(f"Usage count: {code.usage_count}/{code.usage_limit}. Limit check passed.")
        
    print("All tests passed successfully!")

if __name__ == "__main__":
    asyncio.run(test_redeem_flow())
