from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import config
import html
import asyncio
import time
from datetime import datetime, timedelta
from database.models import User, Pokemon, UserPokemon, Auction, AuctionBid
from utils.formatters import get_rarity_emoji
from utils.settings import get_custom_rarity_forms, get_all_custom_rarities
from handlers.admin import get_single_form_media_value, parse_stored_media_value

router = Router()
active_custom_bids = {}  # user_id -> auction_id
auction_channel_cache = {}  # user_id -> (is_member: bool, timestamp: float)


async def check_auction_channel_membership(bot: Bot, user_id: int) -> bool:
    """Checks if user is a member of config.AUCTION_CHANNEL (@PokeEmpireAuctions).
    Admins bypass. Uses 5-minute cache for True, 15-second cache for False."""
    if user_id in config.ADMIN_IDS:
        return True

    now = time.time()
    if user_id in auction_channel_cache:
        cached_val, cached_time = auction_channel_cache[user_id]
        cache_duration = 300 if cached_val else 15
        if now - cached_time < cache_duration:
            return cached_val

    is_member = False
    try:
        channel_id = config.AUCTION_CHANNEL or "@PokeEmpireAuctions"
        chat_member = await bot.get_chat_member(chat_id=channel_id, user_id=user_id)
        if chat_member.status not in ["left", "kicked"]:
            is_member = True
    except Exception as e:
        print(f"⚠️ Membership check error for {config.AUCTION_CHANNEL} (user {user_id}): {e}")
        is_member = False

    auction_channel_cache[user_id] = (is_member, now)
    return is_member


def get_channel_join_keyboard() -> InlineKeyboardMarkup:
    channel_url = "https://t.me/PokeEmpireAuctions"
    if config.AUCTION_CHANNEL and config.AUCTION_CHANNEL.startswith("@"):
        channel_url = f"https://t.me/{config.AUCTION_CHANNEL[1:]}"
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📢 Join @PokeEmpireAuctions", url=channel_url)
    ]])


def parse_duration(duration_str: str) -> int:
    """Parses duration string like '5m', '1h', '30s', '10' into seconds.
    Defaults to 300 seconds (5m) and caps at 300 seconds max (5 minutes)."""
    if not duration_str:
        return 300
    
    s = duration_str.strip().lower()
    total_sec = 300
    try:
        if s.endswith("h"):
            total_sec = int(s[:-1]) * 3600
        elif s.endswith("m"):
            total_sec = int(s[:-1]) * 60
        elif s.endswith("s"):
            total_sec = int(s[:-1])
        elif s.isdigit():
            total_sec = int(s) * 60
    except ValueError:
        total_sec = 300

    if total_sec < 60:
        total_sec = 60
    if total_sec > 300:
        total_sec = 300
        
    return total_sec


async def get_auction_card(db: AsyncSession, auction: Auction) -> tuple[str, str, str | None]:
    """Generates the text caption, media type and media value for an auction card."""
    stmt = select(Pokemon).where(Pokemon.id == auction.pokemon_id)
    res = await db.execute(stmt)
    pokemon = res.scalar_one()

    custom_rarities = await get_all_custom_rarities(db)
    custom_forms = await get_custom_rarity_forms(db)
    
    r_emoji = get_rarity_emoji(pokemon.rarity, custom_rarities)
    
    form_names = {
        0: "Standard",
        1: "AMV/Art",
        2: "Dmax",
        3: "Gmax",
        4: "Z-Move",
        5: "Terastal"
    }
    for f_idx, (r_name, r_emoji_f) in custom_forms.items():
        form_names[f_idx] = r_name
        
    form_label = form_names.get(auction.form_index, f"Form {auction.form_index}")

    stmt_seller = select(User).where(User.id == auction.seller_id)
    res_seller = await db.execute(stmt_seller)
    seller = res_seller.scalar_one_or_none()
    seller_name = seller.nickname or seller.username or f"Trainer {seller.id}" if seller else f"Trainer {auction.seller_id}"

    leader_name = "No bids yet"
    stmt_bids = (
        select(AuctionBid, User)
        .join(User, AuctionBid.bidder_id == User.id)
        .where(AuctionBid.auction_id == auction.id)
        .order_by(AuctionBid.amount.desc())
    )
    bids_res = await db.execute(stmt_bids)
    all_bids = bids_res.all()

    if all_bids:
        highest_bid_rec, bidder_user = all_bids[0]
        leader_name = bidder_user.nickname or bidder_user.username or f"Trainer {bidder_user.id}"

    if all_bids:
        bid_lines = []
        for bid_rec, bidder_user in all_bids[:5]:
            b_name = bidder_user.nickname or bidder_user.username or f"Trainer {bidder_user.id}"
            bid_time = bid_rec.bid_at.strftime("%H:%M:%S")
            bid_lines.append(f"├─ {html.escape(b_name)}: {bid_rec.amount:,} ({bid_time})")
        recent_bids_text = "\n".join(bid_lines)
    else:
        recent_bids_text = "╰─ No bids placed yet"

    time_left = auction.expires_at - datetime.utcnow()
    if time_left.total_seconds() <= 0:
        time_left_str = "Ended"
    else:
        seconds = int(time_left.total_seconds())
        hours, remainder = divmod(seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours > 0:
            time_left_str = f"{hours}h {minutes:02d}m"
        else:
            time_left_str = f"{minutes}m {secs:02d}s"

    title_status = f"🔮 ACTIVE AUCTION (#{auction.id:03d})" if auction.status == "ACTIVE" else f"🔮 AUCTION ENDED (#{auction.id:03d})"

    caption = (
        f"<b>{title_status}</b>\n"
        f"───────────────\n"
        f"<blockquote>🆔 <b>Pokédex ID</b>: <code>#{pokemon.id}</code>\n"
        f"📛 <b>Name</b>: <b>{pokemon.name.title()}</b> ({form_label})\n"
        f"💎 <b>Rarity</b>: {r_emoji} {pokemon.rarity}\n"
        f"🎫 <b>Serial Number</b>: <code>{auction.serial_number}</code>\n\n"
        f"💰 <b>Starting Price</b>: {auction.starting_price:,} coins\n"
        f"💣 <b>Current Bid</b>: <b>{auction.current_bid:,} coins</b>\n"
        f"👑 <b>Leader</b>: {html.escape(leader_name)}\n"
        f"👥 <b>Seller</b>: {html.escape(seller_name)}\n"
        f"⏳ <b>Time Remaining</b>: <code>{time_left_str}</code></blockquote>\n\n"
        f"📝 <b>Recent Bids:</b>\n"
        f"<blockquote>{recent_bids_text}</blockquote>\n\n"
        f"📢 Settlement Channel: @PokeEmpireAuctions"
    )

    media_type = "photo"
    media_value = pokemon.image_url
    if pokemon.image_url:
        media_type, media_value = parse_stored_media_value(pokemon.image_url)
    
    resolved_form = auction.form_index
    if auction.is_shiny and auction.form_index == 0:
        resolved_form = 6

    if resolved_form > 0:
        form_media = await get_single_form_media_value(db, pokemon.id, resolved_form)
        if form_media:
            media_type, media_value = parse_stored_media_value(form_media)
    else:
        if pokemon.video_url:
            media_type, media_value = parse_stored_media_value(pokemon.video_url)

    return caption, media_type, media_value


def get_auction_keyboard(auction_id: int, owner_id: int) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="💵 +1,000", callback_data=f"auc_bid_{auction_id}_1000"),
        InlineKeyboardButton(text="💵 +5,000", callback_data=f"auc_bid_{auction_id}_5000")
    )
    builder.row(
        InlineKeyboardButton(text="💵 +10,000", callback_data=f"auc_bid_{auction_id}_10000"),
        InlineKeyboardButton(text="💬 Custom Bid", callback_data=f"auc_custom_{auction_id}")
    )
    return builder


