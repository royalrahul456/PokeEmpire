import html
import random
from datetime import datetime, timedelta
from typing import Optional, Tuple

from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

import config
from database.models import User, Pokemon, UserPokemon, PokemonFormMedia
from utils.formatters import get_rarity_emoji
from utils.settings import send_safe_media
from utils.vip import (
    is_user_vip,
    get_vip_details,
    set_user_vip,
    remove_user_vip,
    add_poke_gems,
)
from utils.claim import check_vip_claim_cooldown, update_vip_claim_cooldown

router = Router()


def parse_stored_media_value(media_value: Optional[str]) -> Tuple[str, Optional[str]]:
    if not media_value:
        return "photo", None
    if ":" in media_value:
        media_type, clean_value = media_value.split(":", 1)
        if media_type in {"photo", "video", "animation"}:
            return media_type, clean_value
    if media_value.startswith("http"):
        return "photo", media_value
    return "video", media_value


def get_form_label(form_index: int) -> str:
    labels = {
        1: "🎬 AMV / Special Art",
        2: "⚡ Dynamax (Dmax)",
        3: "💥 Gigantamax (Gmax)",
        4: "🌀 Z-Move",
        5: "🔮 Terastal",
        6: "✨ Shiny Alternate",
        7: "🌟 Special Form .7",
        8: "🌟 Special Form .8",
    }
    return labels.get(form_index, f"🌟 Custom Alternate Form .{form_index}")


