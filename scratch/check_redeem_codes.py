import asyncio
from sqlalchemy import select
from database.database import SessionLocal
from database.models import RedeemCode, RedeemClaim

async def check():
    async with SessionLocal() as db:
        print("=== Redeem Codes ===")
        stmt = select(RedeemCode)
        res = await db.execute(stmt)
        for code in res.scalars().all():
            print(f"ID: {code.id} | Code: {code.code} | Reward Type: {code.reward_type} | Value: {code.reward_value} | Limit: {code.usage_count}/{code.usage_limit}")
            
        print("\n=== Redeem Claims ===")
        stmt = select(RedeemClaim)
        res = await db.execute(stmt)
        for claim in res.scalars().all():
            print(f"Claim ID: {claim.id} | User: {claim.user_id} | Code ID: {claim.code_id} | Claimed At: {claim.claimed_at}")

if __name__ == '__main__':
    asyncio.run(check())
