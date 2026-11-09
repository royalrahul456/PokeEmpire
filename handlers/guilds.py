import html
import re
import math
from typing import Optional, Tuple
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy import select, func, distinct, delete
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import User, Guild, GuildMember
from utils.trainer_level import log_transaction
from utils.guild_flags import (
    format_guild_flag,
    get_all_guild_flags,
    register_guild_flag,
    delete_guild_flag,
    auto_save_custom_flag_to_db,
    PRESET_GUILD_FLAGS
)
import config

router = Router()

GUILD_CREATION_FEE = 500000  # 500k coins
GUILD_FLAG_COST = 100000     # 100k coins (one-time choice)
FLAGS_PER_PAGE = 6


async def get_user_guild_data(user_id: int, db: AsyncSession):
    """Helper returning (GuildMember, Guild) for user_id or (None, None)."""
    stmt = select(GuildMember, Guild).join(Guild, GuildMember.guild_id == Guild.id).where(GuildMember.user_id == user_id)
    res = await db.execute(stmt)
    return res.first() or (None, None)


def extract_custom_emoji_or_flag(message: Message, param: str = "") -> Tuple[Optional[str], Optional[str], str]:
    """
    Extracts a custom emoji tag or returns the flag string from message/reply.
    Returns (flag_formatted, emoji_id, description) or (None, None, error_msg).
    """
    # 1. Check for custom_emoji entities in message itself
    entities = message.entities or message.caption_entities or []
    for ent in entities:
        if ent.type == "custom_emoji" and ent.custom_emoji_id:
            txt = message.text or message.caption or "🛡️"
            char = txt[ent.offset:ent.offset + ent.length] if ent.offset is not None else "🛡️"
            eid = str(ent.custom_emoji_id)
            return f'<tg-emoji emoji-id="{eid}">{char}</tg-emoji>', eid, f"Custom Animated Emoji ({eid})"

    # 2. Check reply_to_message if user replied to an animated emoji
    if message.reply_to_message:
        rep_entities = message.reply_to_message.entities or message.reply_to_message.caption_entities or []
        for ent in rep_entities:
            if ent.type == "custom_emoji" and ent.custom_emoji_id:
                txt = message.reply_to_message.text or message.reply_to_message.caption or "🛡️"
                char = txt[ent.offset:ent.offset + ent.length] if ent.offset is not None else "🛡️"
                eid = str(ent.custom_emoji_id)
                return f'<tg-emoji emoji-id="{eid}">{char}</tg-emoji>', eid, f"Custom Animated Emoji ({eid})"

    param = param.strip()
    if not param:
        return None, None, "No flag specified."

    # 3. Check if param is already HTML tag
    if "<tg-emoji" in param:
        m = re.search(r'emoji-id="(\d+)"', param)
        eid = m.group(1) if m else None
        return param, eid, "Custom Animated Tag"

    # 4. Check if param is numeric custom emoji ID
    if param.isdigit():
        return f'<tg-emoji emoji-id="{param}">🛡️</tg-emoji>', param, f"Custom Emoji ID ({param})"

    # 5. Check if matches preset
    low_param = param.lower()
    if low_param in PRESET_GUILD_FLAGS:
        preset = PRESET_GUILD_FLAGS[low_param]
        return preset.get("tag", preset.get("fallback", "🛡️")), preset.get("emoji_id"), preset.get("name", "Preset Flag")

    # 6. Plain emoji/text
    return param[:30], None, "Custom Guild Flag"

async def find_guild_holding_flag(flag_val: str, exclude_guild_id: Optional[int], db: AsyncSession) -> Optional[Guild]:
    """
    Checks if any other Guild is already flying or claimed this exact flag.
    Returns the Guild object or None.
    """
    if not flag_val or flag_val == "🛡️":
        return None

    norm_flag = format_guild_flag(flag_val)
    stmt = select(Guild).where(Guild.flag.is_not(None), Guild.flag != "🛡️")
    if exclude_guild_id:
        stmt = stmt.where(Guild.id != exclude_guild_id)
    res = await db.execute(stmt)
    guilds = res.scalars().all()

    for g in guilds:
        if g.flag == flag_val or format_guild_flag(g.flag) == norm_flag:
            return g
    return None


async def get_all_claimed_flags_map(db: AsyncSession) -> dict:
    """Returns a dict mapping flag variations to (guild_name, guild_tag, guild_id)."""
    stmt = select(Guild.flag, Guild.name, Guild.tag, Guild.id).where(Guild.flag.is_not(None), Guild.flag != "🛡️")
    res = await db.execute(stmt)
    claimed = {}
    for g_flag, g_name, g_tag, g_id in res.all():
        claimed[g_flag] = (g_name, g_tag, g_id)
        norm = format_guild_flag(g_flag)
        claimed[norm] = (g_name, g_tag, g_id)
    return claimed