def build_vip_plan_card(user_db: Optional[User], user_id: int, user_name: str) -> Tuple[str, InlineKeyboardMarkup]:
    """Generates the appropriate card: VIP Status dashboard if active, or Pricing & Perks if not."""
    details = get_vip_details(user_db)
    is_vip = details["is_vip"]

    builder = InlineKeyboardBuilder()

    if is_vip:
        tier_title = details["tier"]
        poke_gems = details["poke_gems"]
        streak = details["streak"]
        coins = user_db.coins if user_db else 0

        if details["is_lifetime"]:
            validity_str = "♾️ <b>Permanent Lifetime Access</b>"
            expiry_date_str = "Never expires"
        else:
            days = details["days_remaining"]
            hours = details["hours_remaining"]
            validity_str = f"⏳ <b>{days} Days, {hours} Hours</b> remaining"
            exp = details["expires_at"]
            expiry_date_str = exp.strftime("%Y-%m-%d %H:%M UTC") if exp else "Active"

        text = (
            "👑 <b>POKÉEMPIRE VIP MEMBERSHIP — ACTIVE</b> 👑\n"
            "◈ ───────────────────────────────── ◈\n"
            f"<blockquote>✨ <b>Welcome, VIP Trainer {html.escape(user_name)}!</b>\n"
            f"Your VIP privileges are active and ready to use.</blockquote>\n\n"
            f"📋 <b>YOUR VIP STATUS & METRICS:</b>\n"
            f"• 👑 <b>Status:</b> 🟢 <b>ACTIVE</b>\n"
            f"• 🎖️ <b>Plan Tier:</b> <b>{tier_title}</b>\n"
            f"• ⏱️ <b>Validity:</b> {validity_str}\n"
            f"• 📅 <b>Valid Until:</b> <code>{expiry_date_str}</code>\n"
            f"• 💎 <b>PokeGems Balance:</b> <b>{poke_gems:,} ⭐ PokeGems</b>\n"
            f"• 💰 <b>Coin Wallet:</b> <b>{coins:,} Coins</b>\n"
            f"• 🔥 <b>VIP Daily Streak:</b> <b>{streak} Days</b>\n\n"
            f"<blockquote>⚡ <b>VIP EXCLUSIVE COMMANDS:</b>\n"
            f"• <code>/vipdaily</code> &mdash; Daily bundle of PokeGems, Coins & Pokémon\n"
            f"• <code>/vipclaim</code> &mdash; Daily rare alternate form & custom art Pokémon</blockquote>\n"
            "◈ ───────────────────────────────── ◈"
        )

        builder.row(
            InlineKeyboardButton(text="🎁 Claim VIP Daily", callback_data="vip_act_daily", style="success"),
            InlineKeyboardButton(text="🎨 VIP Claim", callback_data="vip_act_claim", style="success")
        )
        builder.row(
            InlineKeyboardButton(text="🔄 Refresh Status", callback_data="vip_refresh_status", style="primary"),
            InlineKeyboardButton(text="💎 View Pricing / Extend", callback_data="vip_show_pricing", style="danger")
        )
        return text, builder.as_markup()

    else:
        text = (
            "💎 <b>POKÉEMPIRE VIP MEMBERSHIP PLANS</b> 💎\n"
            "◈ ───────────────────────────────── ◈\n"
            "<blockquote>🌟 <i>Elevate your Pokémon empire with elite daily rewards, rare alternate-art forms, and the exclusive PokeGems currency!</i></blockquote>\n\n"
            "👑 <b>VIP PRIVILEGES & PERKS:</b>\n"
            "• 🎨 <b>/vipclaim</b> &mdash; Daily exclusive Pokémon guaranteed with rare <b>non-.0 alternate form & custom arts</b> (AMV, Dmax, Gmax, Z-Move, Terastal)!\n"
            "• 🎁 <b>/vipdaily</b> &mdash; Massive daily bundle: <b>50-80 ⭐ PokeGems</b>, <b>2,500 Coins</b>, free Pokémon & streak milestones!\n"
            "• 💎 <b>PokeGems Currency</b> &mdash; Unlock exclusive rare items, cards, and special booster vaults!\n"
            "• 👑 <b>VIP Crown Badge</b> &mdash; Displays on your profile card, leaderboards, and trainer tag.\n"
            "• 🎉 <b>7-Day Streak Milestones</b> &mdash; +50 bonus PokeGems every 7 days!\n"
            "• ⚡ <b>Priority Catch & Support</b> &mdash; Fast track perks & direct developer assistance.\n\n"
            "💎 <b>VIP MEMBERSHIP PLANS:</b>\n"
            "• 🥉 <b>Weekly (7 Days):</b> <code>₹39</code>\n"
            "• 🥈 <b>Monthly (30 Days):</b> <code>₹79</code>\n"
            "• 🥇 <b>2 Months (60 Days):</b> <code>₹129</code>\n"
            "• 👑 <b>3 Months (90 Days):</b> <code>₹199</code>\n"
            "◈ ───────────────────────────────── ◈\n"
            "<i>Contact the Bot Owner to purchase your VIP pass and activate instantly!</i>"
        )

        owner_id = config.OWNER_IDS[0] if config.OWNER_IDS else 6593485710
        builder.row(
            InlineKeyboardButton(text="💳 Purchase VIP / Contact Owner", url=f"tg://user?id={owner_id}", style="success")
        )
        builder.row(
            InlineKeyboardButton(text="🎁 Preview /vipdaily", callback_data="vip_preview_daily", style="primary"),
            InlineKeyboardButton(text="🎨 Preview /vipclaim", callback_data="vip_preview_claim", style="primary")
        )
        builder.row(
            InlineKeyboardButton(text="🔄 Check Activation Status", callback_data="vip_refresh_status", style="primary")
        )
        return text, builder.as_markup()


# ── COMMAND: /vipplan, /vip ──────────────────────────────────────────────────
@router.message(Command("vipplan", "vipplans", "vip", "vipstatus", ignore_mention=True))
async def cmd_vip_plan(message: Message, db: AsyncSession):
    user_id = message.from_user.id if message.from_user else 0
    user_name = message.from_user.first_name if message.from_user else "Trainer"

    u_stmt = select(User).where(User.id == user_id)
    u_res = await db.execute(u_stmt)
    user_db = u_res.scalar_one_or_none()

    text, markup = build_vip_plan_card(user_db, user_id, user_name)
    await message.answer(text, reply_markup=markup, parse_mode="HTML")


