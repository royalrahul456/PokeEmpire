from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import config
import html
import asyncio
from datetime import datetime, timedelta
from database.models import User, Pokemon, UserPokemon, Auction, AuctionBid
from utils.formatters import get_rarity_emoji
from utils.settings import get_custom_rarity_forms, get_all_custom_rarities
from handlers.admin import get_single_form_media_value, parse_stored_media_value

router = Router()
active_custom_bids = {}  # user_id -> (auction_id, prompt_message_id)

async def get_auction_card(db: AsyncSession, auction: Auction) -> tuple[str, str, str | None]:
    """Generates the text caption, media type and media value for an auction card."""
    # Resolve Pokemon details
    stmt = select(Pokemon).where(Pokemon.id == auction.pokemon_id)
    res = await db.execute(stmt)
    pokemon = res.scalar_one()

    # Load custom rarities & dynamic forms
    custom_rarities = await get_all_custom_rarities(db)
    custom_forms = await get_custom_rarity_forms(db)
    
    r_emoji = get_rarity_emoji(pokemon.rarity, custom_rarities)
    
    # Resolve form name
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

    # Fetch seller
    stmt_seller = select(User).where(User.id == auction.seller_id)
    res_seller = await db.execute(stmt_seller)
    seller = res_seller.scalar_one()
    seller_name = seller.nickname or seller.username or f"Trainer {seller.id}"

    # Fetch highest bidder
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

    # Build bid history list (top 5 bids)
    recent_bids_text = ""
    if all_bids:
        bid_lines = []
        for bid_rec, bidder_user in all_bids[:5]:
            b_name = bidder_user.nickname or bidder_user.username or f"Trainer {bidder_user.id}"
            bid_time = bid_rec.bid_at.strftime("%H:%M:%S")
            bid_lines.append(f"├─ {html.escape(b_name)}: {bid_rec.amount:,} ({bid_time})")
        recent_bids_text = "\n" + "\n".join(bid_lines)
    else:
        recent_bids_text = "\n╰─ No bids placed yet"

    # Time remaining calculation
    time_left = auction.expires_at - datetime.utcnow()
    if time_left.total_seconds() <= 0:
        time_left_str = "Ended"
    else:
        hours, remainder = divmod(int(time_left.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)
        time_left_str = f"{hours}h {minutes}m"

    title_status = "🔮 ACTIVE AUCTION!" if auction.status == "ACTIVE" else "🔮 AUCTION ENDED!"

    caption = (
        f"{title_status}\n"
        f"───────────────\n"
        f"<blockquote>📛 <b>Name</b>: {pokemon.name.title()} ({form_label})\n"
        f"💎 <b>Rarity</b>: {r_emoji} {pokemon.rarity}\n"
        f"🔢 <b>Level</b>: {auction.level}\n"
        f"📊 <b>IVs</b>: {auction.iv_hp}/{auction.iv_atk}/{auction.iv_def}/{auction.iv_spd} (Total: {auction.iv_hp+auction.iv_atk+auction.iv_def+auction.iv_spd}/124)\n"
        f"🎫 <b>Serial Number</b>: <code>{auction.serial_number}</code>\n\n"
        f"💰 <b>Starting</b>: {auction.starting_price:,}\n"
        f"💣 <b>Current Bid</b>: {auction.current_bid:,}\n"
        f"👑 <b>Leader</b>: {html.escape(leader_name)}\n"
        f"👥 <b>Seller</b>: {html.escape(seller_name)}\n"
        f"⏳ <b>Time Left</b>: {time_left_str}</blockquote>\n\n"
        f"📝 <b>Recent Bids:</b>{recent_bids_text}"
    )

    # Resolve media
    media_value = pokemon.image_url
    media_type = "photo"
    
    resolved_form = auction.form_index
    if auction.is_shiny and auction.form_index == 0:
        resolved_form = 6  # Shiny form index

    if resolved_form > 0:
        form_media = await get_single_form_media_value(db, pokemon.id, resolved_form)
        if form_media:
            media_type, media_value = parse_stored_media_value(form_media)
    else:
        if pokemon.video_url:
            media_type = "video"
            media_value = pokemon.video_url

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

@router.message(Command("auction"))
async def cmd_create_auction(message: Message, db: AsyncSession):
    # Command: /auction <pokedex_id_or_name> <starting_price>
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer(
            "⚠️ <b>Usage:</b>\n"
            "<code>/auction &lt;Pokedex_ID_or_Name&gt; &lt;Starting_Price&gt;</code>\n\n"
            "Example: <code>/auction 6 10000</code> or <code>/auction charizard 10000</code>",
            parse_mode="HTML"
        )
        return

    poke_input = parts[1].strip()
    try:
        starting_price = int(parts[2].replace(",", ""))
    except ValueError:
        await message.answer("❌ Starting price must be a valid integer.")
        return

    if starting_price <= 0:
        await message.answer("❌ Starting price must be greater than 0.")
        return

    # Resolve Pokemon ID
    if poke_input.isdigit():
        stmt_poke = select(Pokemon).where(Pokemon.id == int(poke_input))
    else:
        stmt_poke = select(Pokemon).where(Pokemon.name.ilike(poke_input))
    
    res_poke = await db.execute(stmt_poke)
    pokemon = res_poke.scalar_one_or_none()
    if not pokemon:
        await message.answer(f"❌ Pokémon '{poke_input}' not found in database.")
        return

    stmt = (
        select(UserPokemon)
        .where(
            UserPokemon.user_id == message.from_user.id,
            UserPokemon.pokemon_id == pokemon.id,
            UserPokemon.form_index == 0
        )
        .order_by(UserPokemon.level.desc(), UserPokemon.id.asc())
        .limit(1)
    )
    res = await db.execute(stmt)
    user_poke = res.scalar_one_or_none()
    if not user_poke:
        await message.answer(f"❌ You don't own any <b>{pokemon.name.title()}</b> in your inventory.", parse_mode="HTML")
        return

    # Delete Pokémon from inventory
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

    # Create active auction entry (expires in 5 minutes)
    expires_at = datetime.utcnow() + timedelta(minutes=5)
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

    # Post auction card
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
        else:
            auc_msg = await message.bot.send_photo(
                chat_id=message.chat.id,
                photo=media_value,
                caption=caption,
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )

        # Save message references for editing later
        auction.channel_message_id = auc_msg.message_id
        auction.channel_chat_id = message.chat.id
        await db.commit()

        # Auto pin auction message in group chats
        if message.chat.type != "private":
            try:
                await message.bot.pin_chat_message(chat_id=message.chat.id, message_id=auc_msg.message_id)
            except Exception as pin_err:
                print(f"⚠️ Failed to pin auction message: {pin_err}")
                
    except Exception as e:
        # If sending fails, restore Pokémon back to the seller
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
    # Retrieve all active auctions
    stmt = select(Auction).where(Auction.status == "ACTIVE").order_by(Auction.expires_at.asc())
    res = await db.execute(stmt)
    auctions = res.scalars().all()

    if not auctions:
        await message.answer("🛒 No active auctions found at the moment.")
        return

    text = "🛒 <b>ACTIVE AUCTION LISTINGS</b> 🛒\n───────────────\n\n"
    for a in auctions:
        stmt_p = select(Pokemon.name).where(Pokemon.id == a.pokemon_id)
        res_p = await db.execute(stmt_p)
        p_name = res_p.scalar() or "Unknown"
        
        time_left = a.expires_at - datetime.utcnow()
        if time_left.total_seconds() <= 0:
            time_left_str = "Ended"
        else:
            hours, remainder = divmod(int(time_left.total_seconds()), 3600)
            minutes, _ = divmod(remainder, 60)
            time_left_str = f"{hours}h {minutes}m"

        text += (
            f"• <b>#{a.id:03d}</b> | <b>{p_name.title()}</b> (Lvl {a.level})\n"
            f"  └ 🎫 Serial: <code>{a.serial_number}</code> | 💰 Current Bid: <b>{a.current_bid:,} coins</b>\n"
            f"  └ ⏳ Time remaining: <code>{time_left_str}</code>\n\n"
        )

    text += "👉 Bid on any auction by clicking buttons on the auction card or using: `/bid <auction_id> <amount>`"
    await message.answer(text, parse_mode="HTML")

@router.message(Command("bid"))
async def cmd_bid_manual(message: Message, db: AsyncSession):
    # Command: /bid <auction_id> <amount>
    parts = message.text.split()
    if len(parts) < 3:
        await message.answer("⚠️ Usage: `/bid <auction_id> <amount>`")
        return

    try:
        auction_id = int(parts[1])
        bid_amount = int(parts[2])
    except ValueError:
        await message.answer("❌ Auction ID and bid amount must be valid integers.")
        return

    # Fetch auction
    stmt = select(Auction).where(Auction.id == auction_id, Auction.status == "ACTIVE")
    res = await db.execute(stmt)
    auction = res.scalar_one_or_none()
    if not auction:
        await message.answer("❌ Auction not found or already closed.")
        return

    # Check seller
    if auction.seller_id == message.from_user.id:
        await message.answer("❌ You cannot bid on your own auction!")
        return

    # Bid validation
    min_next_bid = auction.current_bid + 1
    if bid_amount < min_next_bid:
        await message.answer(f"❌ Your bid must be at least {min_next_bid:,} coins.")
        return

    # Check bidder balance
    stmt_bidder = select(User).where(User.id == message.from_user.id)
    res_bidder = await db.execute(stmt_bidder)
    bidder = res_bidder.scalar_one()
    if bidder.coins < bid_amount:
        await message.answer(f"❌ You do not have enough coins. Your balance: {bidder.coins:,} coins.")
        return

    # Refund previous highest bidder
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
        prev_user = res_prev_user.scalar_one()
        prev_user.coins += prev_highest_bid.amount
        db.add(prev_user)

    # Deduct new bid from bidder
    bidder.coins -= bid_amount
    db.add(bidder)

    # Add bid record
    new_bid = AuctionBid(
        auction_id=auction.id,
        bidder_id=message.from_user.id,
        amount=bid_amount
    )
    db.add(new_bid)

    # Update auction price
    auction.current_bid = bid_amount
    await db.commit()

    await message.answer(f"✅ Your bid of <b>{bid_amount:,} coins</b> has been successfully placed on auction #{auction.id:03d}!", parse_mode="HTML")

    # Update dynamic auction card in channel
    if auction.channel_chat_id and auction.channel_message_id:
        caption, media_type, media_value = await get_auction_card(db, auction)
        kb = get_auction_keyboard(auction.id, auction.seller_id)
        try:
            await message.bot.edit_message_caption(
                chat_id=auction.channel_chat_id,
                message_id=auction.channel_message_id,
                caption=caption,
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
        except Exception as edit_err:
            print(f"⚠️ Failed to edit auction card: {edit_err}")

@router.callback_query(F.data.startswith("auc_bid_"))
async def cb_auc_increment_bid(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    # auc_bid_<auction_id>_<increment>
    auction_id = int(parts[2])
    increment = int(parts[3])
    user_id = callback.from_user.id

    stmt = select(Auction).where(Auction.id == auction_id, Auction.status == "ACTIVE")
    res = await db.execute(stmt)
    auction = res.scalar_one_or_none()
    if not auction:
        await callback.answer("❌ Auction is no longer active.", show_alert=True)
        return

    if auction.seller_id == user_id:
        await callback.answer("❌ You cannot bid on your own auction!", show_alert=True)
        return

    bid_amount = auction.current_bid + increment

    # Check bidder balance
    stmt_bidder = select(User).where(User.id == user_id)
    res_bidder = await db.execute(stmt_bidder)
    bidder = res_bidder.scalar_one()
    if bidder.coins < bid_amount:
        await callback.answer(f"❌ Insufficient coins! Balance: {bidder.coins:,}", show_alert=True)
        return

    # Refund previous highest bidder
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
        prev_user = res_prev_user.scalar_one()
        prev_user.coins += prev_highest_bid.amount
        db.add(prev_user)

    # Deduct new bid from bidder
    bidder.coins -= bid_amount
    db.add(bidder)

    # Add bid record
    new_bid = AuctionBid(
        auction_id=auction.id,
        bidder_id=user_id,
        amount=bid_amount
    )
    db.add(new_bid)

    # Update auction price
    auction.current_bid = bid_amount
    await db.commit()

    await callback.answer(f"✅ Bid of {bid_amount:,} coins placed successfully!")

    # Update dynamic auction card in channel
    caption, media_type, media_value = await get_auction_card(db, auction)
    kb = get_auction_keyboard(auction.id, auction.seller_id)
    try:
        await callback.message.edit_caption(
            caption=caption,
            reply_markup=kb.as_markup(),
            parse_mode="HTML"
        )
    except Exception as edit_err:
        print(f"⚠️ Failed to edit auction card: {edit_err}")

@router.callback_query(F.data.startswith("auc_custom_"))
async def cb_auc_custom_bid(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    auction_id = int(parts[2])
    user_id = callback.from_user.id

    stmt = select(Auction).where(Auction.id == auction_id, Auction.status == "ACTIVE")
    res = await db.execute(stmt)
    auction = res.scalar_one_or_none()
    if not auction:
        await callback.answer("❌ Auction is no longer active.", show_alert=True)
        return

    if auction.seller_id == user_id:
        await callback.answer("❌ You cannot bid on your own auction!", show_alert=True)
        return

    # Send DM or instructions
    msg = await callback.message.answer(
        f"💬 <b>Custom Bid for Auction #{auction.id:03d}</b>\n"
        f"Reply to this message with your bid amount (must be greater than {auction.current_bid:,}):",
        parse_mode="HTML"
    )
    active_custom_bids[user_id] = (auction_id, msg.message_id)
    await callback.answer()

@router.message(F.reply_to_message)
async def process_custom_bid_reply(message: Message, db: AsyncSession):
    user_id = message.from_user.id
    if user_id not in active_custom_bids:
        return

    auction_id, prompt_msg_id = active_custom_bids[user_id]
    
    # Check if this reply is to the custom bid prompt
    if not message.reply_to_message or message.reply_to_message.message_id != prompt_msg_id:
        return

    active_custom_bids.pop(user_id, None)

    try:
        bid_amount = int(message.text.strip().replace(",", ""))
    except ValueError:
        await message.answer("❌ Invalid amount. Custom bid must be a valid integer.")
        return

    stmt = select(Auction).where(Auction.id == auction_id, Auction.status == "ACTIVE")
    res = await db.execute(stmt)
    auction = res.scalar_one_or_none()
    if not auction:
        await message.answer("❌ Auction is no longer active.")
        return

    min_next_bid = auction.current_bid + 1
    if bid_amount < min_next_bid:
        await message.answer(f"❌ Your custom bid must be at least {min_next_bid:,} coins.")
        return

    # Check bidder balance
    stmt_bidder = select(User).where(User.id == user_id)
    res_bidder = await db.execute(stmt_bidder)
    bidder = res_bidder.scalar_one()
    if bidder.coins < bid_amount:
        await message.answer(f"❌ Insufficient coins! Balance: {bidder.coins:,} coins.")
        return

    # Refund previous highest bidder
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
        prev_user = res_prev_user.scalar_one()
        prev_user.coins += prev_highest_bid.amount
        db.add(prev_user)

    # Deduct new bid from bidder
    bidder.coins -= bid_amount
    db.add(bidder)

    # Add bid record
    new_bid = AuctionBid(
        auction_id=auction.id,
        bidder_id=user_id,
        amount=bid_amount
    )
    db.add(new_bid)

    # Update auction price
    auction.current_bid = bid_amount
    await db.commit()

    await message.answer(f"✅ Custom bid of <b>{bid_amount:,} coins</b> placed successfully!", parse_mode="HTML")

    # Update dynamic auction card in channel
    if auction.channel_chat_id and auction.channel_message_id:
        caption, media_type, media_value = await get_auction_card(db, auction)
        kb = get_auction_keyboard(auction.id, auction.seller_id)
        try:
            await message.bot.edit_message_caption(
                chat_id=auction.channel_chat_id,
                message_id=auction.channel_message_id,
                caption=caption,
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
        except Exception as edit_err:
            print(f"⚠️ Failed to edit auction card: {edit_err}")

@router.message(Command("cancelauction"))
async def cmd_cancel_auction(message: Message, db: AsyncSession):
    # Command: /cancelauction <auction_id>
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("⚠️ Usage: `/cancelauction <auction_id>`")
        return

    try:
        auction_id = int(parts[1])
    except ValueError:
        await message.answer("❌ Invalid Auction ID.")
        return

    stmt = select(Auction).where(Auction.id == auction_id, Auction.status == "ACTIVE")
    res = await db.execute(stmt)
    auction = res.scalar_one_or_none()
    if not auction:
        await message.answer("❌ Auction not found or not active.")
        return

    if auction.seller_id != message.from_user.id:
        await message.answer("❌ You can only cancel your own auctions.")
        return

    # Check if bids exist
    stmt_bids = select(func.count(AuctionBid.id)).where(AuctionBid.auction_id == auction.id)
    res_bids = await db.execute(stmt_bids)
    bid_count = res_bids.scalar() or 0

    if bid_count > 0:
        await message.answer("❌ You cannot cancel this auction since active bids have already been placed.")
        return

    # Restore Pokémon to seller
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
    auction.status = "CANCELLED"
    await db.commit()

    # Unpin active message
    if auction.channel_chat_id and auction.channel_message_id:
        try:
            await message.bot.unpin_chat_message(chat_id=auction.channel_chat_id, message_id=auction.channel_message_id)
        except Exception:
            pass
            
        # Edit card to show Cancelled
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


async def auction_settlement_worker(bot: Bot):
    from database.database import SessionLocal
    from database.models import Auction, AuctionBid, User, UserPokemon, Pokemon
    
    print("⏳ Auction Settlement Worker Loop Started...")
    while True:
        try:
            await asyncio.sleep(30)
            async with SessionLocal() as db:
                # Find active auctions that have expired
                now = datetime.utcnow()
                stmt = select(Auction).where(Auction.status == "ACTIVE", Auction.expires_at <= now)
                res = await db.execute(stmt)
                expired_auctions = res.scalars().all()
                
                for auction in expired_auctions:
                    try:
                        # Fetch highest bid
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
                            
                            # 1. Award Pokémon to bidder
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

                            # 2. Pay seller (minus 5% system fee)
                            tax = int(highest_bid_rec.amount * 0.05)
                            payout = highest_bid_rec.amount - tax
                            seller.coins += payout
                            db.add(seller)
                            
                            auction.status = "COMPLETED"
                            await db.commit()

                            # 3. Announcement of Auction Won
                            won_caption = (
                                f"🎉 <b>Auction Won!</b> 🎉\n"
                                f"───────────────\n"
                                f"<blockquote>👑 <b>{html.escape(winner_name)}</b> won!\n"
                                f"🙇 <b>{pokemon.name.title()}</b> added to collection\n"
                                f"💰 Paid: <b>{highest_bid_rec.amount:,}</b>\n"
                                f"💰 Seller <b>{html.escape(seller_name)}</b> received <b>{payout:,} coins</b> (5% tax deducted)\n"
                                f"🎉 Congratulations!</blockquote>"
                            )
                            
                            # Send won card to the chat
                            if auction.channel_chat_id:
                                try:
                                    await bot.send_message(chat_id=auction.channel_chat_id, text=won_caption, parse_mode="HTML")
                                except Exception as err:
                                    print(f"⚠️ Failed to send auction win announcement: {err}")
                                    
                                # Unpin original message
                                if auction.channel_message_id:
                                    try:
                                        await bot.unpin_chat_message(chat_id=auction.channel_chat_id, message_id=auction.channel_message_id)
                                    except Exception:
                                        pass
                        else:
                            # Return Pokémon to seller
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

                            # Announcement of Unsold
                            unsold_caption = (
                                f"🪙 <b>Auction Ended — No Bids</b>\n"
                                f"───────────────\n"
                                f"<blockquote>📛 <b>{pokemon.name.title()}</b> went unsold.\n"
                                f"🔄 Pokémon returned to <b>{html.escape(seller_name)}</b></blockquote>"
                            )
                            if auction.channel_chat_id:
                                try:
                                    await bot.send_message(chat_id=auction.channel_chat_id, text=unsold_caption, parse_mode="HTML")
                                except Exception as err:
                                    print(f"⚠️ Failed to send unsold announcement: {err}")
                                    
                                # Unpin original message
                                if auction.channel_message_id:
                                    try:
                                        await bot.unpin_chat_message(chat_id=auction.channel_chat_id, message_id=auction.channel_message_id)
                                    except Exception:
                                        pass
                                        
                        # Update original active message (remove buttons, update text to ended)
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
                        
        except Exception as loop_err:
            print(f"⚠️ Auction settlement loop error: {loop_err}")
