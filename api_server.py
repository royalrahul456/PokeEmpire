import os
import json
import asyncio
from aiohttp import web
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import SessionLocal
from database.models import User, Pokemon, UserPokemon, Guild, GuildMember
from utils.trainer_level import get_trainer_title, get_xp_required_for_next_level

routes = web.RouteTableDef()

def json_response(data, status=200):
    return web.json_response(data, status=status, headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization"
    })

@routes.options("/{tail:.*}")
async def handle_options(request):
    return web.Response(status=204, headers={
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        "Access-Control-Allow-Headers": "Content-Type, Authorization"
    })

@routes.get("/api/health")
@routes.get("/healthz")
async def handle_health(request):
    return json_response({"status": "healthy", "service": "PokeEmpire API"})

# 1. PROFILE API
@routes.get("/api/profile/{user_id}")
async def handle_profile(request):
    user_id_str = request.match_info.get("user_id")
    if not user_id_str.isdigit():
        return json_response({"success": False, "error": "Invalid user_id"}, status=400)

    user_id = int(user_id_str)
    async with SessionLocal() as db:
        stmt = select(User).where(User.id == user_id)
        res = await db.execute(stmt)
        user = res.scalar_one_or_none()

        if not user:
            return json_response({"success": False, "error": "Trainer profile not found"}, status=404)

        catches_stmt = select(func.count(UserPokemon.id)).where(UserPokemon.user_id == user_id)
        total_catches = (await db.scalar(catches_stmt)) or 0

        unique_stmt = select(func.count(func.distinct(UserPokemon.pokemon_id))).where(UserPokemon.user_id == user_id)
        unique_caught = (await db.scalar(unique_stmt)) or 0

        # Guild data
        gm_stmt = select(GuildMember, Guild).join(Guild, GuildMember.guild_id == Guild.id).where(GuildMember.user_id == user_id)
        gm_res = await db.execute(gm_stmt)
        gm_row = gm_res.first()

        guild_info = None
        if gm_row:
            gm, g = gm_row
            guild_info = {
                "id": g.id,
                "name": g.name,
                "tag": g.tag,
                "level": g.level,
                "treasury": g.treasury,
                "role": gm.role
            }

        lvl = user.trainer_level or 1
        xp = user.trainer_xp or 0
        req_xp = get_xp_required_for_next_level(lvl)

        return json_response({
            "success": True,
            "profile": {
                "id": user.id,
                "username": user.username,
                "nickname": user.nickname or user.first_name,
                "level": lvl,
                "title": get_trainer_title(lvl),
                "xp": xp,
                "next_level_xp": req_xp,
                "xp_percentage": min(100, int((xp / req_xp) * 100)) if req_xp > 0 else 0,
                "coins": user.coins,
                "total_catches": total_catches,
                "unique_caught": unique_caught,
                "current_streak": user.current_streak or 0,
                "best_streak": user.best_streak or 0,
                "guild": guild_info
            }
        })

# 2. POKEDEX API
@routes.get("/api/pokedex/{user_id}")
async def handle_pokedex(request):
    user_id_str = request.match_info.get("user_id")
    if not user_id_str.isdigit():
        return json_response({"success": False, "error": "Invalid user_id"}, status=400)

    user_id = int(user_id_str)
    async with SessionLocal() as db:
        caught_stmt = select(UserPokemon.pokemon_id, func.count(UserPokemon.id)).where(UserPokemon.user_id == user_id).group_by(UserPokemon.pokemon_id)
        caught_res = await db.execute(caught_stmt)
        caught_dict = {row[0]: row[1] for row in caught_res.all()}

        total_species = (await db.scalar(select(func.count(Pokemon.id)))) or 0
        unique_caught = len(caught_dict)

        return json_response({
            "success": True,
            "pokedex": {
                "user_id": user_id,
                "unique_caught": unique_caught,
                "total_species": total_species,
                "completion_percentage": round((unique_caught / total_species * 100), 2) if total_species > 0 else 0,
                "caught_species": caught_dict
            }
        })

