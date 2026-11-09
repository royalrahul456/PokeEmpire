import html
import re
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
    auto_save_custom_flag_to_db,
    PRESET_GUILD_FLAGS
)
import config

router = Router()

GUILD_CREATION_FEE = 500000  # 500k coins
GUILD_FLAG_COST = 100000     # 100k coins (one-time choice)


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


async def build_flag_picker_keyboard(db: AsyncSession, is_leader: bool = True, is_locked: bool = False):
    """Builds an interactive keyboard of available flags."""
    builder = InlineKeyboardBuilder()
    if not is_locked:
        flags = await get_all_guild_flags(db)
        row = []
        for k, v in flags.items():
            icon = v.get("fallback", "🛡️")
            name = v.get("name", k)
            btn_text = f"{icon} {name[:12]}"
            row.append(InlineKeyboardButton(text=btn_text, callback_data=f"gflag_set:{k}"))
            if len(row) == 2:
                builder.row(*row)
                row = []
        if row:
            builder.row(*row)

    builder.row(InlineKeyboardButton(text="🔙 Back to Guild Profile", callback_data="gflag_back"))
    return builder.as_markup()


@router.message(Command("guild", "clan", ignore_mention=True))
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
                f"👉 <code>/guild create &lt;name&gt;</code> — Found a new Guild (500k coins)\n"
                f"👉 <code>/guild join &lt;name&gt;</code> — Join an existing Guild\n"
                f"👉 <code>/guild flag</code> — Choose Guild Flag (💰 100k, One-Time Choice)\n"
                f"👉 <code>/guild setflag &lt;emoji&gt;</code> — Set custom/animated flag\n"
                f"👉 <code>/guild deposit &lt;amount&gt;</code> — Donate coins to Treasury\n"
                f"👉 <code>/guild withdraw &lt;amount&gt;</code> — Withdraw coins from Treasury (Leader only)\n"
                f"👉 <code>/guild delete</code> — Disband/Delete your Guild (Owner only)\n"
                f"👉 <code>/guild leave</code> — Leave your current Guild\n"
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

        flag = format_guild_flag(getattr(guild, "flag", "🛡️"))
        is_locked = getattr(guild, "flag_locked", False)
        lock_status_text = "🔒 <i>Official Flag (Locked)</i>" if is_locked else "🔓 <i>Not Set (100k coins to choose)</i>"

        leader_tip = (
            f"👉 <i>Use <code>/guild withdraw &lt;amount&gt;</code> to withdraw from Treasury!</i>\n"
            f"👉 <i>Use <code>/guild flag</code> to choose your official Flag (💰 100k, one-time)!</i>"
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
        if guild.owner_id == user_id or user_id in getattr(config, "ADMIN_IDS", []):
            btn_title = "🚩 View Official Flag" if is_locked else "🚩 Choose Official Flag (💰 100k)"
            builder.row(InlineKeyboardButton(text=btn_title, callback_data="gflag_menu"))
            await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        else:
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
        if existing_g:
            await message.answer("❌ You are already in a Guild! Leave your current Guild first with <code>/guild leave</code>.", parse_mode="HTML")
            return

        u_stmt = select(User).where(User.id == user_id)
        u_res = await db.execute(u_stmt)
        user = u_res.scalar_one_or_none()

        if not user or user.coins < GUILD_CREATION_FEE:
            await message.answer(f"❌ Founding a Guild costs <b>💰 {GUILD_CREATION_FEE:,} coins</b> (500k)! Your balance: 💰 {user.coins:,} coins.", parse_mode="HTML")
            return

        # Check name availability
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
            f"👉 <i>Use <code>/guild flag</code> to choose an official animated flag (💰 100k, one-time choice)!</i>",
            parse_mode="HTML"
        )

    elif sub in ["flag", "flags"]:
        member, guild = await get_user_guild_data(user_id, db)
        if not guild:
            await message.answer("❌ You are not in any Guild!", parse_mode="HTML")
            return

        curr_flag = format_guild_flag(getattr(guild, "flag", "🛡️"))
        is_locked = getattr(guild, "flag_locked", False)

        if is_locked and user_id not in getattr(config, "ADMIN_IDS", []):
            text = (
                f"🚩 <b>OFFICIAL GUILD FLAG</b> 🚩\n"
                f"◈ ────────────────── ◈\n"
                f"🏰 Guild: <b>{html.escape(guild.name)}</b> [{guild.tag}]\n"
                f"🏳️ Official Flag: {curr_flag}\n"
                f"🔒 Status: <b>Permanently Locked</b>\n"
                f"◈ ────────────────── ◈\n"
                f"✨ <i>Your Guild Flag was permanently chosen and autosaved in the database! It cannot be changed.</i>"
            )
            markup = await build_flag_picker_keyboard(db, is_leader=False, is_locked=True)
            await message.answer(text, reply_markup=markup, parse_mode="HTML")
            return

        text = (
            f"🚩 <b>CHOOSE OFFICIAL GUILD FLAG</b> 🚩\n"
            f"◈ ────────────────── ◈\n"
            f"🏰 Guild: <b>{html.escape(guild.name)}</b> [{guild.tag}]\n"
            f"🏳️ Current Flag: {curr_flag}\n"
            f"💰 Cost: <b>100,000 coins (100k)</b>\n"
            f"⚠️ <b>Note:</b> You can choose your Guild Flag <b>ONLY ONCE</b>! Once chosen, it is permanently locked.\n"
            f"◈ ────────────────── ◈\n"
            f"✨ <i>Tap a flag below to choose it, or use your own custom animated emoji:</i>\n\n"
            f"💡 <b>To use custom animated emojis:</b>\n"
            f"• Send <code>/guild setflag &lt;emoji&gt;</code>\n"
            f"• Or reply to any animated emoji with <code>/guild setflag</code>!"
        )
        markup = await build_flag_picker_keyboard(db, is_leader=(guild.owner_id == user_id), is_locked=False)
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
                "⚠️ <b>How to set a Guild Flag:</b>\n\n"
                "💰 <b>Cost:</b> 100,000 coins (One-time choice)\n"
                "1️⃣ <b>Preset Flag:</b> <code>/guild setflag &lt;flag_name&gt;</code> (e.g. <code>strawhat</code>, <code>phoenix</code>, <code>samurai</code>, <code>dragon</code>)\n"
                "2️⃣ <b>Custom Animated Emoji:</b> Send <code>/guild setflag 🏴‍☠️</code> with your custom emoji, or reply to an animated emoji with <code>/guild setflag</code>!\n"
                "3️⃣ <b>Flag Picker:</b> Use <code>/guild flag</code> to browse interactive catalog.",
                parse_mode="HTML"
            )
            return

        u_stmt = select(User).where(User.id == user_id)
        u_res = await db.execute(u_stmt)
        user = u_res.scalar_one_or_none()

        if not user or user.coins < GUILD_FLAG_COST:
            user_coins = user.coins if user else 0
            await message.answer(
                f"❌ Choosing an official Guild Flag costs <b>💰 {GUILD_FLAG_COST:,} coins</b> (100k)!\n"
                f"Your current balance: <b>💰 {user_coins:,} coins</b>.",
                parse_mode="HTML"
            )
            return

        # Deduct coins
        user.coins -= GUILD_FLAG_COST
        await log_transaction(user_id, -GUILD_FLAG_COST, "GUILD_FLAG", f"Purchased official Flag for Guild {guild.name}", db)

        # Autosave custom animated emoji in DB flag catalog if emoji_id detected
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
        # Admin command to unlock a guild flag if requested
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
        # Owner/Admin only: register new animated flag into global catalog
        if user_id not in getattr(config, "ADMIN_IDS", []):
            await message.answer("❌ Owner/Admin only command.")
            return

        # Format: /guild addflag <key> <name>
        if len(parts) < 3:
            await message.answer(
                "⚠️ Format: Reply to a custom animated emoji with:\n"
                "<code>/guild addflag &lt;key&gt; &lt;Flag Title&gt;</code>\n"
                "Example: <code>/guild addflag pirate Straw Hat Flag</code>",
                parse_mode="HTML"
            )
            return

        sub_args = parts[2].split(maxsplit=1)
        flag_key = sub_args[0].lower().strip()
        flag_name = sub_args[1].strip() if len(sub_args) > 1 else flag_key.title()

        flag_val, emoji_id, _ = extract_custom_emoji_or_flag(message, "")
        if not emoji_id:
            await message.answer("❌ Please reply to a message containing a Telegram custom animated emoji.")
            return

        success = await register_guild_flag(flag_key, flag_name, emoji_id, "🛡️", db)
        if success:
            tag = f'<tg-emoji emoji-id="{emoji_id}">🛡️</tg-emoji>'
            await message.answer(
                f"✅ <b>New Guild Flag Registered!</b>\n\n"
                f"• Key: <code>{flag_key}</code>\n"
                f"• Name: <b>{html.escape(flag_name)}</b>\n"
                f"• Preview: {tag}\n\n"
                f"Autosaved in database! All Guild Leaders can now choose this flag from <code>/guild flag</code>!",
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
        
        # Check level up (every 50,000 coins in treasury increases level)
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
            await message.answer("❌ Guild Leaders cannot leave. Use <code>/guild delete</code> to disband the Guild.", parse_mode="HTML")
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
        # Delete all member records & the guild itself
        del_mems = delete(GuildMember).where(GuildMember.guild_id == guild.id)
        await db.execute(del_mems)
        await db.delete(guild)
        await db.commit()

        await message.answer(f"🗑️ Guild <b>{html.escape(guild_name)}</b> has been successfully disbanded and deleted!", parse_mode="HTML")


@router.message(Command("guildflag", "gflag", "setguildflag", ignore_mention=True))
async def cmd_guild_flag_shortcut(message: Message, db: AsyncSession):
    """Shortcut command to view or set guild flag directly."""
    parts = message.text.split(maxsplit=1)
    user_id = message.from_user.id

    member, guild = await get_user_guild_data(user_id, db)
    if not guild:
        await message.answer("❌ You are not in any Guild!", parse_mode="HTML")
        return

    is_locked = getattr(guild, "flag_locked", False)

    # If no argument and not replying to emoji: show picker
    if len(parts) < 2 and not message.reply_to_message:
        curr_flag = format_guild_flag(getattr(guild, "flag", "🛡️"))
        if is_locked and user_id not in getattr(config, "ADMIN_IDS", []):
            text = (
                f"🚩 <b>OFFICIAL GUILD FLAG</b> 🚩\n"
                f"◈ ────────────────── ◈\n"
                f"🏰 Guild: <b>{html.escape(guild.name)}</b> [{guild.tag}]\n"
                f"🏳️ Official Flag: {curr_flag}\n"
                f"🔒 Status: <b>Permanently Locked</b>\n"
                f"◈ ────────────────── ◈\n"
                f"✨ <i>Your Guild Flag was permanently chosen and autosaved!</i>"
            )
            markup = await build_flag_picker_keyboard(db, is_leader=False, is_locked=True)
            await message.answer(text, reply_markup=markup, parse_mode="HTML")
            return

        text = (
            f"🚩 <b>CHOOSE OFFICIAL GUILD FLAG</b> 🚩\n"
            f"◈ ────────────────── ◈\n"
            f"🏰 Guild: <b>{html.escape(guild.name)}</b> [{guild.tag}]\n"
            f"🏳️ Current Flag: {curr_flag}\n"
            f"💰 Cost: <b>100,000 coins (100k)</b>\n"
            f"⚠️ <b>Note:</b> You can choose your Guild Flag <b>ONLY ONCE</b>!\n"
            f"◈ ────────────────── ◈\n"
            f"✨ <i>Choose a flag below, or reply to any custom animated emoji with <code>/setguildflag</code>!</i>"
        )
        markup = await build_flag_picker_keyboard(db, is_leader=(guild.owner_id == user_id), is_locked=False)
        await message.answer(text, reply_markup=markup, parse_mode="HTML")
        return

    if guild.owner_id != user_id and user_id not in getattr(config, "ADMIN_IDS", []):
        await message.answer("❌ Only the Guild Leader can set the Guild Flag!", parse_mode="HTML")
        return

    if is_locked and user_id not in getattr(config, "ADMIN_IDS", []):
        curr_flag = format_guild_flag(getattr(guild, "flag", "🛡️"))
        await message.answer(
            f"❌ <b>Guild Flag Already Set!</b>\n\n"
            f"Your Guild is already flying {curr_flag}!\n"
            f"Guild Flags can only be chosen <b>one time</b> for 100k coins and cannot be changed.",
            parse_mode="HTML"
        )
        return

    param = parts[1] if len(parts) >= 2 else ""
    flag_val, emoji_id, desc = extract_custom_emoji_or_flag(message, param)

    if not flag_val:
        await message.answer("⚠️ Could not detect a valid flag or custom emoji.", parse_mode="HTML")
        return

    u_stmt = select(User).where(User.id == user_id)
    u_res = await db.execute(u_stmt)
    user = u_res.scalar_one_or_none()

    if not user or user.coins < GUILD_FLAG_COST:
        user_coins = user.coins if user else 0
        await message.answer(
            f"❌ Choosing a Guild Flag costs <b>💰 {GUILD_FLAG_COST:,} coins</b> (100k)!\n"
            f"Your current balance: <b>💰 {user_coins:,} coins</b>.",
            parse_mode="HTML"
        )
        return

    # Deduct 100k coins
    user.coins -= GUILD_FLAG_COST
    await log_transaction(user_id, -GUILD_FLAG_COST, "GUILD_FLAG", f"Purchased official Flag for {guild.name}", db)

    # Autosave custom animated emoji in DB if present
    if emoji_id:
        await auto_save_custom_flag_to_db(emoji_id, "🛡️", db, name=f"{guild.name} Banner")

    guild.flag = flag_val
    guild.flag_locked = True
    await db.commit()

    display_flag = format_guild_flag(flag_val)
    await message.answer(
        f"🎉 <b>Guild Flag Chosen & Locked!</b>\n\n"
        f"🏰 <b>{html.escape(guild.name)}</b> [{guild.tag}] is now flying the official flag: {display_flag}\n"
        f"💰 Fee: <code>-{GUILD_FLAG_COST:,} coins</code> (Autosaved & Permanently Locked)",
        parse_mode="HTML"
    )


@router.callback_query(F.data == "gflag_menu")
async def cb_guild_flag_menu(callback: CallbackQuery, db: AsyncSession):
    """Opens flag picker from Guild profile button."""
    user_id = callback.from_user.id
    member, guild = await get_user_guild_data(user_id, db)
    if not guild:
        await callback.answer("You are not in a Guild!", show_alert=True)
        return

    curr_flag = format_guild_flag(getattr(guild, "flag", "🛡️"))
    is_locked = getattr(guild, "flag_locked", False)

    if is_locked and user_id not in getattr(config, "ADMIN_IDS", []):
        text = (
            f"🚩 <b>OFFICIAL GUILD FLAG</b> 🚩\n"
            f"◈ ────────────────── ◈\n"
            f"🏰 Guild: <b>{html.escape(guild.name)}</b> [{guild.tag}]\n"
            f"🏳️ Official Flag: {curr_flag}\n"
            f"🔒 Status: <b>Permanently Locked</b>\n"
            f"◈ ────────────────── ◈\n"
            f"✨ <i>Your Guild Flag was permanently chosen and autosaved! It cannot be changed.</i>"
        )
        markup = await build_flag_picker_keyboard(db, is_leader=False, is_locked=True)
    else:
        text = (
            f"🚩 <b>CHOOSE OFFICIAL GUILD FLAG</b> 🚩\n"
            f"◈ ────────────────── ◈\n"
            f"🏰 Guild: <b>{html.escape(guild.name)}</b> [{guild.tag}]\n"
            f"🏳️ Current Flag: {curr_flag}\n"
            f"💰 Cost: <b>100,000 coins (100k)</b>\n"
            f"⚠️ <b>Note:</b> You can choose your Guild Flag <b>ONLY ONCE</b>!\n"
            f"◈ ────────────────── ◈\n"
            f"Tap any flag below to choose it, or use your own custom animated emoji:\n\n"
            f"💡 <i>Send <code>/guild setflag &lt;emoji&gt;</code> to use custom animated emoji!</i>"
        )
        markup = await build_flag_picker_keyboard(db, is_leader=(guild.owner_id == user_id), is_locked=False)

    try:
        await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=markup, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("gflag_set:"))
