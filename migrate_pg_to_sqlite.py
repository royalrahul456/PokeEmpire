"""
migrate_pg_to_sqlite.py
────────────────────────────────────────────────────────────────
Migrates ALL data from PostgreSQL (Neon / Supabase / any provider)
back to the local SQLite database (pokeempire.db).

Usage:
    python migrate_pg_to_sqlite.py

You will be prompted to enter your PostgreSQL DATABASE_URL.
Make sure pokeempire.db (or the persistent volume path) is writable.
────────────────────────────────────────────────────────────────
"""

import sys
import os
import asyncio

sys.stdout.reconfigure(encoding="utf-8")

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(PROJECT_DIR)
os.chdir(PROJECT_DIR)

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, text

from database.database import Base, SessionLocal
from database.models import (
    User, Pokemon, UserPokemon, ActiveSpawn,
    GroupSetting, GlobalSetting, RedeemCode, RedeemClaim,
    PokemonFormMedia, PvpBattle, Auction, AuctionBid
)


async def migrate_pg_to_sqlite(postgres_url: str):
    # ── Fix URL scheme ───────────────────────────────────────────────────────
    if postgres_url.startswith("postgresql://"):
        postgres_url = postgres_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if "sslmode=require" in postgres_url:
        postgres_url = postgres_url.replace("sslmode=require", "ssl=require")
    if "sslmode=prefer" in postgres_url:
        postgres_url = postgres_url.replace("sslmode=prefer", "ssl=prefer")

    print("🔌 Connecting to PostgreSQL...")
    pg_engine = create_async_engine(postgres_url, echo=False)
    PGSession = sessionmaker(bind=pg_engine, class_=AsyncSession, expire_on_commit=False)

    print("🛠️  Ensuring SQLite tables exist...")
    from database.database import engine as sqlite_engine
    async with sqlite_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    print("\n📚 Reading data from PostgreSQL...\n")
    async with PGSession() as pg:

        def q(model): return pg.execute(select(model))

        users         = (await q(User)).scalars().all()
        pokemons      = (await q(Pokemon)).scalars().all()
        user_pokemons = (await q(UserPokemon)).scalars().all()
        spawns        = (await q(ActiveSpawn)).scalars().all()
        groups        = (await q(GroupSetting)).scalars().all()
        globals_      = (await q(GlobalSetting)).scalars().all()
        redeem_codes  = (await q(RedeemCode)).scalars().all()
        redeem_claims = (await q(RedeemClaim)).scalars().all()
        form_media    = (await q(PokemonFormMedia)).scalars().all()
        battles       = (await q(PvpBattle)).scalars().all()
        auctions      = (await q(Auction)).scalars().all()
        bids          = (await q(AuctionBid)).scalars().all()

    print("📊 PostgreSQL Data Summary:")
    print(f"   • Users              : {len(users)}")
    print(f"   • Pokémon species    : {len(pokemons)}")
    print(f"   • Caught Pokémon     : {len(user_pokemons)}")
    print(f"   • Active Spawns      : {len(spawns)}")
    print(f"   • Group Settings     : {len(groups)}")
    print(f"   • Global Settings    : {len(globals_)}")
    print(f"   • Redeem Codes       : {len(redeem_codes)}")
    print(f"   • Redeem Claims      : {len(redeem_claims)}")
    print(f"   • Form Media         : {len(form_media)}")
    print(f"   • PvP Battles        : {len(battles)}")
    print(f"   • Auctions           : {len(auctions)}")
    print(f"   • Auction Bids       : {len(bids)}")

    print("\n✍️  Writing data to SQLite...\n")
    async with SessionLocal() as db:

        # ── 1. Pokémon species ───────────────────────────────────────────────
        print("   [1/12] Copying Pokémon species...")
        existing = set((await db.execute(select(Pokemon.id))).scalars().all())
        for p in pokemons:
            if p.id not in existing:
                db.add(Pokemon(
                    id=p.id, name=p.name, rarity=p.rarity,
                    generation=p.generation, image_url=p.image_url,
                    video_url=p.video_url, dmax_url=p.dmax_url,
                    gmax_url=p.gmax_url, zmove_url=p.zmove_url,
                    terastal_url=p.terastal_url
                ))
        await db.flush()

        # ── 2. Users ─────────────────────────────────────────────────────────
        print("   [2/12] Copying users...")
        existing = set((await db.execute(select(User.id))).scalars().all())
        for u in users:
            if u.id not in existing:
                db.add(User(
                    id=u.id, username=u.username, nickname=u.nickname,
                    coins=u.coins, last_daily_at=u.last_daily_at,
                    last_spin_at=u.last_spin_at, has_shiny_charm=u.has_shiny_charm,
                    current_streak=u.current_streak, best_streak=u.best_streak,
                    last_secured_date=u.last_secured_date,
                    last_catch_date=u.last_catch_date,
                    catches_today=u.catches_today, created_at=u.created_at
                ))
        await db.flush()

        # ── 3. UserPokemon (caught collection) ───────────────────────────────
        print("   [3/12] Copying caught Pokémon collections...")
        existing = set((await db.execute(select(UserPokemon.id))).scalars().all())
        for up in user_pokemons:
            if up.id not in existing:
                db.add(UserPokemon(
                    id=up.id, user_id=up.user_id, pokemon_id=up.pokemon_id,
                    nickname=up.nickname, is_shiny=up.is_shiny, is_amv=up.is_amv,
                    form_index=up.form_index, serial_number=up.serial_number,
                    level=up.level, xp=up.xp,
                    iv_hp=up.iv_hp, iv_atk=up.iv_atk,
                    iv_def=up.iv_def, iv_spd=up.iv_spd,
                    caught_at=up.caught_at
                ))
        await db.flush()

        # ── 4. Active spawns ─────────────────────────────────────────────────
        print("   [4/12] Copying active spawns...")
        existing = set((await db.execute(select(ActiveSpawn.chat_id))).scalars().all())
        for s in spawns:
            if s.chat_id not in existing:
                db.add(ActiveSpawn(
                    chat_id=s.chat_id, pokemon_id=s.pokemon_id,
                    is_shiny=s.is_shiny, message_id=s.message_id,
                    spawned_at=s.spawned_at
                ))
        await db.flush()

        # ── 5. Group settings ────────────────────────────────────────────────
        print("   [5/12] Copying group settings...")
        existing = set((await db.execute(select(GroupSetting.chat_id))).scalars().all())
        for g in groups:
            if g.chat_id not in existing:
                db.add(GroupSetting(
                    chat_id=g.chat_id, message_counter=g.message_counter,
                    spawn_threshold=g.spawn_threshold, enabled=g.enabled,
                    scribble_enabled=g.scribble_enabled,
                    nameguess_enabled=g.nameguess_enabled
                ))
        await db.flush()

        # ── 6. Global settings ───────────────────────────────────────────────
        print("   [6/12] Copying global settings...")
        existing = set((await db.execute(select(GlobalSetting.key))).scalars().all())
        for gs in globals_:
            if gs.key not in existing:
                db.add(GlobalSetting(key=gs.key, value=gs.value))
        await db.flush()

        # ── 7. Redeem codes ──────────────────────────────────────────────────
        print("   [7/12] Copying redeem codes...")
        existing = set((await db.execute(select(RedeemCode.id))).scalars().all())
        for rc in redeem_codes:
            if rc.id not in existing:
                db.add(RedeemCode(
                    id=rc.id, code=rc.code, reward_type=rc.reward_type,
                    reward_value=rc.reward_value, reward_is_shiny=rc.reward_is_shiny,
                    reward_is_amv=rc.reward_is_amv,
                    reward_form_index=rc.reward_form_index,
                    usage_limit=rc.usage_limit, usage_count=rc.usage_count,
                    created_at=rc.created_at
                ))
        await db.flush()

        # ── 8. Redeem claims ─────────────────────────────────────────────────
        print("   [8/12] Copying redeem claims...")
        existing = set((await db.execute(select(RedeemClaim.id))).scalars().all())
        for claim in redeem_claims:
            if claim.id not in existing:
                db.add(RedeemClaim(
                    id=claim.id, user_id=claim.user_id,
                    code_id=claim.code_id, claimed_at=claim.claimed_at
                ))
        await db.flush()

        # ── 9. Pokémon Form Media ────────────────────────────────────────────
        print("   [9/12] Copying custom form media...")
        existing_res = await db.execute(select(PokemonFormMedia.pokemon_id, PokemonFormMedia.form_index))
        existing = set(existing_res.all())
        for fm in form_media:
            if (fm.pokemon_id, fm.form_index) not in existing:
                db.add(PokemonFormMedia(
                    pokemon_id=fm.pokemon_id,
                    form_index=fm.form_index,
                    media_value=fm.media_value
                ))
        await db.flush()

        # ── 10. PvP Battles ──────────────────────────────────────────────────
        print("   [10/12] Copying PvP battles...")
        existing = set((await db.execute(select(PvpBattle.id))).scalars().all())
        for b in battles:
            if b.id not in existing:
                db.add(PvpBattle(
                    id=b.id, chat_id=b.chat_id, message_id=b.message_id,
                    challenger_id=b.challenger_id, opponent_id=b.opponent_id,
                    bet=b.bet, format_type=b.format_type, status=b.status,
                    draft_json=b.draft_json, created_at=b.created_at
                ))
        await db.flush()

        # ── 11. Auctions ─────────────────────────────────────────────────────
        print("   [11/12] Copying auctions...")
        existing = set((await db.execute(select(Auction.id))).scalars().all())
        for a in auctions:
            if a.id not in existing:
                db.add(Auction(
                    id=a.id, seller_id=a.seller_id, pokemon_id=a.pokemon_id,
                    nickname=a.nickname, is_shiny=a.is_shiny, is_amv=a.is_amv,
                    form_index=a.form_index, serial_number=a.serial_number,
                    level=a.level, xp=a.xp,
                    iv_hp=a.iv_hp, iv_atk=a.iv_atk,
                    iv_def=a.iv_def, iv_spd=a.iv_spd,
                    starting_price=a.starting_price, current_bid=a.current_bid,
                    expires_at=a.expires_at, created_at=a.created_at,
                    status=a.status, channel_message_id=a.channel_message_id,
                    channel_chat_id=a.channel_chat_id
                ))
        await db.flush()

        # ── 12. Auction Bids ─────────────────────────────────────────────────
        print("   [12/12] Copying auction bids...")
        existing = set((await db.execute(select(AuctionBid.id))).scalars().all())
        for bid in bids:
            if bid.id not in existing:
                db.add(AuctionBid(
                    id=bid.id, auction_id=bid.auction_id,
                    bidder_id=bid.bidder_id, amount=bid.amount,
                    bid_at=bid.bid_at
                ))

        await db.commit()

    print("\n✅ Migration Complete! All PostgreSQL data copied to SQLite.")
    print("   You can now remove DATABASE_URL from Render and use SQLite.")


if __name__ == "__main__":
    print("=" * 60)
    print("  PostgreSQL → SQLite Migration Tool")
    print("  PokeEmpire Bot")
    print("=" * 60)
    url = input("\nEnter your PostgreSQL DATABASE_URL: ").strip()
    if not url:
        print("❌ URL cannot be empty.")
        sys.exit(1)
    asyncio.run(migrate_pg_to_sqlite(url))