async def build_flag_store_payload(user_id: int, page: int, db: AsyncSession):
    """Generates text and pagination keyboard for the Guild Flag Store with exclusivity."""
    all_flags = await get_all_guild_flags(db)
    flag_keys = list(all_flags.keys())
    total_items = len(flag_keys)
    total_pages = max(1, math.ceil(total_items / FLAGS_PER_PAGE))
    page = max(1, min(page, total_pages))

    start_idx = (page - 1) * FLAGS_PER_PAGE
    end_idx = start_idx + FLAGS_PER_PAGE
    page_keys = flag_keys[start_idx:end_idx]

    member, guild = await get_user_guild_data(user_id, db)
    u_stmt = select(User).where(User.id == user_id)
    u_res = await db.execute(u_stmt)
    user = u_res.scalar_one_or_none()
    user_coins = user.coins if user else 0

    is_leader = (guild and guild.owner_id == user_id) or (user_id in getattr(config, "ADMIN_IDS", []))
    is_locked = getattr(guild, "flag_locked", False) if guild else False
    curr_flag = format_guild_flag(getattr(guild, "flag", "🛡️")) if guild else "None"

    # Get claimed flags map: flag -> (guild_name, guild_tag, guild_id)
    claimed_map = await get_all_claimed_flags_map(db)

    status_str = "🔒 <b>Flag Locked</b> (Already chosen)" if is_locked else ("🔓 <b>Ready to Choose</b> (💰 100k)" if is_leader else "👥 Member (Leader only)")

    # Format items
    item_lines = []
    for idx, k in enumerate(page_keys, start=start_idx + 1):
        v = all_flags[k]
        display_tag = v.get("tag", v.get("fallback", "🛡️"))
        norm_tag = format_guild_flag(display_tag)
        name = v.get("name", k.title())

        claimed_info = claimed_map.get(k) or claimed_map.get(display_tag) or claimed_map.get(norm_tag)
        if claimed_info:
            c_name, c_tag, c_id = claimed_info
            if guild and c_id == guild.id:
                item_lines.append(f"✦ {idx}. {display_tag} <b>{html.escape(name)}</b> • 👑 <i>YOUR GUILD FLAG</i>")
            else:
                item_lines.append(f"✦ {idx}. {display_tag} <b>{html.escape(name)}</b> • 🔴 <b>SOLD OUT</b> <i>([{html.escape(c_tag)}])</i>")
        else:
            item_lines.append(f"✦ {idx}. {display_tag} <b>{html.escape(name)}</b> • 🟢 <i>Available (💰 100k)</i>")

    body_text = "\n".join(item_lines) if item_lines else "<i>No flags found in store.</i>"

    text = (
        f"🏰 <b>GUILD FLAG STORE (EXCLUSIVE)</b> 🏰\n"
        f"◈ ────────────────────────── ◈\n"
        f"💰 <b>Price:</b> <code>{GUILD_FLAG_COST:,} coins</code> per flag\n"
        f"👛 <b>Your Balance:</b> <code>💰 {user_coins:,} coins</code>\n"
        f"🚩 <b>Current Flag:</b> {curr_flag} ({status_str})\n"
        f"👑 <b>Exclusivity:</b> <i>1 Flag = 1 Guild Only (No duplicate flags across guilds!)</i>\n"
        f"◈ ────────────────────────── ◈\n"
        f"✨ <i>No Telegram Premium required! Tap any flag button below to buy and claim it exclusively for your Guild!</i>\n\n"
        f"{body_text}\n\n"
        f"◈ ────────────────────────── ◈\n"
        f"⚠️ <b>Note:</b> Once claimed by a Guild, that flag is <b>SOLD OUT</b> and cannot be bought by anyone else!"
    )

    builder = InlineKeyboardBuilder()

    # Buy / Select Buttons
    row = []
    for k in page_keys:
        v = all_flags[k]
        icon = v.get("fallback", "🛡️")
        display_tag = v.get("tag", v.get("fallback", "🛡️"))
        norm_tag = format_guild_flag(display_tag)
        name = v.get("name", k.title())
        short_name = name[:10]

        claimed_info = claimed_map.get(k) or claimed_map.get(display_tag) or claimed_map.get(norm_tag)
        if claimed_info:
            c_name, c_tag, c_id = claimed_info
            if guild and c_id == guild.id:
                btn_text = f"👑 {icon} Owned"
                row.append(InlineKeyboardButton(text=btn_text, callback_data="gflag_owned"))
            else:
                btn_text = f"🔴 {icon} Taken"
                row.append(InlineKeyboardButton(text=btn_text, callback_data=f"gflag_taken:{c_tag}"))
        else:
            if is_locked and user_id not in getattr(config, "ADMIN_IDS", []):
                btn_text = f"{icon} {short_name}"
                row.append(InlineKeyboardButton(text=btn_text, callback_data="gflag_noop"))
            else:
                btn_text = f"Buy {icon} {short_name}"
                row.append(InlineKeyboardButton(text=btn_text, callback_data=f"gflag_buy:{k}:{page}"))

        if len(row) == 2:
            builder.row(*row)
            row = []
    if row:
        builder.row(*row)

    # Navigation buttons
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"gflag_store_page_{page - 1}"))
    nav_row.append(InlineKeyboardButton(text=f"📑 {page}/{total_pages}", callback_data="gflag_noop"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="Next ▶️", callback_data=f"gflag_store_page_{page + 1}"))
    builder.row(*nav_row)

    # Bottom shortcut
    builder.row(
        InlineKeyboardButton(text="🏰 Guild Center", callback_data="gflag_back"),
        InlineKeyboardButton(text="🛒 Main Shop", callback_data="dm_shop")
    )

    return text, builder.as_markup()


@router.message(Command("flagstore", "flags", "flagshop", "guildstore", "guildflags", ignore_mention=True))
async def cmd_flag_store(message: Message, db: AsyncSession):
    """Direct command to open the Guild Flag Store."""
    user_id = message.from_user.id
    text, markup = await build_flag_store_payload(user_id=user_id, page=1, db=db)
    await message.answer(text, reply_markup=markup, parse_mode="HTML")


@router.callback_query(F.data.startswith("gflag_store_page_"))
async def cb_flag_store_page(callback: CallbackQuery, db: AsyncSession):
    """Handles Flag Store page navigation."""
    user_id = callback.from_user.id
    page = int(callback.data.split("_")[-1])
    text, markup = await build_flag_store_payload(user_id=user_id, page=page, db=db)
    try:
        await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        try:
            await callback.message.edit_caption(caption=text, reply_markup=markup, parse_mode="HTML")
        except Exception:
            await callback.message.answer(text, reply_markup=markup, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "gflag_noop")
async def cb_gflag_noop(callback: CallbackQuery):
    await callback.answer()

@router.callback_query(F.data.startswith("gflag_taken:"))
async def cb_gflag_taken(callback: CallbackQuery):
    tag = callback.data.split(":", 1)[1]
    await callback.answer(f"❌ SOLD OUT! This flag is already claimed by Guild [{tag}] and cannot be bought by any other guild.", show_alert=True)


@router.callback_query(F.data == "gflag_owned")
async def cb_gflag_owned(callback: CallbackQuery):
    await callback.answer("👑 This is your Guild's exclusive official flag!", show_alert=True)



@router.callback_query(F.data.startswith("gflag_buy:"))
async def cb_guild_flag_buy(callback: CallbackQuery, db: AsyncSession):
    """Purchases selected flag from Store for 100k coins."""
    parts = callback.data.split(":")
    flag_key = parts[1]
    page = int(parts[2]) if len(parts) >= 3 else 1
    user_id = callback.from_user.id

    member, guild = await get_user_guild_data(user_id, db)
    if not guild:
        await callback.answer("❌ You are not in any Guild! Join or create one first.", show_alert=True)
        return

    if guild.owner_id != user_id and user_id not in getattr(config, "ADMIN_IDS", []):
        await callback.answer("❌ Only the Guild Leader can purchase and set the Guild Flag!", show_alert=True)
        return

    if getattr(guild, "flag_locked", False) and user_id not in getattr(config, "ADMIN_IDS", []):
        await callback.answer("❌ Guild Flag is already chosen and permanently locked!", show_alert=True)
        return

    u_stmt = select(User).where(User.id == user_id)
    u_res = await db.execute(u_stmt)
    user = u_res.scalar_one_or_none()

    if not user or user.coins < GUILD_FLAG_COST:
        user_coins = user.coins if user else 0
        await callback.answer(f"❌ Flag costs 100,000 coins! Your balance: {user_coins:,}.", show_alert=True)
        return

    all_flags = await get_all_guild_flags(db)
    if flag_key not in all_flags:
        await callback.answer("Flag not found in store!", show_alert=True)
        return

    preset = all_flags[flag_key]
    flag_val = preset.get("tag", preset.get("fallback", "🛡️"))

    # Exclusivity check: Ensure no other guild already has this flag
    existing_owner = await find_guild_holding_flag(flag_val, guild.id, db)
    if not existing_owner:
        existing_owner = await find_guild_holding_flag(flag_key, guild.id, db)
    if existing_owner:
        await callback.answer(f"❌ SOLD OUT! Already claimed by Guild [{existing_owner.tag}] {existing_owner.name}!", show_alert=True)
        return

    # Deduct 100k coins
    user.coins -= GUILD_FLAG_COST
    await log_transaction(user_id, -GUILD_FLAG_COST, "GUILD_FLAG", f"Bought Flag {preset.get('name')} for {guild.name}", db)

    guild.flag = flag_val
    guild.flag_locked = True
    await db.commit()

    display_flag = format_guild_flag(flag_val)
    await callback.answer(f"🎉 Purchased {preset.get('name')}! Flag permanently set.", show_alert=True)

    # Refresh store view with locked status
    text, markup = await build_flag_store_payload(user_id=user_id, page=page, db=db)
    try:
        await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=markup, parse_mode="HTML")


