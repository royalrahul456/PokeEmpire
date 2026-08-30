import os
import json
import asyncio
from aiohttp import web
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database.database import SessionLocal
from database.models import User, Pokemon, UserPokemon, Guild, GuildMember, TrainerQuest, TransactionHistory, PokemonFormMedia, GlobalSetting
from utils.trainer_level import get_trainer_title, get_xp_required_for_next_level

routes = web.RouteTableDef()

# Enable CORS helper
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

@routes.get("/api/stats")
async def handle_stats(request):
    async with SessionLocal() as db:
        u_count = await db.scalar(select(func.count(User.id)))
        p_count = await db.scalar(select(func.count(Pokemon.id)))
        up_count = await db.scalar(select(func.count(UserPokemon.id)))
        g_count = await db.scalar(select(func.count(Guild.id)))
        total_coins = await db.scalar(select(func.sum(User.coins))) or 0

        return json_response({
            "success": True,
            "total_trainers": u_count or 0,
            "total_species": p_count or 0,
            "total_catches": up_count or 0,
            "total_guilds": g_count or 0,
            "coins_in_economy": total_coins
        })

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
                "role": gm.role
            }

        lvl = user.trainer_level or 1
        xp = user.trainer_xp or 0
        req_xp = get_xp_required_for_next_level(lvl)

        return json_response({
            "success": True,
            "trainer": {
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

@routes.get("/api/pokedex/{user_id}")
async def handle_pokedex(request):
    user_id_str = request.match_info.get("user_id")
    if not user_id_str.isdigit():
        return json_response({"success": False, "error": "Invalid user_id"}, status=400)

    user_id = int(user_id_str)
    async with SessionLocal() as db:
        # Get all caught pokemon_ids for this user
        caught_stmt = select(UserPokemon.pokemon_id, func.count(UserPokemon.id)).where(UserPokemon.user_id == user_id).group_by(UserPokemon.pokemon_id)
        caught_res = await db.execute(caught_stmt)
        caught_dict = {row[0]: row[1] for row in caught_res.all()}

        # Get total species count
        total_species = (await db.scalar(select(func.count(Pokemon.id)))) or 0
        unique_caught = len(caught_dict)

        return json_response({
            "success": True,
            "stats": {
                "unique_caught": unique_caught,
                "total_species": total_species,
                "completion_percentage": round((unique_caught / total_species * 100), 2) if total_species > 0 else 0
            },
            "caught_pokemon": caught_dict
        })

@routes.get("/api/pokemon")
async def handle_pokemon(request):
    async with SessionLocal() as db:
        stmt = select(Pokemon).order_by(Pokemon.id.asc())
        res = await db.execute(stmt)
        pokemon_list = res.scalars().all()

        data = []
        for p in pokemon_list:
            data.append({
                "id": p.id,
                "name": p.name,
                "rarity": p.rarity,
                "generation": p.generation,
                "image_url": p.image_url,
                "video_url": p.video_url
            })

        return json_response({"success": True, "count": len(data), "pokemon": data})

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

        return json_response({"success": True, "guilds": guild_list})

@routes.get("/api/leaderboard")
async def handle_leaderboard(request):
    async with SessionLocal() as db:
        # Top Coins
        coins_stmt = select(User).order_by(User.coins.desc()).limit(10)
        coins_res = await db.execute(coins_stmt)
        top_coins = [{
            "id": u.id,
            "name": u.nickname or u.username or f"Trainer {u.id}",
            "coins": u.coins,
            "level": u.trainer_level or 1
        } for u in coins_res.scalars().all()]

        # Top Guilds
        g_stmt = select(Guild).order_by(Guild.treasury.desc()).limit(10)
        g_res = await db.execute(g_stmt)
        top_guilds = [{
            "id": g.id,
            "name": g.name,
            "tag": g.tag,
            "level": g.level,
            "treasury": g.treasury
        } for g in g_res.scalars().all()]

        return json_response({
            "success": True,
            "leaderboards": {
                "coins": top_coins,
                "guilds": top_guilds
            }
        })

@routes.get("/api/arts")
async def handle_arts(request):
    async with SessionLocal() as db:
        # Form media
        fm_stmt = select(PokemonFormMedia)
        fm_res = await db.execute(fm_stmt)
        form_media = [{
            "pokemon_id": fm.pokemon_id,
            "form_index": fm.form_index,
            "media_type": fm.media_type,
            "media_value": fm.media_value
        } for fm in fm_res.scalars().all()]

        # Custom rarities
        gs_stmt = select(GlobalSetting).where(GlobalSetting.key == "custom_rarities")
        gs_res = await db.execute(gs_stmt)
        gs = gs_res.scalar_one_or_none()
        custom_rarities = json.loads(gs.value) if gs else {}

        return json_response({
            "success": True,
            "custom_rarities": custom_rarities,
            "form_media_count": len(form_media),
            "form_media": form_media
        })

@routes.get("/")
@routes.get("/dashboard")
async def handle_dashboard(request):
    html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PokeEmpire Web Dashboard & API</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body { background: #0f172a; color: #e2e8f0; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .hero { background: linear-gradient(135deg, #1e1b4b 0%, #312e81 100%); padding: 2.5rem 1rem; border-radius: 1rem; border: 1px solid #4338ca; margin-bottom: 2rem; }
        .card-custom { background: #1e293b; border: 1px solid #334155; border-radius: 0.75rem; color: #f8fafc; transition: transform 0.2s; }
        .card-custom:hover { transform: translateY(-3px); }
        .badge-gold { background: #f59e0b; color: #000; font-weight: bold; }
        .api-badge { background: #06b6d4; color: #000; font-weight: 600; font-size: 0.8rem; }
        pre { background: #020617; color: #38bdf8; padding: 1rem; border-radius: 0.5rem; }
    </style>
</head>
<body>
    <div class="container my-4">
        <div class="hero text-center shadow">
            <h1 class="display-5 fw-bold text-warning">⚡ PokeEmpire Dashboard & REST API ⚡</h1>
            <p class="lead text-light">Real-time database sync for Trainer Profiles, Guilds, Pokédex, Arts, and Leaderboards!</p>
            <span class="badge badge-gold px-3 py-2 fs-6">v3.0 Mega Update</span>
        </div>

        <div class="row g-4 mb-4">
            <div class="col-md-3">
                <div class="card card-custom p-3 text-center">
                    <h6 class="text-secondary uppercase">Total Species</h6>
                    <h2 class="text-info fw-bold" id="total-species">Loading...</h2>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card card-custom p-3 text-center">
                    <h6 class="text-secondary uppercase">Registered Trainers</h6>
                    <h2 class="text-success fw-bold" id="total-trainers">Loading...</h2>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card card-custom p-3 text-center">
                    <h6 class="text-secondary uppercase">Founded Guilds</h6>
                    <h2 class="text-warning fw-bold" id="total-guilds">Loading...</h2>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card card-custom p-3 text-center">
                    <h6 class="text-secondary uppercase">Total Catches</h6>
                    <h2 class="text-primary fw-bold" id="total-catches">Loading...</h2>
                </div>
            </div>
        </div>

        <div class="card card-custom p-4 mb-4 shadow">
            <h4 class="text-warning mb-3">📡 Available REST API Endpoints</h4>
            <div class="table-responsive">
                <table class="table table-dark table-hover">
                    <thead>
                        <tr><th>Method</th><th>Endpoint</th><th>Description</th></tr>
                    </thead>
                    <tbody>
                        <tr><td><span class="badge api-badge">GET</span></td><td><code>/api/stats</code></td><td>Overall database statistics & economy summary</td></tr>
                        <tr><td><span class="badge api-badge">GET</span></td><td><code>/api/profile/{user_id}</code></td><td>Trainer level, EXP, title, coins, streak & guild info</td></tr>
                        <tr><td><span class="badge api-badge">GET</span></td><td><code>/api/pokedex/{user_id}</code></td><td>Trainer Pokédex checklist & species completion stats</td></tr>
                        <tr><td><span class="badge api-badge">GET</span></td><td><code>/api/guilds</code></td><td>All founded guilds, treasury balance, level & member counts</td></tr>
                        <tr><td><span class="badge api-badge">GET</span></td><td><code>/api/leaderboard</code></td><td>Global Top Coins & Top Guilds leaderboards</td></tr>
                        <tr><td><span class="badge api-badge">GET</span></td><td><code>/api/pokemon</code></td><td>Full Pokémon database with images, video_url & custom media</td></tr>
                        <tr><td><span class="badge api-badge">GET</span></td><td><code>/api/arts</code></td><td>All custom form media, AMVs & custom rarity definitions</td></tr>
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <script>
        async function fetchStats() {
            try {
                const res = await fetch('/api/stats');
                const data = await res.json();
                if(data.success) {
                    document.getElementById('total-species').innerText = data.total_species.toLocaleString();
                    document.getElementById('total-trainers').innerText = data.total_trainers.toLocaleString();
                    document.getElementById('total-guilds').innerText = data.total_guilds.toLocaleString();
                    document.getElementById('total-catches').innerText = data.total_catches.toLocaleString();
                }
            } catch(e) {
                console.error(e);
            }
        }
        fetchStats();
    </script>
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
    print(f"🚀 PokeEmpire Web Dashboard & REST API server running on port {port}!")