async def cb_guild_flag_apply(callback: CallbackQuery, db: AsyncSession):
    """Applies selected preset flag to the guild with 100k cost and lock."""
    user_id = callback.from_user.id
    member, guild = await get_user_guild_data(user_id, db)
    if not guild:
        await callback.answer("You are not in a Guild!", show_alert=True)
        return

    if guild.owner_id != user_id and user_id not in getattr(config, "ADMIN_IDS", []):
        await callback.answer("Only the Guild Leader can choose the Flag!", show_alert=True)
        return

    if getattr(guild, "flag_locked", False) and user_id not in getattr(config, "ADMIN_IDS", []):
        await callback.answer("❌ Guild Flag is already chosen and permanently locked!", show_alert=True)
        return

    u_stmt = select(User).where(User.id == user_id)
    u_res = await db.execute(u_stmt)
    user = u_res.scalar_one_or_none()

    if not user or user.coins < GUILD_FLAG_COST:
        user_coins = user.coins if user else 0
        await callback.answer(f"❌ Choosing a Flag costs 100,000 coins! You have: {user_coins:,}.", show_alert=True)
        return

    flag_key = callback.data.split(":", 1)[1]
    all_flags = await get_all_guild_flags(db)

    if flag_key not in all_flags:
        await callback.answer("Flag not found!", show_alert=True)
        return

    preset = all_flags[flag_key]
    flag_val = preset.get("tag", preset.get("fallback", "🛡️"))

    # Deduct 100k coins
    user.coins -= GUILD_FLAG_COST
    await log_transaction(user_id, -GUILD_FLAG_COST, "GUILD_FLAG", f"Purchased Flag {preset.get('name')} for {guild.name}", db)

    guild.flag = flag_val
    guild.flag_locked = True
    await db.commit()

    display_flag = format_guild_flag(flag_val)
    await callback.answer(f"Official Flag set to {preset.get('name')} (Paid 100k coins)!", show_alert=True)

    # Return to updated guild screen
    mem_stmt = select(func.count(GuildMember.id)).where(GuildMember.guild_id == guild.id)
    mem_res = await db.execute(mem_stmt)
    total_members = mem_res.scalar() or 0

    owner_stmt = select(User).where(User.id == guild.owner_id)
    owner_res = await db.execute(owner_stmt)
    owner = owner_res.scalar_one_or_none()
    owner_name = html.escape(owner.nickname or owner.username or f"Trainer {owner.id}") if owner else "Unknown"

    text = (
        f"🏰 {display_flag} <b>GUILD: {html.escape(guild.name).upper()} [{html.escape(guild.tag)}]</b> {display_flag} 🏰\n"
        f"◈ ────────────────── ◈\n"
        f"👑 <b>Leader:</b> {owner_name}\n"
        f"🚩 <b>Guild Flag:</b> {display_flag} • 🔒 <i>Official Flag (Locked)</i>\n"
        f"👥 <b>Members:</b> <code>{total_members} members</code>\n"
        f"💎 <b>Guild Level:</b> <code>Lv. {guild.level}</code>\n"
        f"🏛️ <b>Guild Treasury:</b> <code>💰 {guild.treasury:,} coins</code>\n"
        f"⚡ <b>Guild Perks:</b> <code>+5% Shiny Chance | +10% Coin Earnings</code>\n"
        f"◈ ────────────────── ◈\n"
        f"🎉 <i>Official Guild Flag chosen, autosaved & locked!</i>"
    )
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🚩 View Official Flag", callback_data="gflag_menu"))
    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


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
    lock_status_text = "🔒 <i>Official Flag (Locked)</i>" if is_locked else "🔓 <i>Not Set (100k coins to choose)</i>"

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
    if guild.owner_id == user_id or user_id in getattr(config, "ADMIN_IDS", []):
        btn_title = "🚩 View Official Flag" if is_locked else "🚩 Choose Official Flag (💰 100k)"
        builder.row(InlineKeyboardButton(text=btn_title, callback_data="gflag_menu"))
    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.message(Command("guildwithdraw", "gwithdraw", ignore_mention=True))
