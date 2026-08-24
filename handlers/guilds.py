import html
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, func, distinct
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Guild, GuildMember
from utils.trainer_level import log_transaction

router = Router()

async def get_user_guild_data(user_id: int, db: AsyncSession):
    """Helper returning (GuildMember, Guild) for user_id or (None, None)."""
    stmt = select(GuildMember, Guild).join(Guild, GuildMember.guild_id == Guild.id).where(GuildMember.user_id == user_id)
    res = await db.execute(stmt)
    return res.first() or (None, None)

@router.message(Command("guild", "clan"))
async def cmd_guild(message: Message, db: AsyncSession):
    parts = message.text.split(maxsplit=2)
    user_id = message.from_user.id
    
    if len(parts) < 2:
        # Show user's guild info or instructions
        member, guild = await get_user_guild_data(user_id, db)
        if not guild:
            text = (
                f"🏰 <b>TRAINER GUILD CENTER</b> 🏰\n"
                f"◈ ────────────────── ◈\n"
                f"You are currently <b>not in any Guild</b>!\n\n"
                f"💡 <b>Guild Commands</b>:\n"
                f"👉 <code>/guild create &lt;name&gt;</code> — Found a new Guild (5,000 coins)\n"
                f"👉 <code>/guild join &lt;name&gt;</code> — Join an existing Guild\n"
                f"👉 <code>/guildlb</code> — View top Guild Leaderboards\n"
                f"◈ ────────────────── ◈\n"
                f"✨ Guild members receive passive +5% Shiny Chance & +10% Coin Boosts!"
            )
            await message.answer(text, parse_mode="HTML")
            return
            
        # Count members
        mem_stmt = select(func.count(GuildMember.id)).where(GuildMember.guild_id == guild.id)
        mem_res = await db.execute(mem_stmt)
        total_members = mem_res.scalar() or 0
        
        owner_stmt = select(User).where(User.id == guild.owner_id)
        owner_res = await db.execute(owner_stmt)
        owner = owner_res.scalar_one_or_none()
        owner_name = html.escape(owner.nickname or owner.username or f"Trainer {owner.id}") if owner else "Unknown"

        text = (
            f"🏰 <b>GUILD: {html.escape(guild.name).upper()} [{html.escape(guild.tag)}]</b> 🏰\n"
            f"◈ ────────────────── ◈\n"
            f"👑 <b>Leader:</b> {owner_name}\n"
            f"👥 <b>Members:</b> <code>{total_members} members</code>\n"
            f"💎 <b>Guild Level:</b> <code>Lv. {guild.level}</code>\n"
            f"🏛️ <b>Guild Treasury:</b> <code>💰 {guild.treasury:,} coins</code>\n"
            f"⚡ <b>Guild Perks:</b> <code>+5% Shiny Chance | +10% Coin Earnings</code>\n"
            f"◈ ────────────────── ◈\n"
            f"👉 <i>Use <code>/guild deposit &lt;amount&gt;</code> to donate to the Treasury!</i>"
        )
        await message.answer(text, parse_mode="HTML")
        return

    sub = parts[1].lower()

    if sub == "create":
        if len(parts) < 3:
            await message.answer("⚠️ Format: <code>/guild create &lt;Guild Name&gt;</code>", parse_mode="HTML")
            return
            
        guild_name = parts[2].strip()
        if len(guild_name) < 3 or len(guild_name) > 30:
            await message.answer("❌ Guild name must be between 3 and 30 characters.", parse_mode="HTML")
            return

        member, existing_g = await get_user_guild_data(user_id, db)
        if guild:
            await message.answer("❌ You are already in a Guild! Leave your current Guild first with <code>/guild leave</code>.", parse_mode="HTML")
            return

        u_stmt = select(User).where(User.id == user_id)
        u_res = await db.execute(u_stmt)
        user = u_res.scalar_one_or_none()

        creation_fee = 5000
        if not user or user.coins < creation_fee:
            await message.answer(f"❌ Founding a Guild costs <b>💰 {creation_fee:,} coins</b>!", parse_mode="HTML")
            return

        # Check name availability
        chk_stmt = select(Guild).where(func.lower(Guild.name) == guild_name.lower())
        chk_res = await db.execute(chk_stmt)
        if chk_res.scalar_one_or_none():
            await message.answer("❌ A Guild with that name already exists!", parse_mode="HTML")
            return

        tag = guild_name[:3].upper()

        user.coins -= creation_fee
        await log_transaction(user_id, -creation_fee, "GUILD_CREATE", f"Created Guild {guild_name}", db)

        new_guild = Guild(
            name=guild_name,
            tag=tag,
            owner_id=user_id,
            treasury=0,
            level=1
        )
        db.add(new_guild)
        await db.flush()

        gm = GuildMember(
            guild_id=new_guild.id,
            user_id=user_id,
            role="leader"
        )
        db.add(gm)
        await db.commit()

        await message.answer(f"🎉 <b>Guild Created Successfully!</b>\n\n🏰 Welcome to <b>{html.escape(guild_name)}</b>!", parse_mode="HTML")

    elif sub == "join":
        if len(parts) < 3:
            await message.answer("⚠️ Format: <code>/guild join &lt;Guild Name&gt;</code>", parse_mode="HTML")
            return

        target_name = parts[2].strip()
        member, existing_g = await get_user_guild_data(user_id, db)
        if existing_g:
            await message.answer("❌ You are already in a Guild!", parse_mode="HTML")
            return

        g_stmt = select(Guild).where(func.lower(Guild.name) == target_name.lower())
        g_res = await db.execute(g_stmt)
        guild = g_res.scalar_one_or_none()

        if not guild:
            await message.answer("❌ Guild not found. Check spelling and try again.", parse_mode="HTML")
            return

        gm = GuildMember(
            guild_id=guild.id,
            user_id=user_id,
            role="member"
        )
        db.add(gm)
        await db.commit()

        await message.answer(f"🎉 <b>Joined Guild!</b> You are now a member of <b>{html.escape(guild.name)}</b>!", parse_mode="HTML")

    elif sub == "deposit":
        if len(parts) < 3 or not parts[2].isdigit():
            await message.answer("⚠️ Format: <code>/guild deposit &lt;amount&gt;</code>", parse_mode="HTML")
            return

        amount = int(parts[2])
        if amount <= 0:
            await message.answer("❌ Deposit amount must be positive.", parse_mode="HTML")
            return

        member, guild = await get_user_guild_data(user_id, db)
        if not guild:
            await message.answer("❌ You are not in any Guild!", parse_mode="HTML")
            return

        u_stmt = select(User).where(User.id == user_id)
        u_res = await db.execute(u_stmt)
        user = u_res.scalar_one_or_none()

        if not user or user.coins < amount:
            await message.answer(f"❌ Insufficient coins! Your balance: 💰 {user.coins:,} coins.", parse_mode="HTML")
            return

        user.coins -= amount
        guild.treasury += amount
        
        # Check level up (every 50,000 coins in treasury increases level)
        new_lvl = 1 + (guild.treasury // 50000)
        guild.level = max(guild.level, new_lvl)

        await log_transaction(user_id, -amount, "GUILD_DEPOSIT", f"Donated to Guild Treasury", db)
        await db.commit()

        await message.answer(
            f"🏛️ <b>Guild Deposit Successful!</b>\n\n"
            f"You donated <b>💰 {amount:,} coins</b> to <b>{html.escape(guild.name)}</b> Treasury!\n"
            f"New Treasury Balance: <b>💰 {guild.treasury:,} coins</b> (Guild Level: {guild.level}).",
            parse_mode="HTML"
        )

    elif sub == "leave":
        member, guild = await get_user_guild_data(user_id, db)
        if not guild:
            await message.answer("❌ You are not in any Guild!", parse_mode="HTML")
            return

        if guild.owner_id == user_id:
            await message.answer("❌ Guild Leaders cannot leave. Delete or transfer ownership first.", parse_mode="HTML")
            return

        await db.delete(member)
        await db.commit()
        await message.answer(f"🚪 You left <b>{html.escape(guild.name)}</b>.", parse_mode="HTML")

@router.message(Command("guildlb", "clanlb"))
async def cmd_guild_lb(message: Message, db: AsyncSession):
    stmt = select(Guild).order_by(Guild.treasury.desc()).limit(10)
    res = await db.execute(stmt)
    guilds = res.scalars().all()

    if not guilds:
        await message.answer("🏰 No Guilds founded yet! Create one with `/guild create <name>`.")
        return

    rows = []
    for idx, g in enumerate(guilds, start=1):
        rows.append(f"✦ {idx}. 🏰 <b>{html.escape(g.name)}</b> • 💰 {g.treasury:,} coins (Lv. {g.level})")

    ranks_body = "\n".join(rows)

    text = (
        f"⚡ <b>TOP GUILDS LEADERBOARD</b> ⚡\n"
        f"◈ ────────────────── ◈\n"
        f"{ranks_body}\n"
        f"◈ ────────────────── ◈\n"
        f"👉 <i>Found your own Guild with <code>/guild create &lt;name&gt;</code>!</i>"
    )
    await message.answer(text, parse_mode="HTML")