@router.message(Command("addflag", ignore_mention=True))
async def cmd_addflag_standalone(message: Message, db: AsyncSession):
    """Admin command: /addflag <name> (reply to an animated custom emoji)."""
    user_id = message.from_user.id
    if user_id not in getattr(config, "ADMIN_IDS", []):
        await message.answer("❌ Owner/Admin only command.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer(
            "⚠️ <b>How to add a flag to the Store:</b>\n"
            "Reply to any Telegram custom animated emoji with:\n"
            "<code>/addflag &lt;Flag Name&gt;</code>\n\n"
            "Example: Reply to One Piece skull with <code>/addflag Straw Hat Pirate Flag</code>",
            parse_mode="HTML"
        )
        return

    flag_name = parts[1].strip()
    flag_val, emoji_id, _ = extract_custom_emoji_or_flag(message, "")
    if not emoji_id:
        await message.answer("❌ Please reply to a message containing a Telegram custom animated emoji.")
        return

    # Auto-generate a clean slug key
    slug = re.sub(r'[^a-zA-Z0-9]+', '_', flag_name.lower()).strip('_')
    if not slug:
        slug = f"flag_{emoji_id}"

    success = await register_guild_flag(slug, flag_name, emoji_id, "🛡️", db)
    if success:
        tag = f'<tg-emoji emoji-id="{emoji_id}">🛡️</tg-emoji>'
        await message.answer(
            f"✅ <b>Flag Added to Store Successfully!</b>\n"
            f"◈ ────────────────────────── ◈\n"
            f"• <b>Name:</b> {html.escape(flag_name)}\n"
            f"• <b>Preview:</b> {tag}\n"
            f"• <b>Key:</b> <code>{slug}</code>\n"
            f"• <b>Price:</b> <code>100,000 coins</code>\n"
            f"◈ ────────────────────────── ◈\n"
            f"All Guild Leaders can now view and purchase this flag in <code>/flagstore</code> without needing Telegram Premium!",
            parse_mode="HTML"
        )
    else:
        await message.answer("❌ Failed to save new flag to database.")


@router.message(Command("delflag", ignore_mention=True))
async def cmd_delflag_standalone(message: Message, db: AsyncSession):
    """Admin command: /delflag <key> to remove a flag from the store."""
    user_id = message.from_user.id
    if user_id not in getattr(config, "ADMIN_IDS", []):
        await message.answer("❌ Owner/Admin only command.")
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        await message.answer("⚠️ Format: <code>/delflag &lt;key&gt;</code>", parse_mode="HTML")
        return

    flag_key = parts[1].strip().lower()
    success = await delete_guild_flag(flag_key, db)
    if success:
        await message.answer(f"✅ Flag <code>{flag_key}</code> was removed from the Store.")
    else:
        await message.answer(f"❌ Flag <code>{flag_key}</code> not found in custom database flags.")


