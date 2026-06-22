from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from database.models import GlobalSetting
from typing import Optional

async def get_favorite_id(user_id: int, db: AsyncSession) -> Optional[str]:
    """Get the string ID (e.g. '6' or '6.1') of the user's favorite cover Pokémon from DB."""
    stmt = select(GlobalSetting.value).where(GlobalSetting.key == f"user_fav_{user_id}")
    res = await db.execute(stmt)
    return res.scalar()

async def set_favorite_id(user_id: int, fav_val: Optional[str], db: AsyncSession):
    """Set or clear (if fav_val is None) the favorite cover Pokémon for a user in DB."""
    key = f"user_fav_{user_id}"
    if fav_val is None:
        stmt = delete(GlobalSetting).where(GlobalSetting.key == key)
        await db.execute(stmt)
    else:
        stmt = select(GlobalSetting).where(GlobalSetting.key == key)
        res = await db.execute(stmt)
        setting = res.scalar_one_or_none()
        if setting:
            setting.value = str(fav_val)
        else:
            db.add(GlobalSetting(key=key, value=str(fav_val)))
