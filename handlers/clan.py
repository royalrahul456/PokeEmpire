from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from database.models import User, Clan, ClanMember
from keyboards.inline import get_clan_actions_keyboard, get_clan_list_keyboard

router = Router()

async def get_clan_details_text(db: AsyncSession, clan_id: int) -> str:
    """Helper to format a clean description card of a clan's level, treasury, and members list."""
    stmt = select(Clan).where(Clan.id == clan_id)
    res = await db.execute(stmt)
    clan = res.scalar_one_or_none()
    
    if not clan:
        return "⚠️ Clan not found."

    # Query members count and names
    m_stmt = select(ClanMember).where(ClanMember.clan_id == clan_id)
    m_res = await db.execute(m_stmt)
    members = m_res.scalars().all()

    member_rows = []
    for m in members:
        u_stmt = select(User).where(User.id == m.user_id)
        u_res = await db.execute(u_stmt)
        user = u_res.scalar_one_or_none()
        if user:
            role_badge = "👑" if m.role == "Leader" else "🎖️" if m.role == "Co-Leader" else "👤"
            member_rows.append(f"• {role_badge} **{user.nickname}** - Lvl {user.level} ({m.role})")

    members_text = "\n".join(member_rows)

    text = (
        f"🛡️ **CLAN: {clan.name.upper()}** 🛡️\n"
        f"───────────────\n"
        f"• Clan Level: **Lvl {clan.level}**\n"
        f"• Clan Experience: **{clan.xp} XP**\n"
        f"• Treasury: 🪙 **{clan.coins} Coins**\n"
        f"• Members Count: **{len(members)}/15**\n\n"
        f"👥 **ROSTER**:\n"
        f"{members_text}"
    )
    return text

@router.message(Command("clan"))
@router.callback_query(F.data == "menu_clan")
async def cmd_clan(event: Message | CallbackQuery, db: AsyncSession):
    user_id = event.from_user.id
    
    # Check registration
    u_stmt = select(User).where(User.id == user_id)
    u_res = await db.execute(u_stmt)
    user = u_res.scalar_one_or_none()
    if not user:
        msg = "⚠️ You must register first with /start"
        if isinstance(event, CallbackQuery):
            await event.answer(msg, show_alert=True)
        else:
            await event.answer(msg)
        return

    # Check if user is in a clan
    cm_stmt = select(ClanMember).where(ClanMember.user_id == user_id)
    cm_res = await db.execute(cm_stmt)
    membership = cm_res.scalar_one_or_none()

    if membership:
        # User is in a clan, render details
        text = await get_clan_details_text(db, membership.clan_id)
        keyboard = get_clan_actions_keyboard(has_clan=True)
    else:
        # User is clanless
        text = (
            f"🛡️ **PokeEmpire Clans Hub** 🛡️\n\n"
            f"Clans are cooperatives of trainers that battle together to conquer leaderboards! "
            f"As a clan member, you earn global XP bonuses.\n\n"
            f"You are not currently in a Clan."
        )
        keyboard = get_clan_actions_keyboard(has_clan=False)

    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
        await event.answer()
    else:
        await event.answer(text, reply_markup=keyboard, parse_mode="Markdown")