async def process_auction_bid(db: AsyncSession, bot: Bot, auction: Auction, bidder_user: User, bid_amount: int) -> tuple[bool, str]:
    """Centralized helper to process a bid. Performs balance check, outbid DM notification, refund, anti-snipe time extension, and updates DB & card."""
    if auction.seller_id == bidder_user.id:
        return False, "❌ You cannot bid on your own auction!"

    if auction.status != "ACTIVE":
        return False, "❌ Auction is no longer active."

    min_next_bid = auction.current_bid + 1
    if bid_amount < min_next_bid:
        return False, f"❌ Your bid must be at least {min_next_bid:,} coins."

    if bidder_user.coins < bid_amount:
        return False, f"❌ Insufficient coins! Your balance: {bidder_user.coins:,} coins."

    stmt_prev_bids = (
        select(AuctionBid)
        .where(AuctionBid.auction_id == auction.id)
        .order_by(AuctionBid.amount.desc())
        .limit(1)
    )
    prev_bids_res = await db.execute(stmt_prev_bids)
    prev_highest_bid = prev_bids_res.scalar_one_or_none()

    if prev_highest_bid:
        stmt_prev_user = select(User).where(User.id == prev_highest_bid.bidder_id)
        res_prev_user = await db.execute(stmt_prev_user)
        prev_user = res_prev_user.scalar_one_or_none()
        
        if prev_user:
            prev_user.coins += prev_highest_bid.amount
            db.add(prev_user)

            if prev_highest_bid.bidder_id != bidder_user.id:
                try:
                    stmt_p = select(Pokemon.name).where(Pokemon.id == auction.pokemon_id)
                    res_p = await db.execute(stmt_p)
                    poke_name = res_p.scalar() or "Pokémon"

                    time_left = auction.expires_at - datetime.utcnow()
                    secs = max(0, int(time_left.total_seconds()))
                    mins, s = divmod(secs, 60)
                    time_str = f"{mins}m {s:02d}s" if secs > 0 else "Ending soon"

                    outbid_text = (
                        f"⚠️ <b>YOU HAVE BEEN OUTBID!</b> ⚠️\n"
                        f"───────────────\n"
                        f"<blockquote>Someone placed a higher bid of <b>{bid_amount:,} coins</b> on Auction <b>#{auction.id:03d}</b> ({poke_name.title()})!\n\n"
                        f"💰 Your bid of <b>{prev_highest_bid.amount:,} coins</b> was refunded to your balance.\n"
                        f"🆔 Pokédex ID: <code>#{auction.pokemon_id}</code> | 🎫 Serial: <code>{auction.serial_number}</code>\n"
                        f"⏳ Time Remaining: <code>{time_str}</code></blockquote>\n\n"
                        f"👉 Use <code>/bid {bid_amount + 1000}</code> or click buttons on the auction card to counter-bid!"
                    )
                    await bot.send_message(chat_id=prev_highest_bid.bidder_id, text=outbid_text, parse_mode="HTML")
                except Exception as outbid_err:
                    print(f"⚠️ Failed to send outbid notification to {prev_highest_bid.bidder_id}: {outbid_err}")

    bidder_user.coins -= bid_amount
    db.add(bidder_user)

    new_bid = AuctionBid(
        auction_id=auction.id,
        bidder_id=bidder_user.id,
        amount=bid_amount
    )
    db.add(new_bid)

    time_left_sec = (auction.expires_at - datetime.utcnow()).total_seconds()
    anti_snipe_msg = ""
    if time_left_sec < 30:
        auction.expires_at = datetime.utcnow() + timedelta(seconds=60)
        anti_snipe_msg = "\n⏰ <b>Anti-Snipe Protection Triggered!</b> Auction extended by 60 seconds."

    auction.current_bid = bid_amount
    await db.commit()

    if auction.channel_chat_id and auction.channel_message_id:
        caption, media_type, media_value = await get_auction_card(db, auction)
        kb = get_auction_keyboard(auction.id, auction.seller_id)
        try:
            await bot.edit_message_caption(
                chat_id=auction.channel_chat_id,
                message_id=auction.channel_message_id,
                caption=caption,
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
        except Exception as edit_err:
            print(f"⚠️ Failed to edit auction card: {edit_err}")

    return True, f"✅ Bid of <b>{bid_amount:,} coins</b> placed successfully on Auction <b>#{auction.id:03d}</b>!{anti_snipe_msg}"


async def send_auction_settlement_channel_report(bot: Bot, db: AsyncSession, auction: Auction, status_type: str):
    """Sends a full settlement report to @PokeEmpireAuctions channel with media, stats, seller, winner, payout, and complete bid history."""
    try:
        channel_id = config.AUCTION_CHANNEL
        if not channel_id:
            return

        stmt_p = select(Pokemon).where(Pokemon.id == auction.pokemon_id)
        res_p = await db.execute(stmt_p)
        pokemon = res_p.scalar_one_or_none()
        if not pokemon:
            return

        custom_rarities = await get_all_custom_rarities(db)
        custom_forms = await get_custom_rarity_forms(db)
        r_emoji = get_rarity_emoji(pokemon.rarity, custom_rarities)

        form_names = {
            0: "Standard", 1: "AMV/Art", 2: "Dmax", 3: "Gmax", 4: "Z-Move", 5: "Terastal"
        }
        for f_idx, (r_name, r_emoji_f) in custom_forms.items():
            form_names[f_idx] = r_name
        form_label = form_names.get(auction.form_index, f"Form {auction.form_index}")

        stmt_seller = select(User).where(User.id == auction.seller_id)
        res_seller = await db.execute(stmt_seller)
        seller = res_seller.scalar_one_or_none()
        seller_name = seller.nickname or seller.username or f"Trainer {seller.id}" if seller else f"Trainer {auction.seller_id}"
        seller_user_handle = f"@{seller.username}" if seller and seller.username else html.escape(seller_name)

        stmt_bids = (
            select(AuctionBid, User)
            .join(User, AuctionBid.bidder_id == User.id)
            .where(AuctionBid.auction_id == auction.id)
            .order_by(AuctionBid.amount.desc())
        )
        bids_res = await db.execute(stmt_bids)
        all_bids = bids_res.all()

        total_iv = auction.iv_hp + auction.iv_atk + auction.iv_def + auction.iv_spd
        iv_pct = (total_iv / 124.0) * 100

        if status_type == "COMPLETED" and all_bids:
            highest_bid_rec, winner_user = all_bids[0]
            winner_name = winner_user.nickname or winner_user.username or f"Trainer {winner_user.id}"
            winner_handle = f"@{winner_user.username}" if winner_user.username else html.escape(winner_name)
            
            tax = int(highest_bid_rec.amount * 0.05)
            payout = highest_bid_rec.amount - tax

            title_header = "🎉 <b>AUCTION COMPLETED & SETTLED!</b> 🎉"
            winning_str = f"<b>{highest_bid_rec.amount:,} coins</b>"
            payout_str = f"<b>{payout:,} coins</b> (5% tax deducted: {tax:,})"
            winner_str = f"{winner_handle} (ID: <code>{winner_user.id}</code>)"
        elif status_type == "UNSOLD":
            title_header = "🪙 <b>AUCTION ENDED — UNSOLD</b>"
            winning_str = "<i>No bids placed</i>"
            payout_str = "<i>N/A (Returned to Seller)</i>"
            winner_str = "<i>None (No bids)</i>"
        else:
            title_header = "🚫 <b>AUCTION CANCELLED</b>"
            winning_str = "<i>Cancelled</i>"
            payout_str = "<i>N/A (Returned to Seller)</i>"
            winner_str = "<i>None</i>"

        if all_bids:
            history_lines = []
            for rank, (bid_rec, bidder_u) in enumerate(all_bids, start=1):
                b_name = bidder_u.nickname or bidder_u.username or f"Trainer {bidder_u.id}"
                b_handle = f"@{bidder_u.username}" if bidder_u.username else html.escape(b_name)
                b_time = bid_rec.bid_at.strftime("%H:%M:%S UTC")
                
                if rank == 1:
                    rank_icon = "🥇"
                elif rank == 2:
                    rank_icon = "🥈"
                elif rank == 3:
                    rank_icon = "🥉"
                else:
                    rank_icon = "🔹"

                history_lines.append(f"{rank_icon} <b>#{rank}</b> {b_handle} — <b>{bid_rec.amount:,} coins</b> ({b_time})")
            bid_history_text = "\n".join(history_lines)
        else:
            bid_history_text = "<i>No bids were placed on this auction.</i>"

        caption_text = (
            f"{title_header}\n"
            f"───────────────\n"
            f"<blockquote>📌 <b>Auction ID</b>: <code>#{auction.id:03d}</code>\n"
            f"🆔 <b>Pokédex ID</b>: <code>#{pokemon.id}</code> | 🎫 <b>Serial Number</b>: <code>{auction.serial_number}</code>\n"
            f"📛 <b>Pokémon</b>: <b>{pokemon.name.title()}</b> ({form_label})\n"
            f"💎 <b>Rarity</b>: {r_emoji} {pokemon.rarity}</blockquote>\n\n"
            f"<blockquote>👥 <b>Seller</b>: {seller_user_handle} (ID: <code>{auction.seller_id}</code>)\n"
            f"👑 <b>Buyer / Winner</b>: {winner_str}\n"
            f"💰 <b>Starting Price</b>: {auction.starting_price:,} coins\n"
            f"🔨 <b>Winning Bid</b>: {winning_str}\n"
            f"💸 <b>Seller Net Payout</b>: {payout_str}</blockquote>\n\n"
            f"📜 <b>COMPLETE BID HISTORY ({len(all_bids)} bids):</b>\n"
            f"<blockquote>{bid_history_text}</blockquote>\n\n"
            f"📢 Official Channel: @PokeEmpireAuctions"
        )

        media_type = "photo"
        media_value = pokemon.image_url
        if pokemon.image_url:
            media_type, media_value = parse_stored_media_value(pokemon.image_url)

        resolved_form = auction.form_index
        if auction.is_shiny and auction.form_index == 0:
            resolved_form = 6

        if resolved_form > 0:
            form_media = await get_single_form_media_value(db, pokemon.id, resolved_form)
            if form_media:
                media_type, media_value = parse_stored_media_value(form_media)
        else:
            if pokemon.video_url:
                media_type, media_value = parse_stored_media_value(pokemon.video_url)

        if len(caption_text) <= 1024:
            if media_type == "video":
                await bot.send_video(chat_id=channel_id, video=media_value, caption=caption_text, parse_mode="HTML")
            elif media_type == "animation":
                await bot.send_animation(chat_id=channel_id, animation=media_value, caption=caption_text, parse_mode="HTML")
            else:
                await bot.send_photo(chat_id=channel_id, photo=media_value, caption=caption_text, parse_mode="HTML")
        else:
            short_caption = (
                f"{title_header}\n"
                f"───────────────\n"
                f"📌 <b>Auction ID</b>: <code>#{auction.id:03d}</code>\n"
                f"🆔 <b>Pokédex ID</b>: <code>#{pokemon.id}</code> | 🎫 <b>Serial</b>: <code>{auction.serial_number}</code>\n"
                f"📛 <b>Pokémon</b>: <b>{pokemon.name.title()}</b> ({form_label})\n"
                f"💎 <b>Rarity</b>: {r_emoji} {pokemon.rarity}\n"
                f"🔨 <b>Final Bid</b>: {winning_str}\n"
                f"👑 <b>Winner</b>: {winner_str}\n\n"
                f"👇 <b>See full bid history in text message below!</b>"
            )
            if media_type == "video":
                await bot.send_video(chat_id=channel_id, video=media_value, caption=short_caption, parse_mode="HTML")
            elif media_type == "animation":
                await bot.send_animation(chat_id=channel_id, animation=media_value, caption=short_caption, parse_mode="HTML")
            else:
                await bot.send_photo(chat_id=channel_id, photo=media_value, caption=short_caption, parse_mode="HTML")

            await bot.send_message(chat_id=channel_id, text=caption_text, parse_mode="HTML")

    except Exception as report_err:
        print(f"⚠️ Failed to post settlement report to {config.AUCTION_CHANNEL}: {report_err}")


@router.message(Command("auction"))
async def cmd_create_auction(message: Message, db: AsyncSession):
    from utils.settings import global_settings_cache
    if global_settings_cache.get("auctions_enabled", "on") == "off":
        await message.answer("❌ The Auction system is currently disabled globally by the Bot Owner.")
        return

    # Check Channel Membership Requirement
    if not await check_auction_channel_membership(message.bot, message.from_user.id):
        await message.answer(
            "📢 <b>AUCTION CHANNEL JOIN REQUIRED!</b> 📢\n"
            "───────────────\n"
            "<blockquote>You must join our official Auction Channel <b>@PokeEmpireAuctions</b> to create or list auctions!</blockquote>\n\n"
            "👉 Join the channel using the button below and try again!",
            reply_markup=get_channel_join_keyboard(),
            parse_mode="HTML"
        )
        return

    is_owner = (message.from_user.id in config.ADMIN_IDS)

    if not is_owner:
        active_stmt = select(func.count(Auction.id)).where(
            Auction.seller_id == message.from_user.id,
            Auction.status.in_({"ACTIVE", "PENDING"})
        )
        active_res = await db.execute(active_stmt)
        active_count = active_res.scalar() or 0
        if active_count > 0:
            await message.answer("❌ You can only have one active or queued auction at a time. Please wait for your current auction to end.")
            return

    parts = message.text.split()
    if len(parts) < 3:
        await message.answer(
            "⚠️ <b>Usage:</b>\n"
            "<code>/auction &lt;Pokedex_ID_or_Name&gt; &lt;Starting_Price&gt; [duration]</code>\n\n"
            "Example: <code>/auction 6 10000</code> or <code>/auction charizard 10000 5m</code>",
            parse_mode="HTML"
        )
        return

    poke_input = parts[1].strip()
    form_index = 0
    target_poke = poke_input
    if "." in poke_input:
        pq, fq = poke_input.split(".", 1)
        if fq.isdigit():
            form_index = int(fq)
        target_poke = pq

    try:
        starting_price = int(parts[2].replace(",", ""))
    except ValueError:
        await message.answer("❌ Starting price must be a valid integer.")
        return

    if starting_price <= 0:
        await message.answer("❌ Starting price must be greater than 0.")
        return

    duration_str = parts[3] if len(parts) >= 4 else "5m"
    duration_sec = parse_duration(duration_str)

    if target_poke.isdigit():
        stmt_poke = select(Pokemon).where(Pokemon.id == int(target_poke))
    else:
        stmt_poke = select(Pokemon).where(Pokemon.name.ilike(target_poke))
    
    res_poke = await db.execute(stmt_poke)
    pokemon = res_poke.scalar_one_or_none()
    if not pokemon:
        await message.answer(f"❌ Pokémon '{target_poke}' not found in database.")
        return

    stmt = (
        select(UserPokemon)
        .where(
            UserPokemon.user_id == message.from_user.id,
            UserPokemon.pokemon_id == pokemon.id,
            UserPokemon.form_index == form_index
        )
        .order_by(UserPokemon.level.desc(), UserPokemon.id.asc())
        .limit(1)
    )
    res = await db.execute(stmt)
    user_poke = res.scalar_one_or_none()

    if not user_poke:
        if is_owner:
            pokemon_id = pokemon.id
            form_index = form_index
            is_shiny = False
            is_amv = (form_index == 1)
            nickname = None
            serial = "#ADMIN"
            level = 100
            xp = 0
            iv_hp, iv_atk, iv_def, iv_spd = 31, 31, 31, 31
        else:
            form_label = f"Form {form_index}" if form_index > 0 else "standard"
            await message.answer(f"❌ You don't own any <b>{pokemon.name.title()}</b> ({form_label}) in your inventory.", parse_mode="HTML")
            return
    else:
        pokemon_id = user_poke.pokemon_id
        form_index = user_poke.form_index
        is_shiny = user_poke.is_shiny
        is_amv = user_poke.is_amv
        nickname = user_poke.nickname
        serial = user_poke.serial_number
        level = user_poke.level
        xp = user_poke.xp
        iv_hp = user_poke.iv_hp
        iv_atk = user_poke.iv_atk
        iv_def = user_poke.iv_def
        iv_spd = user_poke.iv_spd

        await db.delete(user_poke)
        await db.commit()

    global_active_stmt = select(func.count(Auction.id)).where(Auction.status == "ACTIVE")
    global_active_res = await db.execute(global_active_stmt)
    global_active_count = global_active_res.scalar() or 0

    if global_active_count > 0:
        expires_at = datetime.utcnow() + timedelta(days=365)
        auction = Auction(
            seller_id=message.from_user.id,
            pokemon_id=pokemon_id,
            nickname=nickname,
            is_shiny=is_shiny,
            is_amv=is_amv,
            form_index=form_index,
            serial_number=serial,
            level=level,
            xp=xp,
            iv_hp=iv_hp,
            iv_atk=iv_atk,
            iv_def=iv_def,
            iv_spd=iv_spd,
            starting_price=starting_price,
            current_bid=starting_price,
            expires_at=expires_at,
            status="PENDING",
            channel_chat_id=message.chat.id
        )
        db.add(auction)
        await db.commit()
        await db.refresh(auction)

        pending_stmt = select(func.count(Auction.id)).where(Auction.status == "PENDING")
        pending_res = await db.execute(pending_stmt)
        queue_pos = pending_res.scalar() or 0

        await message.answer(
            f"🕒 <b>Added to Auction Queue!</b>\n"
            f"───────────────\n"
            f"<blockquote>🆔 Pokédex ID: <code>#{pokemon.id}</code>\n"
            f"📛 Pokémon: <b>{pokemon.name.title()}</b>\n"
            f"💰 Starting Price: <b>{starting_price:,} coins</b>\n"
            f"🔢 Queue Position: <b>#{queue_pos}</b></blockquote>\n\n"
            f"It will start automatically once active auctions ahead of it finish.",
            parse_mode="HTML"
        )
        return

    expires_at = datetime.utcnow() + timedelta(seconds=duration_sec)
    auction = Auction(
        seller_id=message.from_user.id,
        pokemon_id=pokemon_id,
        nickname=nickname,
        is_shiny=is_shiny,
        is_amv=is_amv,
        form_index=form_index,
        serial_number=serial,
        level=level,
        xp=xp,
        iv_hp=iv_hp,
        iv_atk=iv_atk,
        iv_def=iv_def,
        iv_spd=iv_spd,
        starting_price=starting_price,
        current_bid=starting_price,
        expires_at=expires_at,
        status="ACTIVE"
    )
    db.add(auction)
    await db.commit()
    await db.refresh(auction)

    caption, media_type, media_value = await get_auction_card(db, auction)
    kb = get_auction_keyboard(auction.id, message.from_user.id)

    try:
        if media_type == "video":
            auc_msg = await message.bot.send_video(
                chat_id=message.chat.id,
                video=media_value,
                caption=caption,
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
        elif media_type == "animation":
            auc_msg = await message.bot.send_animation(
                chat_id=message.chat.id,
                animation=media_value,
                caption=caption,
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
        else:
            auc_msg = await message.bot.send_photo(
                chat_id=message.chat.id,
                photo=media_value,
                caption=caption,
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )

        auction.channel_message_id = auc_msg.message_id
        auction.channel_chat_id = message.chat.id
        await db.commit()

        if message.chat.type != "private":
            try:
                await message.bot.pin_chat_message(chat_id=message.chat.id, message_id=auc_msg.message_id)
            except Exception as pin_err:
                print(f"⚠️ Failed to pin auction message: {pin_err}")
                
    except Exception as e:
        restored = UserPokemon(
            user_id=message.from_user.id,
            pokemon_id=pokemon_id,
            nickname=nickname,
            is_shiny=is_shiny,
            is_amv=is_amv,
            form_index=form_index,
            serial_number=serial,
            level=level,
            xp=xp,
            iv_hp=iv_hp,
            iv_atk=iv_atk,
            iv_def=iv_def,
            iv_spd=iv_spd
        )
        db.add(restored)
        auction.status = "CANCELLED"
        await db.commit()
        await message.answer(f"❌ Failed to list auction: {e}. Your Pokémon has been returned.")


@router.message(Command("auctions", "auc"))
async def cmd_list_auctions(message: Message, db: AsyncSession):
    stmt = select(Auction).where(Auction.status == "ACTIVE").order_by(Auction.expires_at.asc())
    res = await db.execute(stmt)
    auctions = res.scalars().all()

    if not auctions:
        await message.answer("🛒 No active auctions found at the moment.")
        return

    text = "🛒 <b>ACTIVE AUCTION LISTINGS</b> 🛒\n───────────────\n\n"
    for a in auctions:
        stmt_p = select(Pokemon).where(Pokemon.id == a.pokemon_id)
        res_p = await db.execute(stmt_p)
        poke = res_p.scalar_one_or_none()
        p_name = poke.name.title() if poke else "Unknown"
        p_id = poke.id if poke else 0
        
        time_left = a.expires_at - datetime.utcnow()
        if time_left.total_seconds() <= 0:
            time_left_str = "Ended"
        else:
            seconds = int(time_left.total_seconds())
            hours, remainder = divmod(seconds, 3600)
            minutes, secs = divmod(remainder, 60)
            if hours > 0:
                time_left_str = f"{hours}h {minutes:02d}m"
            else:
                time_left_str = f"{minutes}m {secs:02d}s"

        text += (
            f"• <b>#{a.id:03d}</b> | 🆔 Pokédex: <code>#{p_id}</code> — <b>{p_name}</b>\n"
            f"  └ 🎫 Serial: <code>{a.serial_number}</code> | 💰 Current Bid: <b>{a.current_bid:,} coins</b>\n"
            f"  └ ⏳ Time remaining: <code>{time_left_str}</code>\n\n"
        )

    text += "👉 Bid on active auction using: <code>/bid &lt;amount&gt;</code> or click buttons on the card!"
    await message.answer(text, parse_mode="HTML")


@router.message(Command("bid"))
async def cmd_bid_manual(message: Message, db: AsyncSession):
    # Check Channel Membership Requirement
    if not await check_auction_channel_membership(message.bot, message.from_user.id):
        await message.answer(
            "📢 <b>AUCTION CHANNEL JOIN REQUIRED!</b> 📢\n"
            "───────────────\n"
            "<blockquote>You must join our official Auction Channel <b>@PokeEmpireAuctions</b> to place bids!</blockquote>\n\n"
            "👉 Join the channel using the button below and try again!",
            reply_markup=get_channel_join_keyboard(),
            parse_mode="HTML"
        )
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            "⚠️ <b>Usage:</b>\n"
            "• <code>/bid &lt;amount&gt;</code> (Bids on current active auction)\n"
            "• <code>/bid &lt;auction_id&gt; &lt;amount&gt;</code> (Bids on specific auction)\n\n"
            "Example: <code>/bid 25000</code> or <code>/bid 1 25000</code>",
            parse_mode="HTML"
        )
        return

    auction_id = None
    bid_amount = None

    if len(parts) == 2:
        try:
            bid_amount = int(parts[1].replace(",", ""))
        except ValueError:
            await message.answer("❌ Bid amount must be a valid integer.")
            return

        stmt_active = select(Auction).where(Auction.status == "ACTIVE").order_by(Auction.id.desc()).limit(2)
        res_active = await db.execute(stmt_active)
        active_auctions = res_active.scalars().all()

        if not active_auctions:
            await message.answer("❌ There are no active auctions at the moment.")
            return
        elif len(active_auctions) > 1:
            await message.answer(
                f"⚠️ Multiple active auctions exist. Please specify the Auction ID:\n"
                f"<code>/bid &lt;auction_id&gt; {bid_amount}</code>",
                parse_mode="HTML"
            )
            return
        else:
            auction_id = active_auctions[0].id
    else:
        try:
            auction_id = int(parts[1])
            bid_amount = int(parts[2].replace(",", ""))
        except ValueError:
            await message.answer("❌ Auction ID and bid amount must be valid integers.")
            return

    stmt = select(Auction).where(Auction.id == auction_id, Auction.status == "ACTIVE")
    res = await db.execute(stmt)
    auction = res.scalar_one_or_none()
    if not auction:
        await message.answer("❌ Auction not found or is no longer active.")
        return

    stmt_bidder = select(User).where(User.id == message.from_user.id)
    res_bidder = await db.execute(stmt_bidder)
    bidder = res_bidder.scalar_one()

    success, reply_msg = await process_auction_bid(db, message.bot, auction, bidder, bid_amount)
    await message.answer(reply_msg, parse_mode="HTML")


@router.callback_query(F.data.startswith("auc_bid_"))
async def cb_auc_increment_bid(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id

    if not await check_auction_channel_membership(callback.bot, user_id):
        await callback.answer("⚠️ You must join @PokeEmpireAuctions to place bids!", show_alert=True)
        return

    parts = callback.data.split("_")
    auction_id = int(parts[2])
    increment = int(parts[3])

    stmt = select(Auction).where(Auction.id == auction_id, Auction.status == "ACTIVE")
    res = await db.execute(stmt)
    auction = res.scalar_one_or_none()
    if not auction:
        await callback.answer("❌ Auction is no longer active.", show_alert=True)
        return

    bid_amount = auction.current_bid + increment

    stmt_bidder = select(User).where(User.id == user_id)
    res_bidder = await db.execute(stmt_bidder)
    bidder = res_bidder.scalar_one()

    success, msg_text = await process_auction_bid(db, callback.bot, auction, bidder, bid_amount)
    if success:
        await callback.answer(f"✅ Bid of {bid_amount:,} coins placed successfully!")
    else:
        await callback.answer(msg_text, show_alert=True)


@router.callback_query(F.data.startswith("auc_custom_"))
async def cb_auc_custom_bid(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id

    if not await check_auction_channel_membership(callback.bot, user_id):
        await callback.answer("⚠️ You must join @PokeEmpireAuctions to place custom bids!", show_alert=True)
        return

    parts = callback.data.split("_")
    auction_id = int(parts[2])

    stmt = select(Auction).where(Auction.id == auction_id, Auction.status == "ACTIVE")
    res = await db.execute(stmt)
    auction = res.scalar_one_or_none()
    if not auction:
        await callback.answer("❌ Auction is no longer active.", show_alert=True)
        return

    if auction.seller_id == user_id:
        await callback.answer("❌ You cannot bid on your own auction!", show_alert=True)
        return

    active_custom_bids[user_id] = auction.id

    await callback.message.answer(
        f"💬 <b>Custom Bid for Auction #{auction.id:03d}</b>\n"
        f"───────────────\n"
        f"Current highest bid: <b>{auction.current_bid:,} coins</b>\n\n"
        f"👉 Type your bid amount in chat (e.g. <code>{auction.current_bid + 5000:,}</code> or <code>/bid {auction.current_bid + 5000:,}</code>):",
        parse_mode="HTML"
    )
    await callback.answer()


@router.message(F.text & ~F.text.startswith("/"))
async def process_custom_bid_text(message: Message, db: AsyncSession):
    user_id = message.from_user.id
    if user_id not in active_custom_bids:
        return

    if not await check_auction_channel_membership(message.bot, user_id):
        await message.answer(
            "📢 <b>AUCTION CHANNEL JOIN REQUIRED!</b> 📢\n"
            "───────────────\n"
            "<blockquote>You must join our official Auction Channel <b>@PokeEmpireAuctions</b> to place bids!</blockquote>\n\n"
            "👉 Join the channel using the button below and try again!",
            reply_markup=get_channel_join_keyboard(),
            parse_mode="HTML"
        )
        return

    text = message.text.strip().replace(",", "")
    if not text.isdigit():
        return

    auction_id = active_custom_bids.pop(user_id, None)
    bid_amount = int(text)

    stmt = select(Auction).where(Auction.id == auction_id, Auction.status == "ACTIVE")
    res = await db.execute(stmt)
    auction = res.scalar_one_or_none()
    if not auction:
        await message.answer("❌ Auction is no longer active.")
        return

    stmt_bidder = select(User).where(User.id == user_id)
    res_bidder = await db.execute(stmt_bidder)
    bidder = res_bidder.scalar_one_or_none()

    if not bidder:
        return

    success, reply_msg = await process_auction_bid(db, message.bot, auction, bidder, bid_amount)
    await message.answer(reply_msg, parse_mode="HTML")


@router.message(Command("bidhistory", "auchistory"))
async def cmd_bid_history(message: Message, db: AsyncSession):
    parts = message.text.split()
    auction_id = None

    if len(parts) >= 2 and parts[1].isdigit():
        auction_id = int(parts[1])
    else:
        stmt_latest = select(Auction).order_by(Auction.id.desc()).limit(1)
        res_latest = await db.execute(stmt_latest)
        latest = res_latest.scalar_one_or_none()
        if latest:
            auction_id = latest.id

    if not auction_id:
        await message.answer("❌ No auction found.")
        return

    stmt = select(Auction).where(Auction.id == auction_id)
    res = await db.execute(stmt)
    auction = res.scalar_one_or_none()
    if not auction:
        await message.answer(f"❌ Auction #{auction_id:03d} not found.")
        return

    stmt_p = select(Pokemon).where(Pokemon.id == auction.pokemon_id)
    res_p = await db.execute(stmt_p)
    pokemon = res_p.scalar_one()

    stmt_bids = (
        select(AuctionBid, User)
        .join(User, AuctionBid.bidder_id == User.id)
        .where(AuctionBid.auction_id == auction.id)
        .order_by(AuctionBid.amount.desc())
    )
    res_bids = await db.execute(stmt_bids)
    all_bids = res_bids.all()

    text = (
        f"📜 <b>BID HISTORY FOR AUCTION #{auction.id:03d}</b> 📜\n"
        f"───────────────\n"
        f"🆔 <b>Pokédex ID</b>: <code>#{pokemon.id}</code> | 📛 <b>Pokémon</b>: <b>{pokemon.name.title()}</b>\n"
        f"🎫 <b>Serial</b>: <code>{auction.serial_number}</code> | 💰 <b>Starting</b>: {auction.starting_price:,} coins\n"
        f"Status: <b>{auction.status}</b> | Total Bids: <b>{len(all_bids)}</b>\n"
        f"───────────────\n"
    )

    if all_bids:
        for rank, (bid_rec, bidder_u) in enumerate(all_bids, start=1):
            b_name = bidder_u.nickname or bidder_u.username or f"Trainer {bidder_u.id}"
            b_time = bid_rec.bid_at.strftime("%Y-%m-%d %H:%M:%S UTC")
            rank_icon = "🥇" if rank == 1 else ("🥈" if rank == 2 else ("🥉" if rank == 3 else "🔹"))
            text += f"{rank_icon} <b>#{rank}</b> {html.escape(b_name)}: <b>{bid_rec.amount:,} coins</b> (<code>{b_time}</code>)\n"
    else:
        text += "<i>No bids have been placed on this auction.</i>"

    await message.answer(text, parse_mode="HTML")


@router.message(Command("cancelauction"))
async def cmd_cancel_auction(message: Message, db: AsyncSession):
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("⚠️ Usage: <code>/cancelauction &lt;auction_id&gt;</code>", parse_mode="HTML")
        return

    try:
        auction_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Invalid Auction ID.")
        return

    stmt = select(Auction).where(Auction.id == auction_id, Auction.status.in_({"ACTIVE", "PENDING"}))
    res = await db.execute(stmt)
    auction = res.scalar_one_or_none()
    if not auction:
        await message.answer("❌ Auction not found, or it has already ended.")
        return

    if auction.seller_id != message.from_user.id:
        await message.answer("❌ You can only cancel your own auctions.")
        return

    bid_count = 0
    if auction.status == "ACTIVE":
        stmt_bids = select(func.count(AuctionBid.id)).where(AuctionBid.auction_id == auction.id)
        res_bids = await db.execute(stmt_bids)
        bid_count = res_bids.scalar() or 0

    if bid_count > 0:
        await message.answer("❌ You cannot cancel this auction since active bids have already been placed.")
        return

    restored = UserPokemon(
        user_id=message.from_user.id,
        pokemon_id=auction.pokemon_id,
        nickname=auction.nickname,
        is_shiny=auction.is_shiny,
        is_amv=auction.is_amv,
        form_index=auction.form_index,
        serial_number=auction.serial_number,
        level=auction.level,
        xp=auction.xp,
        iv_hp=auction.iv_hp,
        iv_atk=auction.iv_atk,
        iv_def=auction.iv_def,
        iv_spd=auction.iv_spd
    )
    db.add(restored)
    
    was_active = (auction.status == "ACTIVE")
    auction.status = "CANCELLED"
    await db.commit()

    if was_active:
        await send_auction_settlement_channel_report(message.bot, db, auction, "CANCELLED")

        if auction.channel_chat_id and auction.channel_message_id:
            try:
                await message.bot.unpin_chat_message(chat_id=auction.channel_chat_id, message_id=auction.channel_message_id)
            except Exception:
                pass
                
            caption, media_type, media_value = await get_auction_card(db, auction)
            try:
                await message.bot.edit_message_caption(
                    chat_id=auction.channel_chat_id,
                    message_id=auction.channel_message_id,
                    caption=caption,
                    reply_markup=None,
                    parse_mode="HTML"
                )
            except Exception:
                pass

    await message.answer("✅ Auction cancelled successfully! Your Pokémon has been returned to your inventory.")

    if was_active:
        try:
            next_stmt = select(Auction).where(Auction.status == "PENDING").order_by(Auction.created_at.asc()).limit(1)
            next_res = await db.execute(next_stmt)
            next_auction = next_res.scalar_one_or_none()
            
            if next_auction:
                next_auction.status = "ACTIVE"
                next_auction.expires_at = datetime.utcnow() + timedelta(minutes=5)
                await db.commit()
                
                caption, media_type, media_value = await get_auction_card(db, next_auction)
                kb = get_auction_keyboard(next_auction.id, next_auction.seller_id)
                
                try:
                    if media_type == "video":
                        auc_msg = await message.bot.send_video(
                            chat_id=next_auction.channel_chat_id,
                            video=media_value,
                            caption=caption,
                            reply_markup=kb.as_markup(),
                            parse_mode="HTML"
                        )
                    elif media_type == "animation":
                        auc_msg = await message.bot.send_animation(
                            chat_id=next_auction.channel_chat_id,
                            animation=media_value,
                            caption=caption,
                            reply_markup=kb.as_markup(),
                            parse_mode="HTML"
                        )
                    else:
                        auc_msg = await message.bot.send_photo(
                            chat_id=next_auction.channel_chat_id,
                            photo=media_value,
                            caption=caption,
                            reply_markup=kb.as_markup(),
                            parse_mode="HTML"
                        )
                    
                    next_auction.channel_message_id = auc_msg.message_id
                    await db.commit()
                    
                    try:
                        await message.bot.pin_chat_message(chat_id=next_auction.channel_chat_id, message_id=auc_msg.message_id)
                    except Exception:
                        pass

                    try:
                        stmt_p = select(Pokemon.name).where(Pokemon.id == next_auction.pokemon_id)
                        res_p = await db.execute(stmt_p)
                        p_name = res_p.scalar() or "Pokémon"
                        await message.bot.send_message(
                            chat_id=next_auction.seller_id,
                            text=f"🔔 <b>Your Queued Auction is LIVE!</b> 🔔\n"
                                 f"───────────────\n"
                                 f"Auction <b>#{next_auction.id:03d}</b> for <b>{p_name.title()}</b> (Pokédex #{next_auction.pokemon_id}) is now active!",
                            parse_mode="HTML"
                        )
                    except Exception:
                        pass
                except Exception as post_err:
                    print(f"⚠️ Failed to post activated queued auction {next_auction.id}: {post_err}")
        except Exception as queue_err:
            print(f"⚠️ Failed to process next queued auction after manual cancel: {queue_err}")


@router.message(Command("au"))
async def cmd_toggle_auctions(message: Message, db: AsyncSession):
    if message.from_user.id not in config.ADMIN_IDS:
        await message.answer("❌ Denied. Only Bot Owners can run this command.")
        return
        
    parts = message.text.split()
    if len(parts) < 2 or parts[1].lower() not in {"on", "off"}:
        await message.answer("⚠️ Usage: <code>/au &lt;on/off&gt;</code>", parse_mode="HTML")
        return
        
    val = parts[1].lower()
    
    from database.models import GlobalSetting
    stmt = select(GlobalSetting).where(GlobalSetting.key == "auctions_enabled")
    res = await db.execute(stmt)
    setting = res.scalar_one_or_none()
    if setting:
        setting.value = val
    else:
        db.add(GlobalSetting(key="auctions_enabled", value=val))
    await db.commit()
    
    from utils.settings import global_settings_cache
    global_settings_cache["auctions_enabled"] = val
    
    await message.answer(f"✅ Globally toggled auctions: <b>{val.upper()}</b>", parse_mode="HTML")


async def auction_settlement_worker(bot: Bot):
    """Ultra-fast background settlement loop running every 2 seconds to settle expired auctions instantly."""
    from database.database import SessionLocal
    from database.models import Auction, AuctionBid, User, UserPokemon, Pokemon
    
    print("⏳ Fast Auction Settlement Worker Loop Started (2s polling)...")
    while True:
        try:
            await asyncio.sleep(2)
            async with SessionLocal() as db:
                now = datetime.utcnow()
                stmt = select(Auction).where(Auction.status == "ACTIVE", Auction.expires_at <= now)
                res = await db.execute(stmt)
                expired_auctions = res.scalars().all()
                
                for auction in expired_auctions:
                    try:
                        stmt_bids = (
                            select(AuctionBid, User)
                            .join(User, AuctionBid.bidder_id == User.id)
                            .where(AuctionBid.auction_id == auction.id)
                            .order_by(AuctionBid.amount.desc())
                            .limit(1)
                        )
                        bids_res = await db.execute(stmt_bids)
                        highest_bid_data = bids_res.all()
                        
                        stmt_poke = select(Pokemon).where(Pokemon.id == auction.pokemon_id)
                        res_poke = await db.execute(stmt_poke)
                        pokemon = res_poke.scalar_one()

                        stmt_seller = select(User).where(User.id == auction.seller_id)
                        res_seller = await db.execute(stmt_seller)
                        seller = res_seller.scalar_one()
                        seller_name = seller.nickname or seller.username or f"Trainer {seller.id}"

                        if highest_bid_data:
                            highest_bid_rec, bidder_user = highest_bid_data[0]
                            winner_name = bidder_user.nickname or bidder_user.username or f"Trainer {bidder_user.id}"
                            
                            new_poke = UserPokemon(
                                user_id=bidder_user.id,
                                pokemon_id=auction.pokemon_id,
                                nickname=auction.nickname,
                                is_shiny=auction.is_shiny,
                                is_amv=auction.is_amv,
                                form_index=auction.form_index,
                                serial_number=auction.serial_number,
                                level=auction.level,
                                xp=auction.xp,
                                iv_hp=auction.iv_hp,
                                iv_atk=auction.iv_atk,
                                iv_def=auction.iv_def,
                                iv_spd=auction.iv_spd
                            )
                            db.add(new_poke)

                            tax = int(highest_bid_rec.amount * 0.05)
                            payout = highest_bid_rec.amount - tax
                            seller.coins += payout
                            db.add(seller)
                            
                            auction.status = "COMPLETED"
                            await db.commit()

                            won_caption = (
                                f"🎉 <b>Auction Won!</b> 🎉\n"
                                f"───────────────\n"
                                f"<blockquote>👑 <b>{html.escape(winner_name)}</b> won Auction #{auction.id:03d}!\n"
                                f"🙇 <b>{pokemon.name.title()}</b> (Pokédex #{pokemon.id}) added to collection\n"
                                f"💰 Winning Bid: <b>{highest_bid_rec.amount:,} coins</b>\n"
                                f"💰 Seller <b>{html.escape(seller_name)}</b> received <b>{payout:,} coins</b> (5% tax deducted)\n"
                                f"🎉 Congratulations!</blockquote>"
                            )
                            
                            if auction.channel_chat_id:
                                try:
                                    await bot.send_message(chat_id=auction.channel_chat_id, text=won_caption, parse_mode="HTML")
                                except Exception as err:
                                    print(f"⚠️ Failed to send auction win announcement: {err}")
                                     
                                if auction.channel_message_id:
                                    try:
                                        await bot.unpin_chat_message(chat_id=auction.channel_chat_id, message_id=auction.channel_message_id)
                                    except Exception:
                                        pass

                            await send_auction_settlement_channel_report(bot, db, auction, "COMPLETED")
                                        
                            seller_dm = (
                                f"🔔 <b>Auction Sold!</b> 🔔\n"
                                f"───────────────\n"
                                f"<blockquote>👑 Your <b>{pokemon.name.title()}</b> (Pokédex #{pokemon.id}) has been sold to <b>{html.escape(winner_name)}</b>!\n"
                                f"💰 Payout: <b>{payout:,} coins</b> (5% tax deducted)\n"
                                f"🎫 Serial: <code>{auction.serial_number}</code></blockquote>"
                            )
                            try:
                                await bot.send_message(chat_id=auction.seller_id, text=seller_dm, parse_mode="HTML")
                            except Exception as dm_err:
                                print(f"⚠️ Failed to DM seller {auction.seller_id} on auction sale: {dm_err}")

                            buyer_dm = (
                                f"🔔 <b>Auction Won!</b> 🔔\n"
                                f"───────────────\n"
                                f"<blockquote>👑 You won the auction for <b>{pokemon.name.title()}</b> (Pokédex #{pokemon.id})!\n"
                                f"💰 Amount Paid: <b>{highest_bid_rec.amount:,} coins</b>\n"
                                f"🎫 Serial: <code>{auction.serial_number}</code>\n"
                                f"🙇 Added to your collection bag.</blockquote>"
                            )
                            try:
                                await bot.send_message(chat_id=bidder_user.id, text=buyer_dm, parse_mode="HTML")
                            except Exception as dm_err:
                                print(f"⚠️ Failed to DM buyer {bidder_user.id} on auction win: {dm_err}")

                        else:
                            restored = UserPokemon(
                                user_id=auction.seller_id,
                                pokemon_id=auction.pokemon_id,
                                nickname=auction.nickname,
                                is_shiny=auction.is_shiny,
                                is_amv=auction.is_amv,
                                form_index=auction.form_index,
                                serial_number=auction.serial_number,
                                level=auction.level,
                                xp=auction.xp,
                                iv_hp=auction.iv_hp,
                                iv_atk=auction.iv_atk,
                                iv_def=auction.iv_def,
                                iv_spd=auction.iv_spd
                            )
                            db.add(restored)
                            auction.status = "CANCELLED"
                            await db.commit()

                            unsold_caption = (
                                f"🪙 <b>Auction Ended — No Bids</b>\n"
                                f"───────────────\n"
                                f"<blockquote>📛 <b>{pokemon.name.title()}</b> (Pokédex #{pokemon.id}) went unsold.\n"
                                f"🔄 Pokémon returned to <b>{html.escape(seller_name)}</b></blockquote>"
                            )
                            if auction.channel_chat_id:
                                try:
                                    await bot.send_message(chat_id=auction.channel_chat_id, text=unsold_caption, parse_mode="HTML")
                                except Exception as err:
                                    print(f"⚠️ Failed to send unsold announcement: {err}")
                                     
                                if auction.channel_message_id:
                                    try:
                                        await bot.unpin_chat_message(chat_id=auction.channel_chat_id, message_id=auction.channel_message_id)
                                    except Exception:
                                        pass

                            await send_auction_settlement_channel_report(bot, db, auction, "UNSOLD")
                                        
                            seller_dm = (
                                f"🔔 <b>Auction Ended — No Bids</b> 🔔\n"
                                f"───────────────\n"
                                f"<blockquote>📛 Your auction for <b>{pokemon.name.title()}</b> (Pokédex #{pokemon.id}) has ended with no bids.\n"
                                f"🔄 The Pokémon has been returned to your inventory.\n"
                                f"🎫 Serial: <code>{auction.serial_number}</code></blockquote>"
                            )
                            try:
                                await bot.send_message(chat_id=auction.seller_id, text=seller_dm, parse_mode="HTML")
                            except Exception as dm_err:
                                print(f"⚠️ Failed to DM seller {auction.seller_id} on unsold auction: {dm_err}")
                                        
                        if auction.channel_chat_id and auction.channel_message_id:
                            caption, media_type, media_value = await get_auction_card(db, auction)
                            try:
                                await bot.edit_message_caption(
                                    chat_id=auction.channel_chat_id,
                                    message_id=auction.channel_message_id,
                                    caption=caption,
                                    reply_markup=None,
                                    parse_mode="HTML"
                                )
                            except Exception as edit_err:
                                print(f"⚠️ Failed to update original auction card to ended: {edit_err}")
                                
                    except Exception as single_auc_err:
                        print(f"⚠️ Error settling auction {auction.id}: {single_auc_err}")
                    
                    try:
                        next_stmt = select(Auction).where(Auction.status == "PENDING").order_by(Auction.created_at.asc()).limit(1)
                        next_res = await db.execute(next_stmt)
                        next_auction = next_res.scalar_one_or_none()
                        
                        if next_auction:
                            next_auction.status = "ACTIVE"
                            next_auction.expires_at = datetime.utcnow() + timedelta(minutes=5)
                            await db.commit()
                            
                            caption, media_type, media_value = await get_auction_card(db, next_auction)
                            kb = get_auction_keyboard(next_auction.id, next_auction.seller_id)
                            
                            try:
                                if media_type == "video":
                                    auc_msg = await bot.send_video(
                                        chat_id=next_auction.channel_chat_id,
                                        video=media_value,
                                        caption=caption,
                                        reply_markup=kb.as_markup(),
                                        parse_mode="HTML"
                                    )
                                elif media_type == "animation":
                                    auc_msg = await bot.send_animation(
                                        chat_id=next_auction.channel_chat_id,
                                        animation=media_value,
                                        caption=caption,
                                        reply_markup=kb.as_markup(),
                                        parse_mode="HTML"
                                    )
                                else:
                                    auc_msg = await bot.send_photo(
                                        chat_id=next_auction.channel_chat_id,
                                        photo=media_value,
                                        caption=caption,
                                        reply_markup=kb.as_markup(),
                                        parse_mode="HTML"
                                    )
                                
                                next_auction.channel_message_id = auc_msg.message_id
                                await db.commit()
                                
                                try:
                                    await bot.pin_chat_message(chat_id=next_auction.channel_chat_id, message_id=auc_msg.message_id)
                                except Exception:
                                    pass

                                try:
                                    stmt_p = select(Pokemon.name).where(Pokemon.id == next_auction.pokemon_id)
                                    res_p = await db.execute(stmt_p)
                                    p_name = res_p.scalar() or "Pokémon"
                                    await bot.send_message(
                                        chat_id=next_auction.seller_id,
                                        text=f"🔔 <b>Your Queued Auction is LIVE!</b> 🔔\n"
                                             f"───────────────\n"
                                             f"Auction <b>#{next_auction.id:03d}</b> for <b>{p_name.title()}</b> (Pokédex #{next_auction.pokemon_id}) is now active!",
                                        parse_mode="HTML"
                                    )
                                except Exception:
                                    pass

                            except Exception as post_err:
                                print(f"⚠️ Failed to post activated queued auction {next_auction.id}: {post_err}")
                    except Exception as queue_err:
                        print(f"⚠️ Failed to process next queued auction: {queue_err}")
                        
        except Exception as loop_err:
            print(f"⚠️ Auction settlement loop error: {loop_err}")
