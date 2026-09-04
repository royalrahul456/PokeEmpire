from typing import Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database.models import Pokemon

# Global high-speed in-memory caches
_cache_by_id: Dict[int, Pokemon] = {}
_cache_by_name: Dict[str, Pokemon] = {}
_cache_by_rarity: Dict[str, List[Pokemon]] = {}

async def init_pokemon_cache(db: AsyncSession):
    """Loads all Pokemon records into memory for instant sub-millisecond access."""
    global _cache_by_id, _cache_by_name, _cache_by_rarity
    stmt = select(Pokemon)
    res = await db.execute(stmt)
    all_pokes = res.scalars().all()
    
    _cache_by_id = {p.id: p for p in all_pokes}
    _cache_by_name = {p.name.lower(): p for p in all_pokes}
    
    by_rarity: Dict[str, List[Pokemon]] = {}
    for p in all_pokes:
        by_rarity.setdefault(p.rarity, []).append(p)
    _cache_by_rarity = by_rarity
    print(f"⚡ In-Memory Pokemon Cache active! Loaded {len(all_pokes)} Pokemon species across {len(by_rarity)} rarity tiers.")

def get_cached_pokemon_by_id(poke_id: int) -> Optional[Pokemon]:
    return _cache_by_id.get(poke_id)

def get_cached_pokemon_by_name(name: str) -> Optional[Pokemon]:
    if not name:
        return None
    return _cache_by_name.get(name.strip().lower())

def get_cached_pokemon_by_rarity(rarity: str) -> List[Pokemon]:
    return _cache_by_rarity.get(rarity, [])

def get_all_cached_pokemon() -> List[Pokemon]:
    return list(_cache_by_id.values())

def refresh_single_pokemon_cache(pokemon: Pokemon):
    global _cache_by_id, _cache_by_name, _cache_by_rarity
    _cache_by_id[pokemon.id] = pokemon
    _cache_by_name[pokemon.name.lower()] = pokemon
    
    # Refresh rarity bucket
    r_list = _cache_by_rarity.setdefault(pokemon.rarity, [])
    if pokemon not in r_list:
        r_list.append(pokemon)