async def cmd_guild_withdraw_standalone(message: Message, db: AsyncSession):
    """Direct shortcut command /guildwithdraw <amount> or /gwithdraw <amount>."""
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
            f"👉 <code>/guild flag</code> — Choose Guild Flag (💰 100k, One-Time Choice)\n"
            f"👉 <code>/guild setflag &lt;emoji&gt;</code> — Set custom/animated flag\n"
            f"👉 <code>/guild deposit &lt;amount&gt;</code> — Donate coins to Guild Treasury\n"
            f"👉 <code>/guild withdraw &lt;amount&gt;</code> — Withdraw coins from Treasury (Leader only)\n"
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
        lock_status_text = "🔒 <i>Official Flag (Locked)</i>" if is_locked else "🔓 <i>Not Set (100k coins to choose)</i>"

        leader_tip = (
            f"👉 <i>Use <code>/guild withdraw &lt;amount&gt;</code> to withdraw from Treasury!</i>\n"
            f"👉 <i>Use <code>/guild flag</code> to choose your official Flag (💰 100k, one-time)!</i>"
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
        if guild.owner_id == user_id or user_id in getattr(config, "ADMIN_IDS", []):
            btn_title = "🚩 View Official Flag" if is_locked else "🚩 Choose Official Flag (💰 100k)"
            builder.row(InlineKeyboardButton(text=btn_title, callback_data="gflag_menu"))

    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        try:
            await callback.message.edit_caption(caption=text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception:
            await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()