# 3. GUILDS API
@routes.get("/api/guilds")
async def handle_guilds(request):
    async with SessionLocal() as db:
        stmt = select(Guild).order_by(Guild.treasury.desc())
        res = await db.execute(stmt)
        guilds = res.scalars().all()

        guild_list = []
        for g in guilds:
            mem_count = (await db.scalar(select(func.count(GuildMember.id)).where(GuildMember.guild_id == g.id))) or 0
            guild_list.append({
                "id": g.id,
                "name": g.name,
                "tag": g.tag,
                "level": g.level,
                "treasury": g.treasury,
                "owner_id": g.owner_id,
                "members_count": mem_count
            })

        return json_response({"success": True, "count": len(guild_list), "guilds": guild_list})

@routes.get("/api/guild/{guild_id}")
async def handle_single_guild(request):
    guild_id_str = request.match_info.get("guild_id")
    if not guild_id_str.isdigit():
        return json_response({"success": False, "error": "Invalid guild_id"}, status=400)

    guild_id = int(guild_id_str)
    async with SessionLocal() as db:
        stmt = select(Guild).where(Guild.id == guild_id)
        res = await db.execute(stmt)
        guild = res.scalar_one_or_none()

        if not guild:
            return json_response({"success": False, "error": "Guild not found"}, status=404)

        mems_stmt = select(GuildMember, User).join(User, GuildMember.user_id == User.id).where(GuildMember.guild_id == guild_id)
        mems_res = await db.execute(mems_stmt)
        members = [{
            "id": u.id,
            "name": u.nickname or u.username or f"Trainer {u.id}",
            "role": gm.role,
            "level": u.trainer_level or 1
        } for gm, u in mems_res.all()]

        return json_response({
            "success": True,
            "guild": {
                "id": guild.id,
                "name": guild.name,
                "tag": guild.tag,
                "level": guild.level,
                "treasury": guild.treasury,
                "owner_id": guild.owner_id,
                "members": members
            }
        })

@routes.get("/")
@routes.get("/dashboard")
async def handle_dashboard(request):
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PokeEmpire Core Hub</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .hero { background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%); padding: 2rem 1rem; border-radius: 1rem; border: 1px solid #4338ca; margin-bottom: 2rem; }
        .card-custom { background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; color: #f8fafc; }
        .badge-gold { background: #f59e0b; color: #000; font-weight: bold; }
        .api-badge { background: #06b6d4; color: #000; font-weight: 600; font-size: 0.8rem; }
    </style>
</head>
<body>
    <div class="container my-4">
        <div class="hero text-center shadow">
            <h1 class="display-6 fw-bold text-warning">⚡ PokeEmpire App Sync API ⚡</h1>
            <p class="lead text-light">Focused REST API endpoints for Profile, Pokédex, and Guilds!</p>
            <span class="badge badge-gold px-3 py-2">Profile • Pokédex • Guilds Only</span>
        </div>

        <div class="card card-custom p-4 shadow">
            <h4 class="text-warning mb-3">📡 Active App Endpoints</h4>
            <div class="table-responsive">
                <table class="table table-dark table-hover">
                    <thead>
                        <tr><th>Method</th><th>Endpoint</th><th>Description</th></tr>
                    </thead>
                    <tbody>
                        <tr><td><span class="badge api-badge">GET</span></td><td><code>/api/profile/{user_id}</code></td><td>Trainer Level, EXP, Title, Coins, Streak & Guild details</td></tr>
                        <tr><td><span class="badge api-badge">GET</span></td><td><code>/api/pokedex/{user_id}</code></td><td>Pokédex Checklist & Species Completion %</td></tr>
                        <tr><td><span class="badge api-badge">GET</span></td><td><code>/api/guilds</code></td><td>All founded Guilds, Treasury balance, Level & Member count</td></tr>
                        <tr><td><span class="badge api-badge">GET</span></td><td><code>/api/guild/{guild_id}</code></td><td>Specific Guild details and member roster</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>"""
    return web.Response(text=html_content, content_type="text/html")

async def start_api_server():
    port = int(os.getenv("PORT", "8000"))
    app = web.Application()
    app.add_routes(routes)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🚀 PokeEmpire API server (Profile, Pokédex & Guilds) running on port {port}!")