# ── COMMAND: /vipclaim ───────────────────────────────────────────────────────
@router.message(Command("vipclaim", ignore_mention=True))
async def cmd_vip_claim(message: Message, db: AsyncSession):
    user_id = message.from_user.id if message.from_user else 0
    user_name = message.from_user.first_name if message.from_user else "Trainer"

    u_stmt = select(User).where(User.id == user_id)
    u_res = await db.execute(u_stmt)
    user_db = u_res.scalar_one_or_none()

    if not user_db:
        user_db = User(
            id=user_id,
            username=message.from_user.username if message.from_user else None,
            nickname=user_name,
            coins=500
        )
        db.add(user_db)
        await db.flush()

    if not is_user_vip(user_db):
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="💎 View VIP Plans & Pricing", callback_data="vip_show_pricing"))
        await message.answer(
            "🔒 <b>VIP EXCLUSIVE FEATURE</b> 🔒\n"
            "◈ ────────────────────────── ◈\n"
            "<blockquote>⚠️ <b>/vipclaim is exclusively reserved for VIP Members.</b>\n\n"
            "Unlike the standard <code>/claim</code> which only awards base .0 art, "
            "<b>/vipclaim guarantees special non-.0 alternate form & custom art Pokémon</b> (AMV, Dmax, Gmax, Z-Move, Terastal)!\n\n"
            "💎 <b>Plans start at just ₹39 for 7 days!</b>\n"
            "Use <code>/vipplan</code> to activate your VIP Pass.</blockquote>\n"
            "◈ ────────────────────────── ◈",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        return

    # Check 24h VIP claim cooldown
    remaining_cooldown = check_vip_claim_cooldown(user_id)
    if remaining_cooldown > 0:
        hours = remaining_cooldown // 3600
        minutes = (remaining_cooldown % 3600) // 60
        seconds = remaining_cooldown % 60
        time_str = f"{hours}h {minutes}m {seconds}s"
        await message.answer(
            "⏳ <b>VIP CLAIM COOLDOWN</b>\n"
            "◈ ────────────────────────── ◈\n"
            f"<blockquote>Too early, VIP Trainer! You can claim your next custom art Pokémon in <b>{time_str}</b>.</blockquote>\n"
            "◈ ────────────────────────── ◈",
            parse_mode="HTML"
        )
        return

    # Query only alternate form media strictly between .1 and .8 (excluding .0 base form and > .8)
    fm_stmt = select(PokemonFormMedia).where(
        PokemonFormMedia.form_index >= 1,
        PokemonFormMedia.form_index <= 8
    )
    fm_res = await db.execute(fm_stmt)
    available_forms = fm_res.scalars().all()

    selected_pokemon = None
    form_index = 1
    media_value = None

    if available_forms:
        chosen_fm = random.choice(available_forms)
        form_index = chosen_fm.form_index
        media_value = chosen_fm.media_value
        p_res = await db.execute(select(Pokemon).where(Pokemon.id == chosen_fm.pokemon_id))
        selected_pokemon = p_res.scalar_one_or_none()

    if not selected_pokemon:
        p_all_res = await db.execute(select(Pokemon))
        all_pokemon = p_all_res.scalars().all()
        if not all_pokemon:
            await message.answer("❌ <b>Error:</b> No Pokémon found in database to claim.", parse_mode="HTML")
            return
        selected_pokemon = random.choice(all_pokemon)
        form_index = random.choice([1, 2, 3, 4, 5, 6, 7, 8])

    # VIP boosted shiny rate: 1 in 40 (normal is 1 in 100)
    is_shiny = random.randint(1, 40) == 1
    iv_hp = random.randint(10, 31)  # VIP IV floor of 10
    iv_atk = random.randint(10, 31)
    iv_def = random.randint(10, 31)
    iv_spd = random.randint(10, 31)
    iv_total_pct = round(((iv_hp + iv_atk + iv_def + iv_spd) / 124) * 100, 1)

    # Determine if AMV / video
    is_amv = (form_index == 1) or (media_value is not None and "video" in str(media_value).lower())

    capture = UserPokemon(
        user_id=user_id,
        pokemon_id=selected_pokemon.id,
        is_shiny=is_shiny,
        is_amv=is_amv,
        form_index=form_index,
        level=1,
        xp=0,
        iv_hp=iv_hp,
        iv_atk=iv_atk,
        iv_def=iv_def,
        iv_spd=iv_spd
    )
    db.add(capture)
    update_vip_claim_cooldown(user_id)
    await db.commit()

    form_label = get_form_label(form_index)
    shiny_prefix = "✨ Shiny " if is_shiny else ""
    r_emoji = get_rarity_emoji(selected_pokemon.rarity)

    card_text = (
        "👑 <b>VIP POKÉMON CLAIMED</b> 👑\n"
        "◈ ────────────────────────── ◈\n"
        f"<blockquote>✨ <b>EXCLUSIVE VIP SPECIAL ARTWORK REWARD</b> ✨\n\n"
        f"👤 <b>Trainer:</b> {html.escape(user_name)} [👑 VIP]\n"
        f"👾 <b>Pokémon:</b> {shiny_prefix}<b>{selected_pokemon.name.title()}</b>\n"
        f"🎨 <b>Artwork Form:</b> <b>{form_label}</b> (Form .{form_index})\n"
        f"{r_emoji} <b>Rarity:</b> <b>{selected_pokemon.rarity}</b>\n\n"
        f"💎 <i>Exclusively awarded with custom non-.0 alternate art!</i></blockquote>\n"
        "◈ ────────────────────────── ◈\n"
        "⏳ <i>Come back in 24h for your next VIP Claim!</i>"
    )

    media_type, parsed_media = parse_stored_media_value(media_value)
    if not parsed_media:
        parsed_media = selected_pokemon.image_url
        media_type = "photo"

    claim_kb = InlineKeyboardBuilder()
    claim_kb.row(
        InlineKeyboardButton(text="💎 VIP Menu", callback_data="vip_refresh_status", style="danger"),
        InlineKeyboardButton(text="🎁 Claim VIP Daily", callback_data="vip_act_daily", style="success")
    )

    await send_safe_media(
        bot=message.bot,
        chat_id=message.chat.id,
        media_type=media_type,
        media_value=parsed_media,
        caption=card_text,
        reply_markup=claim_kb.as_markup(),
        parse_mode="HTML",
        message_to_reply=message
    )


# ── COMMAND: /vipdaily ───────────────────────────────────────────────────────
@router.message(Command("vipdaily", ignore_mention=True))
async def cmd_vip_daily(message: Message, db: AsyncSession):
    user_id = message.from_user.id if message.from_user else 0
    user_name = message.from_user.first_name if message.from_user else "Trainer"

    u_stmt = select(User).where(User.id == user_id)
    u_res = await db.execute(u_stmt)
    user_db = u_res.scalar_one_or_none()

    if not user_db:
        user_db = User(
            id=user_id,
            username=message.from_user.username if message.from_user else None,
            nickname=user_name,
            coins=500
        )
        db.add(user_db)
        await db.flush()

    if not is_user_vip(user_db):
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="💎 View VIP Plans & Pricing", callback_data="vip_show_pricing"))
        await message.answer(
            "🔒 <b>VIP EXCLUSIVE FEATURE</b> 🔒\n"
            "◈ ────────────────────────── ◈\n"
            "<blockquote>⚠️ <b>/vipdaily is exclusively reserved for VIP Members.</b>\n\n"
            "Upgrade to VIP to claim:\n"
            "• 💎 <b>50-80 ⭐ PokeGems</b> every day!\n"
            "• 💰 <b>+2,500 Coins</b> every day!\n"
            "• 🎁 <b>Free Daily Pokémon</b>!\n"
            "• 🎉 <b>+50 bonus PokeGems</b> on 7-day streaks!\n\n"
            "Plans start at just ₹39 for 7 days!</blockquote>\n"
            "◈ ────────────────────────── ◈",
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
        return

    now = datetime.utcnow()
    last_daily = getattr(user_db, "last_vip_daily", None)
    if last_daily:
        if last_daily.tzinfo is not None:
            last_daily = last_daily.replace(tzinfo=None)
        cooldown = timedelta(hours=24)
        elapsed = now - last_daily
        if elapsed < cooldown:
            remaining = cooldown - elapsed
            hours, remainder = divmod(remaining.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            time_str = f"{hours}h {minutes}m {seconds}s"
            await message.answer(
                "⏳ <b>VIP DAILY COOLDOWN</b>\n"
                "◈ ────────────────────────── ◈\n"
                f"<blockquote>Too early, VIP Trainer! You can claim your next VIP daily reward in <b>{time_str}</b>.</blockquote>\n"
                "◈ ────────────────────────── ◈",
                parse_mode="HTML"
            )
            return

    # Calculate rewards:
    # 1. PokeGems (random 50-80)
    gems_added = random.randint(50, 80)
    # 2. Coins (2,500)
    coins_added = 2500

    # 3. Streak tracking
    current_streak = getattr(user_db, "vip_daily_streak", 0) or 0
    if last_daily and (now - last_daily) <= timedelta(hours=48):
        new_streak = current_streak + 1
    else:
        new_streak = 1
    user_db.vip_daily_streak = new_streak

    # 4. Streak Milestones
    bonus_gems = 0
    streak_msg = ""
    if new_streak % 7 == 0:
        bonus_gems = 50
        streak_msg = f"\n🎉 <b>7-Day Streak Bonus! +50 extra ⭐ gems</b>\n"
    elif new_streak > 1:
        days_to_milestone = 7 - (new_streak % 7)
        streak_msg = f"\n🔥 <i>VIP Streak: <b>{new_streak} Days</b> ({days_to_milestone} days until +50 gems bonus!)</i>\n"

    # 5. Today's Pokemon reward (strictly between .1 and .8 only!)
    fm_stmt = select(PokemonFormMedia).where(
        PokemonFormMedia.form_index >= 1,
        PokemonFormMedia.form_index <= 8
    )
    fm_res = await db.execute(fm_stmt)
    available_forms = fm_res.scalars().all()

    selected_pokemon = None
    form_index = 1
    media_value = None

    if available_forms:
        chosen_fm = random.choice(available_forms)
        form_index = chosen_fm.form_index
        media_value = chosen_fm.media_value
        p_res = await db.execute(select(Pokemon).where(Pokemon.id == chosen_fm.pokemon_id))
        selected_pokemon = p_res.scalar_one_or_none()

    if not selected_pokemon:
        p_all_res = await db.execute(select(Pokemon))
        all_pokemon = p_all_res.scalars().all()
        if all_pokemon:
            selected_pokemon = random.choice(all_pokemon)
            form_index = random.choice([1, 2, 3, 4, 5, 6, 7, 8])

    shiny_prefix = ""
    poke_name = "None"
    rarity_text = "Common"
    r_emoji = "⚪️"
    media_type = "photo"
    parsed_media = None

    if selected_pokemon:
        is_shiny = random.randint(1, 40) == 1
        shiny_prefix = "✨ Shiny " if is_shiny else ""
        form_label = get_form_label(form_index)
        poke_name = f"{selected_pokemon.name.title()} ({form_label})"
        rarity_text = selected_pokemon.rarity
        r_emoji = get_rarity_emoji(rarity_text)

        is_amv = (form_index == 1) or (media_value is not None and "video" in str(media_value).lower())

        capture = UserPokemon(
            user_id=user_id,
            pokemon_id=selected_pokemon.id,
            is_shiny=is_shiny,
            is_amv=is_amv,
            form_index=form_index,
            level=1,
            xp=0,
            iv_hp=random.randint(10, 31),
            iv_atk=random.randint(10, 31),
            iv_def=random.randint(10, 31),
            iv_spd=random.randint(10, 31)
        )
        db.add(capture)

        media_type, parsed_media = parse_stored_media_value(media_value)
        if not parsed_media:
            parsed_media = selected_pokemon.image_url
            media_type = "photo"

    # Update user wallet
    total_gems_added = gems_added + bonus_gems
    user_db.poke_gems = (getattr(user_db, "poke_gems", 0) or 0) + total_gems_added
    user_db.coins = (getattr(user_db, "coins", 0) or 0) + coins_added
    user_db.last_vip_daily = now
    await db.commit()

    card_text = (
        f"👑 <b>vipdaily Daily — {html.escape(user_name)}</b>\n"
        "◈ ────────────────────────── ◈\n"
        f"<blockquote>✨ <b>+{gems_added} ⭐ poke gems added!</b>\n"
        f"💰 <b>+{coins_added:,} Coins added!</b>\n"
        f"<i>(gems — randomly chosen!)</i>\n\n"
        f"🎁 <b>Today's pokemon:</b>\n"
        f"📛 <b>{shiny_prefix}{poke_name}</b>\n"
        f"{r_emoji} <b>{rarity_text}</b>"
        f"{streak_msg}</blockquote>\n"
        "◈ ────────────────────────── ◈\n"
        "⏳ <b>Come back in 24h for the next reward!</b>"
    )

    daily_kb = InlineKeyboardBuilder()
    daily_kb.row(
        InlineKeyboardButton(text="💎 VIP Menu", callback_data="vip_refresh_status", style="danger"),
        InlineKeyboardButton(text="🎨 VIP Claim", callback_data="vip_act_claim", style="success")
    )

    if parsed_media:
        await send_safe_media(
            bot=message.bot,
            chat_id=message.chat.id,
            media_type=media_type,
            media_value=parsed_media,
            caption=card_text,
            reply_markup=daily_kb.as_markup(),
            parse_mode="HTML",
            message_to_reply=message
        )
    else:
        await message.answer(card_text, reply_markup=daily_kb.as_markup(), parse_mode="HTML")


# ── ADMIN VIP MANAGEMENT COMMANDS ───────────────────────────────────────────
def is_bot_staff(user_id: Optional[int]) -> bool:
    if not user_id:
        return False
    staff = set(getattr(config, "OWNER_IDS", [])) | set(getattr(config, "CO_OWNER_IDS", [])) | set(getattr(config, "DEV_IDS", [])) | set(getattr(config, "ADMIN_IDS", []))
    return user_id in staff


@router.message(Command("setvip", "givevip", ignore_mention=True))
async def cmd_set_vip(message: Message, db: AsyncSession):
    """Admin: /setvip <user_id_or_reply> <days> [tier_name]"""
    sender_id = message.from_user.id if message.from_user else None
    if not is_bot_staff(sender_id):
        await message.answer("⛔ Access denied. Only Bot Admins, Developers & Owners can grant VIP.", parse_mode="HTML")
        return

    args = (message.text or "").strip().split()
    target_user_id = None
    days = 30
    tier_name = None

    if message.reply_to_message and message.reply_to_message.from_user:
        target_user_id = message.reply_to_message.from_user.id
        if len(args) > 1 and args[1].isdigit():
            days = int(args[1])
            tier_name = " ".join(args[2:]) if len(args) > 2 else None
    else:
        if len(args) < 3:
            await message.answer(
                "⚠️ <b>Usage:</b> <code>/setvip &lt;user_id&gt; &lt;days&gt; [optional_tier_name]</code>\n"
                "<i>Example:</i> <code>/setvip 123456789 30 Monthly VIP</code>\n"
                "<i>Or reply to a user's message with:</i> <code>/setvip 30</code>",
                parse_mode="HTML"
            )
            return
        if not args[1].isdigit():
            await message.answer("❌ Invalid User ID.", parse_mode="HTML")
            return
        target_user_id = int(args[1])
        days = int(args[2]) if args[2].isdigit() else 30
        tier_name = " ".join(args[3:]) if len(args) > 3 else None

    u_stmt = select(User).where(User.id == target_user_id)
    u_res = await db.execute(u_stmt)
    target_user = u_res.scalar_one_or_none()

    if not target_user:
        target_user = User(id=target_user_id, nickname=f"Trainer_{target_user_id}", coins=500)
        db.add(target_user)
        await db.flush()

    await set_user_vip(db, target_user, days, tier_name)
    details = get_vip_details(target_user)
    exp = details["expires_at"].strftime("%Y-%m-%d %H:%M UTC") if details["expires_at"] else "Permanent"

    await message.answer(
        f"✅ <b>VIP GRANTED SUCCESSFULLY!</b>\n"
        f"◈ ────────────────────────── ◈\n"
        f"• 👤 <b>User ID:</b> <code>{target_user_id}</code>\n"
        f"• 🎖️ <b>Plan Tier:</b> <b>{details['tier']}</b>\n"
        f"• ⏱️ <b>Duration:</b> +{days} Days\n"
        f"• 📅 <b>Valid Until:</b> <code>{exp}</code>\n"
        f"◈ ────────────────────────── ◈",
        parse_mode="HTML"
    )


@router.message(Command("removevip", "revokevip", ignore_mention=True))
async def cmd_remove_vip(message: Message, db: AsyncSession):
    """Admin: /removevip <user_id_or_reply>"""
    sender_id = message.from_user.id if message.from_user else None
    if not is_bot_staff(sender_id):
        await message.answer("⛔ Access denied.", parse_mode="HTML")
        return

    args = (message.text or "").strip().split()
    target_user_id = None
    if message.reply_to_message and message.reply_to_message.from_user:
        target_user_id = message.reply_to_message.from_user.id
    elif len(args) > 1 and args[1].isdigit():
        target_user_id = int(args[1])

    if not target_user_id:
        await message.answer("⚠️ <b>Usage:</b> <code>/removevip &lt;user_id&gt;</code> or reply to a user.", parse_mode="HTML")
        return

    u_stmt = select(User).where(User.id == target_user_id)
    u_res = await db.execute(u_stmt)
    target_user = u_res.scalar_one_or_none()
    if not target_user:
        await message.answer("❌ User not found in database.", parse_mode="HTML")
        return

    await remove_user_vip(db, target_user)
    await message.answer(f"✅ <b>VIP Privileges Revoked</b> for Trainer <code>{target_user_id}</code>.", parse_mode="HTML")


@router.message(Command("giftgems", "addgems", ignore_mention=True))
async def cmd_gift_gems(message: Message, db: AsyncSession):
    """Admin: /giftgems <user_id_or_reply> <amount>"""
    sender_id = message.from_user.id if message.from_user else None
    if not is_bot_staff(sender_id):
        await message.answer("⛔ Access denied.", parse_mode="HTML")
        return

    args = (message.text or "").strip().split()
    target_user_id = None
    amount = 0

    if message.reply_to_message and message.reply_to_message.from_user:
        target_user_id = message.reply_to_message.from_user.id
        if len(args) > 1 and args[1].isdigit():
            amount = int(args[1])
    elif len(args) > 2 and args[1].isdigit() and args[2].isdigit():
        target_user_id = int(args[1])
        amount = int(args[2])

    if not target_user_id or amount <= 0:
        await message.answer("⚠️ <b>Usage:</b> <code>/giftgems &lt;user_id&gt; &lt;amount&gt;</code>", parse_mode="HTML")
        return

    u_stmt = select(User).where(User.id == target_user_id)
    u_res = await db.execute(u_stmt)
    target_user = u_res.scalar_one_or_none()
    if not target_user:
        target_user = User(id=target_user_id, nickname=f"Trainer_{target_user_id}", coins=500)
        db.add(target_user)
        await db.flush()

    new_total = await add_poke_gems(db, target_user, amount)
    await message.answer(
        f"💎 <b>POKEGEMS GIFTED!</b>\n"
        f"◈ ────────────────────────── ◈\n"
        f"• 👤 <b>Recipient:</b> <code>{target_user_id}</code>\n"
        f"• ⭐ <b>Added:</b> +{amount:,} PokeGems\n"
        f"• 💳 <b>New Balance:</b> {new_total:,} PokeGems\n"
        f"◈ ────────────────────────── ◈",
        parse_mode="HTML"
    )


# ── CALLBACK QUERY HANDLERS ──────────────────────────────────────────────────
@router.callback_query(F.data == "vip_refresh_status")
async def cb_vip_refresh_status(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id
    user_name = callback.from_user.first_name or "Trainer"
    u_stmt = select(User).where(User.id == user_id)
    u_res = await db.execute(u_stmt)
    user_db = u_res.scalar_one_or_none()

    text, markup = build_vip_plan_card(user_db, user_id, user_name)
    try:
        await callback.message.edit_text(text, reply_markup=markup, parse_mode="HTML")
    except Exception:
        pass
    await callback.answer("🔄 VIP Status updated!")


@router.callback_query(F.data == "vip_show_pricing")
async def cb_vip_show_pricing(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id
    user_name = callback.from_user.first_name or "Trainer"
    # Show pricing view
    text = (
        "💎 <b>VIP MEMBERSHIP PLANS & PRICING</b> 💎\n"
        "◈ ───────────────────────────────── ◈\n"
        "• 🥉 <b>Weekly (7 Days):</b> <code>₹39</code>\n"
        "• 🥈 <b>Monthly (30 Days):</b> <code>₹79</code>\n"
        "• 🥇 <b>2 Months (60 Days):</b> <code>₹129</code>\n"
        "• 👑 <b>3 Months (90 Days):</b> <code>₹199</code>\n\n"
        "<blockquote>✨ <b>Includes full access to:</b>\n"
        "• 🎨 <code>/vipclaim</code> &mdash; Rare non-.0 alternate art Pokémon!\n"
        "• 🎁 <code>/vipdaily</code> &mdash; 50-80 ⭐ PokeGems + 2,500 Coins + Pokémon!\n"
        "• 👑 Royal 👑 VIP profile badge & priority perks!</blockquote>\n"
        "◈ ───────────────────────────────── ◈\n"
        "<i>To purchase or renew, tap Contact Owner below!</i>"
    )
    owner_id = config.OWNER_IDS[0] if config.OWNER_IDS else 6593485710
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="💳 Contact Owner to Buy", url=f"tg://user?id={owner_id}", style="success"))
    builder.row(InlineKeyboardButton(text="🔙 Back to VIP Dashboard", callback_data="vip_refresh_status", style="primary"))
    try:
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        pass
    await callback.answer()


@router.callback_query(F.data == "vip_preview_daily")
async def cb_vip_preview_daily(callback: CallbackQuery):
    text = (
        "🎁 <b>VIP DAILY PREVIEW</b>\n"
        "◈ ────────────────────────── ◈\n"
        "Every 24 hours, VIP members claim:\n\n"
        "✨ <b>+50 to +80 ⭐ PokeGems</b> (Random bonus)\n"
        "💰 <b>+2,500 Gold Coins</b>\n"
        "👾 <b>Free Pokémon Capture</b>\n"
        "🎉 <b>+50 bonus PokeGems on every 7-Day streak!</b>\n"
        "◈ ────────────────────────── ◈"
    )
    await callback.answer(text, show_alert=True)


@router.callback_query(F.data == "vip_preview_claim")
async def cb_vip_preview_claim(callback: CallbackQuery):
    text = (
        "🎨 <b>VIP CLAIM PREVIEW</b>\n"
        "◈ ────────────────────────── ◈\n"
        "Unlike /claim which only awards base .0 art:\n\n"
        "🎨 /vipclaim guarantees exclusive non-.0 alternate form Pokémon!\n"
        "• 🎬 AMV / Special Art (Form .1)\n"
        "• ⚡ Dynamax (Form .2)\n"
        "• 💥 Gigantamax (Form .3)\n"
        "• 🌀 Z-Move (Form .4)\n"
        "• 🔮 Terastal (Form .5)\n"
        "• 🌟 Custom Tiers & boosted shiny rates!\n"
        "◈ ────────────────────────── ◈"
    )
    await callback.answer(text, show_alert=True)


@router.callback_query(F.data == "vip_act_daily")
async def cb_vip_act_daily(callback: CallbackQuery, db: AsyncSession):
    await callback.answer("⚡ Running /vipdaily...")
    await cmd_vip_daily(callback.message, db)


@router.callback_query(F.data == "vip_act_claim")
async def cb_vip_act_claim(callback: CallbackQuery, db: AsyncSession):
    await callback.answer("⚡ Running /vipclaim...")
    await cmd_vip_claim(callback.message, db)