@router.callback_query(F.data == "clan_create_prompt")
async def callback_clan_create_prompt(callback: CallbackQuery):
    text = (
        "🆕 **Create a Clan**\n\n"
        "To establish a new PokeEmpire Clan, you require at least 🪙 **1000 Coins**.\n\n"
        "Send the command:\n"
        "`/createclan <clan_name>`\n\n"
        "(No special characters, maximum 15 letters)."
    )
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="menu_clan"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@router.message(Command("createclan"))
async def cmd_create_clan(message: Message, db: AsyncSession):
    user_id = message.from_user.id
    
    # Check registration
    u_stmt = select(User).where(User.id == user_id)
    u_res = await db.execute(u_stmt)
    user = u_res.scalar_one_or_none()
    if not user: return

    # Check command params
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("⚠️ Format: `/createclan <name>`")
        return
        
    clan_name = " ".join(parts[1:]).strip()
    if len(clan_name) > 15:
        await message.answer("⚠️ Clan name must be 15 characters or less.")
        return

    # Check if already in a clan
    cm_stmt = select(ClanMember).where(ClanMember.user_id == user_id)
    cm_res = await db.execute(cm_stmt)
    if cm_res.scalar_one_or_none():
        await message.answer("❌ You are already in a clan! Leave your current clan first.")
        return

    # Check if name is taken
    c_name_stmt = select(Clan).where(Clan.name == clan_name)
    c_name_res = await db.execute(c_name_stmt)
    if c_name_res.scalar_one_or_none():
        await message.answer("❌ That clan name is already taken!")
        return

    # Check coins
    if user.coins < 1000:
        await message.answer(f"❌ Creation fee is 🪙 **1000 Coins** (You have 🪙 **{user.coins}**).")
        return

    # Deduct fee and save new clan
    user.coins -= 1000
    
    new_clan = Clan(
        name=clan_name,
        owner_id=user_id,
        level=1,
        xp=0,
        coins=0
    )
    db.add(new_clan)
    await db.flush()  # Populates new_clan.id

    # Add leader to membership
    new_member = ClanMember(
        clan_id=new_clan.id,
        user_id=user_id,
        role="Leader"
    )
    db.add(new_member)
    await db.commit()

    await message.answer(f"🎉 **Clan {clan_name} has been successfully founded!** 🛡️\nEstablish your team, recruit members, and rule the empire!")

@router.callback_query(F.data == "clan_list")
async def callback_clan_list(callback: CallbackQuery, db: AsyncSession):
    # Query clans
    stmt = select(Clan).order_by(Clan.level.desc()).limit(10)
    res = await db.execute(stmt)
    clans = res.scalars().all()

    text = "🔍 **Active Clans List**\nSelect a clan to request membership:\n\n"
    if not clans:
        text += "_No clans have been founded yet._"

    keyboard = get_clan_list_keyboard(clans)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("clan_join_"))
async def callback_clan_join(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id
    clan_id = int(callback.data.split("_")[2])

    # Check if already in a clan
    cm_stmt = select(ClanMember).where(ClanMember.user_id == user_id)
    cm_res = await db.execute(cm_stmt)
    if cm_res.scalar_one_or_none():
        await callback.answer("❌ You are already in a clan!", show_alert=True)
        return

    # Check member limit (max 15 members)
    m_stmt = select(ClanMember).where(ClanMember.clan_id == clan_id)
    m_res = await db.execute(m_stmt)
    members_count = len(m_res.scalars().all())

    if members_count >= 15:
        await callback.answer("❌ This clan is full! (Max 15 members)", show_alert=True)
        return

    # Add user to clan membership
    new_member = ClanMember(
        clan_id=clan_id,
        user_id=user_id,
        role="Member"
    )
    db.add(new_member)
    await db.commit()

    await callback.answer("Successfully joined the clan!")
    await cmd_clan(callback, db)

@router.callback_query(F.data == "clan_leave")
async def callback_clan_leave(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id

    cm_stmt = select(ClanMember).where(ClanMember.user_id == user_id)
    cm_res = await db.execute(cm_stmt)
    membership = cm_res.scalar_one_or_none()

    if not membership:
        await callback.answer("⚠️ You are not in a clan.", show_alert=True)
        return

    # If user is Leader, disband the clan
    if membership.role == "Leader":
        # Delete clan (cascade deletes memberships)
        await db.execute(delete(Clan).where(Clan.id == membership.clan_id))
        await db.commit()
        await callback.answer("🛡️ You disbanded the clan.", show_alert=True)
    else:
        await db.delete(membership)
        await db.commit()
        await callback.answer("You successfully left the clan.")

    await cmd_clan(callback, db)