@router.message(Command("guild", "clan", ignore_mention=True))
async def cmd_guild(message: Message, db: AsyncSession):
    parts = message.text.split(maxsplit=2)
    user_id = message.from_user.id
    
    if len(parts) < 2:
        member, guild = await get_user_guild_data(user_id, db)
        if not guild:
            text = (
                f"🏰 <b>TRAINER GUILD CENTER</b> 🏰\n"
                f"◈ ────────────────── ◈\n"
                f"You are currently <b>not in any Guild</b>!\n\n"
                f"💡 <b>Guild Commands</b>:\n"
                f"👉 <code>/guild create &lt;name&gt;</code> — Found a new Guild (500k coins)\n"
                f"👉 <code>/guild join &lt;name&gt;</code> — Join an existing Guild\n"
                f"👉 <code>/flagstore</code> — Browse & buy animated flags (100k coins)\n"
                f"👉 <code>/guild deposit &lt;amount&gt;</code> — Donate coins to Treasury\n"
                f"👉 <code>/guild withdraw &lt;amount&gt;</code> — Withdraw coins from Treasury (Leader only)\n"
                f"👉 <code>/guild transfer &lt;name&gt; &lt;user&gt;</code> — Transfer Guild Ownership\n"
                f"👉 <code>/guild delete</code> — Disband/Delete your Guild (Owner only)\n"
                f"👉 <code>/guild leave</code> — Leave your current Guild\n"
                f"👉 <code>/guildlb</code> — View top Guild Leaderboards\n"
                f"◈ ────────────────── ◈\n"
                f"✨ Guild members receive passive +5% Shiny Chance & +10% Coin Boosts!"
            )
            await message.answer(text, parse_mode="HTML")
            return
            
        mem_stmt = select(func.count(GuildMember.id)).where(GuildMember.guild_id == guild.id)
        mem_res = await db.execute(mem_stmt)
        total_members = mem_res.scalar() or 0
        
        owner_stmt = select(User).where(User.id == guild.owner_id)
        owner_res = await db.execute(owner_stmt)
        owner = owner_res.scalar_one_or_none()
        owner_name = html.escape(owner.nickname or owner.username or f"Trainer {owner.id}") if owner else "Unknown"

        flag = format_guild_flag(getattr(guild, "flag", "🛡️"))
        is_locked = getattr(guild, "flag_locked", False)
        lock_status_text = "🔒 <i>Official Flag (Locked)</i>" if is_locked else "🔓 <i>Not Set (100k coins to buy)</i>"

        leader_tip = (
            f"👉 <i>Use <code>/guild withdraw &lt;amount&gt;</code> to withdraw from Treasury!</i>\n"
            f"👉 <i>Use <code>/flagstore</code> to buy your official Guild Flag (💰 100k, one-time)!</i>"
            if (guild.owner_id == user_id and not is_locked)
            else (
                f"👉 <i>Use <code>/guild withdraw &lt;amount&gt;</code> to withdraw from Treasury!</i>"
                if guild.owner_id == user_id
                else f"👉 <i>Use <code>/guild deposit &lt;amount&gt;</code> to donate to the Treasury!</i>"
            )
        )

        text = (
            f"🏰 {flag} <b>GUILD: {html.escape(guild.name).upper()} [{html.escape(guild.tag)}]</b> {flag} 🏰\n"
            f"◈ ────────────────── ◈\n"
            f"👑 <b>Leader:</b> {owner_name}\n"
            f"🚩 <b>Guild Flag:</b> {flag} • {lock_status_text}\n"
            f"👥 <b>Members:</b> <code>{total_members} members</code>\n"
            f"💎 <b>Guild Level:</b> <code>Lv. {guild.level}</code>\n"
            f"🏛️ <b>Guild Treasury:</b> <code>💰 {guild.treasury:,} coins</code>\n"
            f"⚡ <b>Guild Perks:</b> <code>+5% Shiny Chance | +10% Coin Earnings</code>\n"
            f"◈ ────────────────── ◈\n"
            f"{leader_tip}"
        )
        builder = InlineKeyboardBuilder()
        btn_title = "🚩 View Flag Store" if is_locked else "🚩 Flag Store (💰 100k)"
        builder.row(InlineKeyboardButton(text=btn_title, callback_data="gflag_store_page_1"))
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
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
        if existing_g:
            await message.answer("❌ You are already in a Guild! Leave your current Guild first with <code>/guild leave</code>.", parse_mode="HTML")
            return

        u_stmt = select(User).where(User.id == user_id)
        u_res = await db.execute(u_stmt)
        user = u_res.scalar_one_or_none()

        if not user or user.coins < GUILD_CREATION_FEE:
            await message.answer(f"❌ Founding a Guild costs <b>💰 {GUILD_CREATION_FEE:,} coins</b> (500k)! Your balance: 💰 {user.coins:,} coins.", parse_mode="HTML")
            return

        chk_stmt = select(Guild).where(func.lower(Guild.name) == guild_name.lower())
        chk_res = await db.execute(chk_stmt)
        if chk_res.scalar_one_or_none():
            await message.answer("❌ A Guild with that name already exists!", parse_mode="HTML")
            return

        tag = guild_name[:3].upper()

        user.coins -= GUILD_CREATION_FEE
        await log_transaction(user_id, -GUILD_CREATION_FEE, "GUILD_CREATE", f"Created Guild {guild_name}", db)

        new_guild = Guild(
            name=guild_name,
            tag=tag,
            owner_id=user_id,
            treasury=0,
            level=1,
            flag="🛡️",
            flag_locked=False
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

        await message.answer(
            f"🎉 <b>Guild Created Successfully!</b>\n\n"
            f"🏰 Welcome to 🛡️ <b>{html.escape(guild_name)}</b> [{tag}]!\n"
            f"👉 <i>Visit <code>/flagstore</code> to buy an official animated flag (💰 100k, one-time choice)!</i>",
            parse_mode="HTML"
        )

    elif sub in ["store", "flagstore", "flag", "flags"]:
        text, markup = await build_flag_store_payload(user_id=user_id, page=1, db=db)
        await message.answer(text, reply_markup=markup, parse_mode="HTML")

    elif sub in ["setflag", "changeflag"]:
        member, guild = await get_user_guild_data(user_id, db)
        if not guild:
            await message.answer("❌ You are not in any Guild!", parse_mode="HTML")
            return

        if guild.owner_id != user_id and user_id not in getattr(config, "ADMIN_IDS", []):
            await message.answer("❌ Only the Guild Leader can set the Guild Flag!", parse_mode="HTML")
            return

        if getattr(guild, "flag_locked", False) and user_id not in getattr(config, "ADMIN_IDS", []):
            curr_flag = format_guild_flag(getattr(guild, "flag", "🛡️"))
            await message.answer(
                f"❌ <b>Guild Flag Already Set!</b>\n\n"
                f"Your Guild is already flying {curr_flag}!\n"
                f"Guild Flags can only be chosen <b>one time</b> for 100k coins and cannot be changed.",
                parse_mode="HTML"
            )
            return

        param = parts[2] if len(parts) >= 3 else ""
        flag_val, emoji_id, desc = extract_custom_emoji_or_flag(message, param)

        if not flag_val:
            await message.answer(
                "⚠️ <b>How to get a Guild Flag:</b>\n\n"
                "💰 <b>Cost:</b> 100,000 coins (One-time choice)\n"
                "1️⃣ <b>Browse Store:</b> Open <code>/flagstore</code> to pick and buy directly with buttons (No Telegram Premium needed!)\n"
                "2️⃣ <b>Direct Emoji:</b> Send <code>/guild setflag 🏴‍☠️</code> or reply to an animated emoji with <code>/guild setflag</code>!",
                parse_mode="HTML"
            )
            return

        u_stmt = select(User).where(User.id == user_id)
        u_res = await db.execute(u_stmt)
        user = u_res.scalar_one_or_none()

        # Exclusivity check: Ensure no other guild has this flag
        existing_owner = await find_guild_holding_flag(flag_val, guild.id, db)
        if existing_owner:
            await message.answer(
                f"❌ <b>Flag Already Claimed!</b>\n\n"
                f"This flag is exclusively owned by <b>{html.escape(existing_owner.name)}</b> [{existing_owner.tag}]!\n"
                f"Each Guild Flag is <b>one-of-a-kind</b> and can only belong to ONE Guild.\n\n"
                f"👉 <i>Browse available flags in <code>/flagstore</code>!</i>",
                parse_mode="HTML"
            )
            return

        if not user or user.coins < GUILD_FLAG_COST:
            user_coins = user.coins if user else 0
            await message.answer(
                f"❌ Choosing an official Guild Flag costs <b>💰 {GUILD_FLAG_COST:,} coins</b> (100k)!\n"
                f"Your current balance: <b>💰 {user_coins:,} coins</b>.",
                parse_mode="HTML"
            )
            return

        user.coins -= GUILD_FLAG_COST
        await log_transaction(user_id, -GUILD_FLAG_COST, "GUILD_FLAG", f"Purchased official Flag for Guild {guild.name}", db)

        if emoji_id:
            await auto_save_custom_flag_to_db(emoji_id, "🛡️", db, name=f"{guild.name} Banner")

        guild.flag = flag_val
        guild.flag_locked = True
        await db.commit()

        display_flag = format_guild_flag(flag_val)
        await message.answer(
            f"🎉 <b>Guild Flag Chosen & Locked!</b>\n"
            f"◈ ────────────────── ◈\n"
            f"🏰 Guild: <b>{html.escape(guild.name)}</b> [{guild.tag}]\n"
            f"🚩 Official Flag: {display_flag}\n"
            f"💰 Fee Paid: <code>-{GUILD_FLAG_COST:,} coins</code>\n"
            f"🔒 Status: <b>Permanently Locked</b> (One-time choice)\n"
            f"◈ ────────────────── ◈\n"
            f"Your new animated flag is permanently autosaved in the database and flying proudly across PokéEmpire!",
            parse_mode="HTML"
        )

    elif sub == "resetflag":
        if user_id not in getattr(config, "ADMIN_IDS", []):
            await message.answer("❌ Owner/Admin only command.")
            return

        if len(parts) < 3:
            await message.answer("⚠️ Format: <code>/guild resetflag &lt;Guild Name&gt;</code>", parse_mode="HTML")
            return

        target_name = parts[2].strip()
        g_stmt = select(Guild).where(func.lower(Guild.name) == target_name.lower())
        g_res = await db.execute(g_stmt)
        t_guild = g_res.scalar_one_or_none()

        if not t_guild:
            await message.answer(f"❌ Guild '{target_name}' not found.")
            return

        t_guild.flag_locked = False
        t_guild.flag = "🛡️"
        await db.commit()
        await message.answer(f"✅ Guild <b>{html.escape(t_guild.name)}</b> flag has been unlocked and reset to default.", parse_mode="HTML")

    elif sub == "addflag":
        if user_id not in getattr(config, "ADMIN_IDS", []):
            await message.answer("❌ Owner/Admin only command.")
            return

        if len(parts) < 3:
            await message.answer("⚠️ Format: Reply to an animated emoji with <code>/guild addflag &lt;Flag Title&gt;</code>", parse_mode="HTML")
            return

        flag_name = parts[2].strip()
        flag_val, emoji_id, _ = extract_custom_emoji_or_flag(message, "")
        if not emoji_id:
            await message.answer("❌ Please reply to a message containing a Telegram custom animated emoji.")
            return

        slug = re.sub(r'[^a-zA-Z0-9]+', '_', flag_name.lower()).strip('_')
        success = await register_guild_flag(slug, flag_name, emoji_id, "🛡️", db)
        if success:
            tag = f'<tg-emoji emoji-id="{emoji_id}">🛡️</tg-emoji>'
            await message.answer(
                f"✅ <b>Added to Flag Store!</b>\n\n"
                f"• Name: <b>{html.escape(flag_name)}</b>\n"
                f"• Preview: {tag}\n"
                f"• Key: <code>{slug}</code>\n\n"
                f"All Guild Leaders can now buy this from <code>/flagstore</code> for 100k coins!",
                parse_mode="HTML"
            )
        else:
            await message.answer("❌ Failed to save new flag to database.")

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

        flag = format_guild_flag(getattr(guild, "flag", "🛡️"))
        await message.answer(f"🎉 <b>Joined Guild!</b> You are now a member of {flag} <b>{html.escape(guild.name)}</b>!", parse_mode="HTML")

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
        
        new_lvl = 1 + (guild.treasury // 50000)
        guild.level = max(guild.level, new_lvl)

        await log_transaction(user_id, -amount, "GUILD_DEPOSIT", f"Donated to Guild Treasury", db)
        await db.commit()

        flag = format_guild_flag(getattr(guild, "flag", "🛡️"))
        await message.answer(
            f"🏛️ <b>Guild Deposit Successful!</b>\n\n"
            f"You donated <b>💰 {amount:,} coins</b> to {flag} <b>{html.escape(guild.name)}</b> Treasury!\n"
            f"New Treasury Balance: <b>💰 {guild.treasury:,} coins</b> (Guild Level: {guild.level}).",
            parse_mode="HTML"
        )

    elif sub in ["withdraw", "withdrawal"]:
        if len(parts) < 3 or not parts[2].isdigit():
            await message.answer("⚠️ Format: <code>/guild withdraw &lt;amount&gt;</code>", parse_mode="HTML")
            return

        amount = int(parts[2])
        if amount <= 0:
            await message.answer("❌ Withdrawal amount must be greater than zero.", parse_mode="HTML")
            return

        member, guild = await get_user_guild_data(user_id, db)
        if not guild:
            await message.answer("❌ You are not in any Guild!", parse_mode="HTML")
            return

        if guild.owner_id != user_id and user_id not in getattr(config, "OWNER_IDS", []):
            await message.answer("❌ Only the Guild Leader can withdraw coins from the Treasury!", parse_mode="HTML")
            return

        if guild.treasury < amount:
            await message.answer(
                f"❌ Insufficient Treasury funds! Current Treasury: <b>💰 {guild.treasury:,} coins</b>.",
                parse_mode="HTML"
            )
            return

        u_stmt = select(User).where(User.id == user_id)
        u_res = await db.execute(u_stmt)
        user = u_res.scalar_one_or_none()
        if not user:
            user = User(id=user_id, username=message.from_user.username, nickname=message.from_user.first_name)
            db.add(user)
            await db.flush()

        guild.treasury -= amount
        user.coins += amount

        await log_transaction(user_id, amount, "GUILD_WITHDRAW", f"Withdrew from {guild.name} Treasury", db)
        await db.commit()

        leader_name = user.nickname or user.username or message.from_user.first_name or "Trainer"
        flag = format_guild_flag(getattr(guild, "flag", "🛡️"))
        await message.answer(
            f"🏛️ <b>Guild Treasury Withdrawal Successful!</b>\n"
            f"◈ ────────────────── ◈\n"
            f"👑 <b>Leader:</b> {html.escape(leader_name)}\n"
            f"🏰 <b>Guild:</b> {flag} {html.escape(guild.name)}\n"
            f"💰 <b>Withdrawn:</b> <code>+{amount:,} coins</code>\n"
            f"🏛️ <b>Remaining Treasury:</b> <code>💰 {guild.treasury:,} coins</code>\n"
            f"👤 <b>Your New Balance:</b> <code>💰 {user.coins:,} coins</code>\n"
            f"◈ ────────────────── ◈",
            parse_mode="HTML"
        )

    elif sub == "leave":
        member, guild = await get_user_guild_data(user_id, db)
        if not guild:
            await message.answer("❌ You are not in any Guild!", parse_mode="HTML")
            return

        if guild.owner_id == user_id:
            await message.answer("❌ Guild Leaders cannot leave. Use <code>/guild transfer &lt;user&gt;</code> to transfer ownership or <code>/guild delete</code> to disband the Guild.", parse_mode="HTML")
            return

        await db.delete(member)
        await db.commit()
        await message.answer(f"🚪 You left <b>{html.escape(guild.name)}</b>.", parse_mode="HTML")

    elif sub in ["delete", "disband"]:
        member, guild = await get_user_guild_data(user_id, db)
        if not guild:
            await message.answer("❌ You are not in any Guild!", parse_mode="HTML")
            return

        if guild.owner_id != user_id and user_id not in config.ADMIN_IDS:
            await message.answer("❌ Only the Guild Leader can delete or disband the Guild!", parse_mode="HTML")
            return

        guild_name = guild.name
        del_mems = delete(GuildMember).where(GuildMember.guild_id == guild.id)
        await db.execute(del_mems)
        await db.delete(guild)
        await db.commit()

        await message.answer(f"🗑️ Guild <b>{html.escape(guild_name)}</b> has been successfully disbanded and deleted!", parse_mode="HTML")

    elif sub in ["transfer", "transferowner", "transferownership"]:
        raw_cmd = message.text or message.caption or ""
        match = re.search(r'\b(?:transfer|transferowner|transferownership)\b(.*)', raw_cmd, re.IGNORECASE | re.DOTALL)
        cmd_args = match.group(1).strip() if match else ""
        await handle_guild_transfer_flow(message, cmd_args, db)
        return


@router.callback_query(F.data == "gflag_back")
async def cb_guild_flag_back(callback: CallbackQuery, db: AsyncSession):
    """Returns to Guild overview from flag menu."""
    user_id = callback.from_user.id
    member, guild = await get_user_guild_data(user_id, db)
    if not guild:
        await callback.answer()
        return

    mem_stmt = select(func.count(GuildMember.id)).where(GuildMember.guild_id == guild.id)
    mem_res = await db.execute(mem_stmt)
    total_members = mem_res.scalar() or 0

    owner_stmt = select(User).where(User.id == guild.owner_id)
    owner_res = await db.execute(owner_stmt)
    owner = owner_res.scalar_one_or_none()
    owner_name = html.escape(owner.nickname or owner.username or f"Trainer {owner.id}") if owner else "Unknown"
    flag = format_guild_flag(getattr(guild, "flag", "🛡️"))
    is_locked = getattr(guild, "flag_locked", False)
    lock_status_text = "🔒 <i>Official Flag (Locked)</i>" if is_locked else "🔓 <i>Not Set (100k coins to buy)</i>"

    text = (
        f"🏰 {flag} <b>GUILD: {html.escape(guild.name).upper()} [{html.escape(guild.tag)}]</b> {flag} 🏰\n"
        f"◈ ────────────────── ◈\n"
        f"👑 <b>Leader:</b> {owner_name}\n"
        f"🚩 <b>Guild Flag:</b> {flag} • {lock_status_text}\n"
        f"👥 <b>Members:</b> <code>{total_members} members</code>\n"
        f"💎 <b>Guild Level:</b> <code>Lv. {guild.level}</code>\n"
        f"🏛️ <b>Guild Treasury:</b> <code>💰 {guild.treasury:,} coins</code>\n"
        f"⚡ <b>Guild Perks:</b> <code>+5% Shiny Chance | +10% Coin Earnings</code>\n"
        f"◈ ────────────────── ◈"
    )
    builder = InlineKeyboardBuilder()
    btn_title = "🚩 View Flag Store" if is_locked else "🚩 Flag Store (💰 100k)"
    builder.row(InlineKeyboardButton(text=btn_title, callback_data="gflag_store_page_1"))
    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.message(Command("guildwithdraw", "gwithdraw", ignore_mention=True))
async def cmd_guild_withdraw_standalone(message: Message, db: AsyncSession):
    parts = message.text.split()
    user_id = message.from_user.id

    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("⚠️ Format: <code>/guildwithdraw &lt;amount&gt;</code> (or <code>/gwithdraw &lt;amount&gt;</code>)", parse_mode="HTML")
        return

    amount = int(parts[1])
    if amount <= 0:
        await message.answer("❌ Withdrawal amount must be greater than zero.", parse_mode="HTML")
        return

    member, guild = await get_user_guild_data(user_id, db)
    if not guild:
        await message.answer("❌ You are not in any Guild!", parse_mode="HTML")
        return

    if guild.owner_id != user_id and user_id not in getattr(config, "OWNER_IDS", []):
        await message.answer("❌ Only the Guild Leader can withdraw coins from the Treasury!", parse_mode="HTML")
        return

    if guild.treasury < amount:
        await message.answer(
            f"❌ Insufficient Treasury funds! Current Treasury: <b>💰 {guild.treasury:,} coins</b>.",
            parse_mode="HTML"
        )
        return

    u_stmt = select(User).where(User.id == user_id)
    u_res = await db.execute(u_stmt)
    user = u_res.scalar_one_or_none()
    if not user:
        user = User(id=user_id, username=message.from_user.username, nickname=message.from_user.first_name)
        db.add(user)
        await db.flush()

    guild.treasury -= amount
    user.coins += amount

    await log_transaction(user_id, amount, "GUILD_WITHDRAW", f"Withdrew from {guild.name} Treasury", db)
    await db.commit()

    leader_name = user.nickname or user.username or message.from_user.first_name or "Trainer"
    flag = format_guild_flag(getattr(guild, "flag", "🛡️"))
    await message.answer(
        f"🏛️ <b>Guild Treasury Withdrawal Successful!</b>\n"
        f"◈ ────────────────── ◈\n"
        f"👑 <b>Leader:</b> {html.escape(leader_name)}\n"
        f"🏰 <b>Guild:</b> {flag} {html.escape(guild.name)}\n"
        f"💰 <b>Withdrawn:</b> <code>+{amount:,} coins</code>\n"
        f"🏛️ <b>Remaining Treasury:</b> <code>💰 {guild.treasury:,} coins</code>\n"
        f"👤 <b>Your New Balance:</b> <code>💰 {user.coins:,} coins</code>\n"
        f"◈ ────────────────── ◈",
        parse_mode="HTML"
    )


@router.message(Command("guildlb", "clanlb", ignore_mention=True))
async def cmd_guild_lb(message: Message, db: AsyncSession):
    stmt = select(Guild).order_by(Guild.treasury.desc()).limit(10)
    res = await db.execute(stmt)
    guilds = res.scalars().all()

    if not guilds:
        await message.answer("🏰 No Guilds founded yet! Create one with `/guild create <name>`.")
        return

    rows = []
    for idx, g in enumerate(guilds, start=1):
        flag = format_guild_flag(getattr(g, "flag", "🛡️"))
        rows.append(f"✦ {idx}. {flag} <b>{html.escape(g.name)}</b> [{g.tag}] • 💰 {g.treasury:,} coins (Lv. {g.level})")

    ranks_body = "\n".join(rows)

    text = (
        f"⚡ <b>TOP GUILDS LEADERBOARD</b> ⚡\n"
        f"◈ ────────────────── ◈\n"
        f"{ranks_body}\n"
        f"◈ ────────────────── ◈\n"
        f"👉 <i>Found your own Guild with <code>/guild create &lt;name&gt;</code>!</i>"
    )
    await message.answer(text, parse_mode="HTML")


async def handle_guild_transfer_flow(message: Message, cmd_args: str, db: AsyncSession):
    """
    Handles transferring ownership of a Guild to a new user.
    Can be executed by Bot Owners for ANY guild, or by Guild Leaders for their own Guild.
    """
    caller_id = message.from_user.id
    is_bot_owner = bool(
        caller_id in getattr(config, "OWNER_IDS", [])
        or caller_id in getattr(config, "CO_OWNER_IDS", [])
        or (getattr(config, "ADMIN_IDS", None) and caller_id in config.ADMIN_IDS)
    )

    # 1. Parse target user and guild name
    target_tg_user = None
    target_str = None
    guild_str = None

    # Check reply first
    if message.reply_to_message and message.reply_to_message.from_user:
        target_tg_user = message.reply_to_message.from_user
        target_str = str(target_tg_user.id)
        guild_str = cmd_args.strip() if cmd_args.strip() else None
    else:
        # Check text_mention entity in message
        entities = message.entities or message.caption_entities or []
        for ent in entities:
            if ent.type == "text_mention" and ent.user:
                target_tg_user = ent.user
                target_str = str(target_tg_user.id)
                full_text = message.text or message.caption or ""
                mention_text = full_text[ent.offset:ent.offset + ent.length]
                cleaned_args = cmd_args.replace(mention_text, "").strip()
                guild_str = cleaned_args if cleaned_args else None
                break

        # If not text_mention and not reply, parse text tokens
        if not target_str and cmd_args:
            tokens = cmd_args.split()
            if len(tokens) == 1:
                # 1 token: could be target (@user or user_id) or guild name
                if tokens[0].isdigit() or tokens[0].startswith("@"):
                    target_str = tokens[0]
                    guild_str = None
                else:
                    guild_str = tokens[0]
                    target_str = None
            elif len(tokens) >= 2:
                # Check if last token is target (@user or user_id)
                if tokens[-1].isdigit() or tokens[-1].startswith("@"):
                    target_str = tokens[-1]
                    guild_str = " ".join(tokens[:-1]).strip()
                # Or if first token is target (@user or user_id)
                elif tokens[0].isdigit() or tokens[0].startswith("@"):
                    target_str = tokens[0]
                    guild_str = " ".join(tokens[1:]).strip()
                else:
                    # Check if last token matches a known username in DB
                    u_chk_stmt = select(User.id).where(func.lower(User.username) == tokens[-1].lower())
                    u_chk = (await db.execute(u_chk_stmt)).scalar_one_or_none()
                    if u_chk:
                        target_str = tokens[-1]
                        guild_str = " ".join(tokens[:-1]).strip()
                    else:
                        target_str = tokens[-1]
                        guild_str = " ".join(tokens[:-1]).strip()

    # 2. Resolve the Guild
    guild = None
    if guild_str:
        clean_g = guild_str.strip('\'"')
        # 1. Exact match by name
        g_stmt = select(Guild).where(func.lower(Guild.name) == clean_g.lower())
        guild = (await db.execute(g_stmt)).scalar_one_or_none()
        # 2. Exact match by tag
        if not guild:
            g_stmt = select(Guild).where(func.lower(Guild.tag) == clean_g.lower())
            guild = (await db.execute(g_stmt)).scalar_one_or_none()
        # 3. Match by numeric ID
        if not guild and clean_g.isdigit():
            g_stmt = select(Guild).where(Guild.id == int(clean_g))
            guild = (await db.execute(g_stmt)).scalar_one_or_none()
        # 4. Partial match by name
        if not guild:
            g_stmt = select(Guild).where(Guild.name.ilike(f"%{clean_g}%"))
            guild = (await db.execute(g_stmt)).scalar_one_or_none()

        if not guild:
            await message.answer(
                f"❌ Guild '<b>{html.escape(guild_str)}</b>' not found.\n"
                f"Please check the spelling of the Guild name or tag and try again.",
                parse_mode="HTML"
            )
            return
    else:
        # No guild name provided; check if caller is in a guild
        caller_member, caller_guild = await get_user_guild_data(caller_id, db)
        if caller_guild:
            guild = caller_guild
        else:
            await message.answer(
                "⚠️ <b>Guild Transfer Command Usage:</b>\n"
                "◈ ────────────────────────── ◈\n"
                "👉 <code>/transferguild &lt;Guild Name&gt; &lt;@username/ID&gt;</code>\n"
                "👉 Reply to a user's message: <code>/transferguild &lt;Guild Name&gt;</code>\n"
                "👉 Or: <code>/guild transfer &lt;Guild Name&gt; &lt;@username/ID&gt;</code>\n"
                "◈ ────────────────────────── ◈\n"
                "👑 <i>Bot Owners can transfer any Guild. Guild Leaders can transfer their own Guild.</i>",
                parse_mode="HTML"
            )
            return

    # 3. Check authorization for this guild
    if not is_bot_owner and guild.owner_id != caller_id:
        await message.answer(
            f"❌ Denied. Only Bot Owners or the Leader of <b>{html.escape(guild.name)}</b> can transfer its ownership.",
            parse_mode="HTML"
        )
        return

    # 4. Resolve Target User
    target_id = None
    target_name = None
    target_username = None
    is_bot = False

    if target_tg_user:
        target_id = target_tg_user.id
        target_name = target_tg_user.first_name
        target_username = target_tg_user.username
        is_bot = getattr(target_tg_user, "is_bot", False)
    elif target_str:
        if target_str.isdigit():
            target_id = int(target_str)
            u_stmt = select(User).where(User.id == target_id)
            u_res = await db.execute(u_stmt)
            target_u = u_res.scalar_one_or_none()
            if target_u:
                target_name = target_u.nickname or target_u.username or f"Trainer {target_id}"
                target_username = target_u.username
            else:
                try:
                    chat = await message.bot.get_chat(target_id)
                    target_name = chat.first_name
                    target_username = chat.username
                    is_bot = getattr(chat, "is_bot", False)
                except Exception:
                    target_name = f"Trainer {target_id}"
                    target_username = None
        else:
            clean_u = target_str.lstrip("@").strip()
            u_stmt = select(User).where(func.lower(User.username) == clean_u.lower())
            u_res = await db.execute(u_stmt)
            target_u = u_res.scalar_one_or_none()
            if target_u:
                target_id = target_u.id
                target_name = target_u.nickname or target_u.username or f"Trainer {target_u.id}"
                target_username = target_u.username
            else:
                await message.answer(
                    f"❌ User <b>@{html.escape(clean_u)}</b> was not found in PokéEmpire.\n"
                    f"They must register or start the bot before they can lead a Guild.",
                    parse_mode="HTML"
                )
                return

    if not target_id:
        await message.answer(
            "⚠️ <b>Please specify the target user to receive ownership:</b>\n\n"
            f"👉 <code>/transferguild {html.escape(guild.name)} &lt;@username/ID&gt;</code>\n"
            f"👉 Or reply to their message with: <code>/transferguild {html.escape(guild.name)}</code>",
            parse_mode="HTML"
        )
        return

    # 5. Target validations
    if is_bot:
        await message.answer("❌ You cannot transfer Guild ownership to a Telegram bot.", parse_mode="HTML")
        return

    if target_id == guild.owner_id:
        await message.answer(
            f"⚠️ <b>{html.escape(target_name or str(target_id))}</b> is already the Leader of <b>{html.escape(guild.name)}</b>!",
            parse_mode="HTML"
        )
        return

    # 6. Ensure target exists in User table
    u_stmt = select(User).where(User.id == target_id)
    u_res = await db.execute(u_stmt)
    target_user_record = u_res.scalar_one_or_none()
    if not target_user_record:
        target_user_record = User(
            id=target_id,
            username=target_username,
            nickname=target_name or f"Trainer {target_id}",
            coins=500
        )
        db.add(target_user_record)
        await db.flush()

    # 7. Check if target user is in any guild
    tgt_m_stmt = select(GuildMember, Guild).join(Guild, GuildMember.guild_id == Guild.id).where(GuildMember.user_id == target_id)
    tgt_m_res = await db.execute(tgt_m_stmt)
    tgt_membership = tgt_m_res.first()

    old_guild_note = ""
    if tgt_membership:
        existing_tgt_member, existing_tgt_guild = tgt_membership
        if existing_tgt_guild.id == guild.id:
            # Target is already in this guild: promote to leader
            existing_tgt_member.role = "leader"
        else:
            # Target is in another guild
            if existing_tgt_guild.owner_id == target_id:
                await message.answer(
                    f"❌ Cannot transfer: Target user is already the Leader of another Guild (<b>{html.escape(existing_tgt_guild.name)}</b> [{existing_tgt_guild.tag}]).\n"
                    f"They must transfer or disband that Guild before taking over a new one.",
                    parse_mode="HTML"
                )
                return
            old_guild_note = f"\nℹ️ <i>(Moved from previous Guild: {html.escape(existing_tgt_guild.name)})</i>"
            await db.delete(existing_tgt_member)
            await db.flush()
            new_target_member = GuildMember(guild_id=guild.id, user_id=target_id, role="leader")
            db.add(new_target_member)
    else:
        new_target_member = GuildMember(guild_id=guild.id, user_id=target_id, role="leader")
        db.add(new_target_member)

    # 8. Demote previous owner to member
    old_owner_id = guild.owner_id
    old_m_stmt = select(GuildMember).where(GuildMember.guild_id == guild.id, GuildMember.user_id == old_owner_id)
    old_m_res = await db.execute(old_m_stmt)
    old_member = old_m_res.scalar_one_or_none()
    if old_member:
        old_member.role = "member"
    else:
        db.add(GuildMember(guild_id=guild.id, user_id=old_owner_id, role="member"))

    # 9. Update Guild owner_id
    guild.owner_id = target_id
    await db.commit()

    # 10. Prepare success announcement
    old_u_stmt = select(User).where(User.id == old_owner_id)
    old_u_res = await db.execute(old_u_stmt)
    old_u = old_u_res.scalar_one_or_none()
    old_owner_name = html.escape(old_u.nickname or old_u.username or f"Trainer {old_owner_id}") if old_u else f"Trainer {old_owner_id}"

    new_leader_name = html.escape(target_user_record.nickname or target_user_record.username or f"Trainer {target_id}")
    caller_display = html.escape(message.from_user.first_name or message.from_user.username or "Admin")

    if is_bot_owner:
        auth_title = f"👑 <b>Bot Executive Admin</b> ({caller_display})"
    else:
        auth_title = f"👑 <b>Previous Leader</b> ({caller_display})"

    flag = format_guild_flag(getattr(guild, "flag", "🛡️"))

    success_text = (
        f"👑 <b>GUILD OWNERSHIP TRANSFERRED!</b> 👑\n"
        f"◈ ────────────────────────── ◈\n"
        f"🏰 <b>Guild:</b> {flag} <b>{html.escape(guild.name)}</b> [{html.escape(guild.tag)}]\n"
        f"👤 <b>Previous Leader:</b> {old_owner_name}\n"
        f"👑 <b>New Leader:</b> {new_leader_name} (<code>{target_id}</code>)\n"
        f"🛡️ <b>Authorized By:</b> {auth_title}\n"
        f"🏛️ <b>Guild Treasury:</b> <code>💰 {guild.treasury:,} coins</code>\n"
        f"◈ ────────────────────────── ◈{old_guild_note}\n"
        f"✨ <i>All Guild Leadership privileges, Treasury withdrawals, and Flag controls have been transferred to {new_leader_name}!</i>"
    )
    await message.answer(success_text, parse_mode="HTML")

    # Send notifications in DM
    try:
        await message.bot.send_message(
            chat_id=target_id,
            text=(
                f"👑 <b>Congratulations!</b>\n\n"
                f"You have been appointed as the new <b>Leader</b> of Guild {flag} <b>{html.escape(guild.name)}</b> [{html.escape(guild.tag)}]!\n\n"
                f"👉 Use <code>/guild</code> to manage your clan, check treasury balance, and view perks."
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass

    if old_owner_id != caller_id:
        try:
            await message.bot.send_message(
                chat_id=old_owner_id,
                text=(
                    f"ℹ️ <b>Guild Notice:</b>\n\n"
                    f"Leadership of Guild {flag} <b>{html.escape(guild.name)}</b> [{html.escape(guild.tag)}] "
                    f"has been transferred to <b>{new_leader_name}</b> by {auth_title}."
                ),
                parse_mode="HTML"
            )
        except Exception:
            pass


@router.message(Command("transferguild", "guildtransfer", "setguildowner", "transferclan", ignore_mention=True))
async def cmd_transfer_guild_standalone(message: Message, db: AsyncSession):
    """
    Standalone command for transferring Guild ownership:
    /transferguild <Guild Name> <@username/user_id>
    Or reply to a user: /transferguild <Guild Name>
    """
    raw_cmd = message.text or message.caption or ""
    parts = raw_cmd.split(maxsplit=1)
    cmd_args = parts[1].strip() if len(parts) > 1 else ""
    await handle_guild_transfer_flow(message, cmd_args, db)


@router.callback_query(F.data == "dm_guild_info")
async def cb_dm_guild_info(callback: CallbackQuery, db: AsyncSession):
    """Hub Menu callback handler for Guilds."""
    user_id = callback.from_user.id
    member, guild = await get_user_guild_data(user_id, db)

    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Back to Hub Menu", callback_data="dm_home"))

    if not guild:
        text = (
            f"🏰 <b>TRAINER GUILD CENTER</b> 🏰\n"
            f"◈ ────────────────── ◈\n"
            f"You are currently <b>not in any Guild</b>!\n\n"
            f"💡 <b>Guild Commands</b>:\n"
            f"👉 <code>/guild create &lt;name&gt;</code> — Found a new Guild (500k coins)\n"
            f"👉 <code>/guild join &lt;name&gt;</code> — Join an existing Guild\n"
            f"👉 <code>/flagstore</code> — Browse & buy animated flags (100k coins)\n"
            f"👉 <code>/guild deposit &lt;amount&gt;</code> — Donate coins to Guild Treasury\n"
            f"👉 <code>/guild withdraw &lt;amount&gt;</code> — Withdraw coins from Treasury (Leader only)\n"
            f"👉 <code>/guild transfer &lt;name&gt; &lt;user&gt;</code> — Transfer Guild Ownership\n"
            f"👉 <code>/guild delete</code> — Disband/Delete your Guild (Owner only)\n"
            f"👉 <code>/guild leave</code> — Leave your current Guild\n"
            f"👉 <code>/guildlb</code> — View top Guild Leaderboards\n"
            f"◈ ────────────────── ◈\n"
            f"✨ Guild members receive passive +5% Shiny Chance & +10% Coin Boosts!"
        )
    else:
        mem_stmt = select(func.count(GuildMember.id)).where(GuildMember.guild_id == guild.id)
        mem_res = await db.execute(mem_stmt)
        total_members = mem_res.scalar() or 0

        owner_stmt = select(User).where(User.id == guild.owner_id)
        owner_res = await db.execute(owner_stmt)
        owner = owner_res.scalar_one_or_none()
        owner_name = html.escape(owner.nickname or owner.username or f"Trainer {owner.id}") if owner else "Unknown"

        flag = format_guild_flag(getattr(guild, "flag", "🛡️"))
        is_locked = getattr(guild, "flag_locked", False)
        lock_status_text = "🔒 <i>Official Flag (Locked)</i>" if is_locked else "🔓 <i>Not Set (100k coins to buy)</i>"

        leader_tip = (
            f"👉 <i>Use <code>/guild withdraw &lt;amount&gt;</code> to withdraw from Treasury!</i>\n"
            f"👉 <i>Use <code>/flagstore</code> to buy your official Flag (💰 100k, one-time)!</i>"
            if (guild.owner_id == user_id and not is_locked)
            else (
                f"👉 <i>Use <code>/guild withdraw &lt;amount&gt;</code> to withdraw from Treasury!</i>"
                if guild.owner_id == user_id
                else f"👉 <i>Use <code>/guild deposit &lt;amount&gt;</code> to donate to the Treasury!</i>"
            )
        )

        text = (
            f"🏰 {flag} <b>GUILD: {html.escape(guild.name).upper()} [{html.escape(guild.tag)}]</b> {flag} 🏰\n"
            f"◈ ────────────────── ◈\n"
            f"👑 <b>Leader:</b> {owner_name}\n"
            f"🚩 <b>Guild Flag:</b> {flag} • {lock_status_text}\n"
            f"👥 <b>Members:</b> <code>{total_members} members</code>\n"
            f"💎 <b>Guild Level:</b> <code>Lv. {guild.level}</code>\n"
            f"🏛️ <b>Guild Treasury:</b> <code>💰 {guild.treasury:,} coins</code>\n"
            f"⚡ <b>Guild Perks:</b> <code>+5% Shiny Chance | +10% Coin Earnings</code>\n"
            f"◈ ────────────────── ◈\n"
            f"{leader_tip}"
        )
        btn_title = "🚩 View Flag Store" if is_locked else "🚩 Flag Store (💰 100k)"
        builder.row(InlineKeyboardButton(text=btn_title, callback_data="gflag_store_page_1"))

    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        try:
            await callback.message.edit_caption(caption=text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception:
            await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()
