import html
import random
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
import config
from database.models import User, Pokemon, UserPokemon
from utils.formatters import get_rarity_emoji, escape_md
from keyboards.inline import create_styled_button

router = Router()

@router.message(Command("pay"))
async def cmd_pay(message: Message, db: AsyncSession):
    parts = message.text.split()
    sender_id = message.from_user.id
    target_user = None
    amount = 0
    
    # 1. Parse arguments based on message type
    if message.reply_to_message:
        # Format: /pay <amount>
        if len(parts) < 2 or not parts[1].isdigit():
            await message.answer("⚠️ Format: Reply to a user's message with <code>/pay &lt;amount&gt;</code>", parse_mode="HTML")
            return
        amount = int(parts[1])
        target_tg_user = message.reply_to_message.from_user
        target_id = target_tg_user.id
        
        if target_id == sender_id:
            await message.answer("❌ You cannot transfer coins to yourself!", parse_mode="HTML")
            return
            
        # Ensure target user is registered
        user_stmt = select(User).where(User.id == target_id)
        user_res = await db.execute(user_stmt)
        target_user = user_res.scalar_one_or_none()
        if not target_user:
            target_user = User(
                id=target_id,
                username=target_tg_user.username,
                nickname=target_tg_user.first_name
            )
            db.add(target_user)
            await db.flush()
    else:
        # Format: /pay <@username/user_id> <amount>
        if len(parts) < 3:
            await message.answer("⚠️ Format: <code>/pay &lt;@username/user_id&gt; &lt;amount&gt;</code> (or reply to their message with <code>/pay &lt;amount&gt;</code>)", parse_mode="HTML")
            return
            
        target_str = parts[1]
        amount_str = parts[2]
        
        if not amount_str.isdigit():
            await message.answer("⚠️ Amount must be a positive integer.", parse_mode="HTML")
            return
        amount = int(amount_str)
        
        if target_str.isdigit():
            target_id = int(target_str)
            if target_id == sender_id:
                await message.answer("❌ You cannot transfer coins to yourself!", parse_mode="HTML")
                return
            user_stmt = select(User).where(User.id == target_id)
            user_res = await db.execute(user_stmt)
            target_user = user_res.scalar_one_or_none()
            if not target_user:
                try:
                    chat = await message.bot.get_chat(target_id)
                    target_user = User(
                        id=target_id,
                        username=chat.username,
                        nickname=chat.first_name
                    )
                    db.add(target_user)
                    await db.flush()
                except Exception:
                    await message.answer(f"❌ User ID {target_id} is not registered and couldn't be resolved.", parse_mode="HTML")
                    return
        elif target_str.startswith("@"):
            username = target_str.replace("@", "").strip()
            user_stmt = select(User).where(User.username.ilike(username))
            user_res = await db.execute(user_stmt)
            target_user = user_res.scalar_one_or_none()
            if not target_user:
                await message.answer(f"❌ User with username @{username} not found in database.", parse_mode="HTML")
                return
            if target_user.id == sender_id:
                await message.answer("❌ You cannot transfer coins to yourself!", parse_mode="HTML")
                return
        else:
            await message.answer("⚠️ Target must be a user ID or @username.", parse_mode="HTML")
            return

    if amount <= 0:
        await message.answer("⚠️ Amount must be greater than zero.", parse_mode="HTML")
        return

    # Check/Register sender
    sender_stmt = select(User).where(User.id == sender_id)
    sender_res = await db.execute(sender_stmt)
    sender_user = sender_res.scalar_one_or_none()
    if not sender_user:
        sender_user = User(
            id=sender_id,
            username=message.from_user.username,
            nickname=message.from_user.first_name
        )
        db.add(sender_user)
        await db.flush()

    if sender_user.coins < amount:
        await message.answer(f"❌ Transaction failed. You don't have enough coins! (Balance: 💰 <code>{sender_user.coins:,} coins</code>)", parse_mode="HTML")
        return

    # Transfer coins
    sender_user.coins -= amount
    target_user.coins += amount
    try:
        from utils.trainer_level import log_transaction
        await log_transaction(sender_user.id, -amount, "Transfer", f"Transferred to {target_user.nickname or 'Trainer'}", db)
        await log_transaction(target_user.id, amount, "Transfer", f"Received from {sender_user.nickname or 'Trainer'}", db)
    except Exception:
        pass
    await db.commit()

    text = (
        f"💸 <b>COINS TRANSFERRED</b> 💸\n"
        f"◈ ────────────────── ◈\n"
        f"Trainer <b>{html.escape(sender_user.nickname or 'Trainer')}</b> sent coins to Trainer <b>{html.escape(target_user.nickname or 'Trainer')}</b>:\n"
        f"💰 <b>-{amount:,} coins</b> ➡️ 💰 <code>+{amount:,} coins</code>\n\n"
        f"👤 <b>Sender Balance:</b> <code>💰 {sender_user.coins:,} coins</code>\n"
        f"👤 <b>Recipient Balance:</b> <code>💰 {target_user.coins:,} coins</code>\n"
        f"◈ ────────────────── ◈"
    )
    await message.answer(text, parse_mode="HTML")


@router.message(Command("trade"))
async def cmd_trade(message: Message, db: AsyncSession):
    parts = message.text.split()
    sender_id = message.from_user.id
    target_tg_user = None
    my_pokedex_id = None
    their_pokedex_id = None
    
    # 1. Parse arguments based on message context
    if message.reply_to_message:
        target_tg_user = message.reply_to_message.from_user
        if len(parts) < 2 or not parts[1].isdigit():
            await message.answer(
                "⚠️ <b>Trade Format Error</b>\n\n"
                "When replying to a message, type:\n"
                "• <code>/trade &lt;your_pokedex_id&gt;</code> (to send a Pokémon)\n"
                "• <code>/trade &lt;your_pokedex_id&gt; &lt;their_pokedex_id&gt;</code> (to swap Pokémon)",
                parse_mode="HTML"
            )
            return
        my_pokedex_id = int(parts[1])
        if len(parts) > 2 and parts[2].isdigit():
            their_pokedex_id = int(parts[2])
    else:
        # Syntax: /trade @username <pokedex_id> [their_pokedex_id]
        if len(parts) < 3:
            # If user typed `/trade <pokedex_id>` without replying to anyone
            if len(parts) == 2 and parts[1].isdigit():
                await message.answer(
                    "⚠️ <b>Missing Trade Partner</b>\n\n"
                    "To trade a Pokémon, you must either:\n"
                    "1️⃣ <b>Reply</b> to a user's message with <code>/trade " + parts[1] + "</code>\n"
                    "2️⃣ <b>Specify</b> target user: <code>/trade @username " + parts[1] + "</code>",
                    parse_mode="HTML"
                )
                return
            await message.answer(
                "⚠️ <b>Usage Format for /trade</b>\n\n"
                "• <b>Reply to a user:</b> <code>/trade &lt;your_pokedex_id&gt; [their_pokedex_id]</code>\n"
                "• <b>Specify user:</b> <code>/trade @username &lt;your_pokedex_id&gt; [their_pokedex_id]</code>",
                parse_mode="HTML"
            )
            return

        target_str = parts[1]
        if not parts[2].isdigit():
            await message.answer("⚠️ Pokédex number must be a valid numeric ID (e.g. <code>/trade @username 150</code>).", parse_mode="HTML")
            return
        my_pokedex_id = int(parts[2])
        if len(parts) > 3 and parts[3].isdigit():
            their_pokedex_id = int(parts[3])

        if target_str.isdigit():
            t_id = int(target_str)
            try:
                chat = await message.bot.get_chat(t_id)
                target_tg_user = chat
            except Exception:
                user_stmt = select(User).where(User.id == t_id)
                user_res = await db.execute(user_stmt)
                db_user = user_res.scalar_one_or_none()
                if db_user:
                    class TempUser:
                        def __init__(self, id, first_name, username):
                            self.id = id
                            self.first_name = first_name
                            self.username = username
                    target_tg_user = TempUser(db_user.id, db_user.nickname, db_user.username)
                else:
                    await message.answer(f"❌ User ID {t_id} is not registered in the database.", parse_mode="HTML")
                    return
        elif target_str.startswith("@"):
            username = target_str.replace("@", "").strip()
            user_stmt = select(User).where(User.username.ilike(username))
            user_res = await db.execute(user_stmt)
            db_user = user_res.scalar_one_or_none()
            if not db_user:
                await message.answer(f"❌ User with username @{username} not found in database.", parse_mode="HTML")
                return
            class TempUser:
                def __init__(self, id, first_name, username):
                    self.id = id
                    self.first_name = first_name
                    self.username = username
            target_tg_user = TempUser(db_user.id, db_user.nickname, db_user.username)
        else:
            await message.answer("⚠️ Target must be a user ID or @username.", parse_mode="HTML")
            return

    target_id = target_tg_user.id
    if target_id == sender_id:
        await message.answer("❌ You cannot trade with yourself!", parse_mode="HTML")
        return

    # Check/Register sender
    sender_stmt = select(User).where(User.id == sender_id)
    sender_res = await db.execute(sender_stmt)
    sender_user = sender_res.scalar_one_or_none()
    if not sender_user:
        sender_user = User(id=sender_id, username=message.from_user.username, nickname=message.from_user.first_name)
        db.add(sender_user)
        await db.flush()

    # Check/Register target
    target_stmt = select(User).where(User.id == target_id)
    target_res = await db.execute(target_stmt)
    target_user = target_res.scalar_one_or_none()
    if not target_user:
        target_user = User(id=target_id, username=getattr(target_tg_user, "username", None), nickname=getattr(target_tg_user, "first_name", "Trainer"))
        db.add(target_user)
        await db.flush()

    # 2. Query Proposer's Pokémon (match by Pokédex ID or unique caught instance ID)
    my_poke_stmt = (
        select(UserPokemon, Pokemon)
        .join(Pokemon, UserPokemon.pokemon_id == Pokemon.id)
        .where(
            UserPokemon.user_id == sender_id,
            or_(UserPokemon.pokemon_id == my_pokedex_id, UserPokemon.id == my_pokedex_id)
        )
        .order_by(UserPokemon.level.desc())
        .limit(1)
    )
    my_poke_res = await db.execute(my_poke_stmt)
    my_pair = my_poke_res.first()
    
    if not my_pair:
        await message.answer(
            f"❌ <b>You don't have this Pokémon!</b>\n\n"
            f"You do not own any Pokémon with Pokédex number/ID <code>#{my_pokedex_id}</code> in your collection.\n"
            f"Catch or acquire it first before initiating a trade.",
            parse_mode="HTML"
        )
        return
    my_up, my_p = my_pair

    # 3. Query Partner's Pokémon (if swap)
    their_up, their_p = None, None
    if their_pokedex_id is not None:
        their_poke_stmt = (
            select(UserPokemon, Pokemon)
            .join(Pokemon, UserPokemon.pokemon_id == Pokemon.id)
            .where(
                UserPokemon.user_id == target_id,
                or_(UserPokemon.pokemon_id == their_pokedex_id, UserPokemon.id == their_pokedex_id)
            )
            .order_by(UserPokemon.level.desc())
            .limit(1)
        )
        their_poke_res = await db.execute(their_poke_stmt)
        their_pair = their_poke_res.first()
        if not their_pair:
            await message.answer(
                f"❌ <b>Partner missing Pokémon!</b>\n\n"
                f"Target Trainer <b>{html.escape(target_user.nickname or 'Trainer')}</b> does not own any Pokémon with Pokédex number/ID <code>#{their_pokedex_id}</code>.",
                parse_mode="HTML"
            )
            return
        their_up, their_p = their_pair

    # Form text representation
    my_shiny = "✨ Shiny " if my_up.is_shiny else ""
    my_rarity = get_rarity_emoji(my_p.rarity)
    my_iv_total = round((my_up.iv_hp + my_up.iv_atk + my_up.iv_def + my_up.iv_spd) / 124 * 100, 1)
    my_display = (
        f"{my_rarity} {my_shiny}<b>{html.escape(my_up.nickname or my_p.name.title())}</b> "
        f"<code>(Lvl {my_up.level} | IV: {my_iv_total}%)</code> [#{my_p.id}]"
    )

    if their_up and their_p:
        their_shiny = "✨ Shiny " if their_up.is_shiny else ""
        their_rarity = get_rarity_emoji(their_p.rarity)
        their_iv_total = round((their_up.iv_hp + their_up.iv_atk + their_up.iv_def + their_up.iv_spd) / 124 * 100, 1)
        their_display = (
            f"{their_rarity} {their_shiny}<b>{html.escape(their_up.nickname or their_p.name.title())}</b> "
            f"<code>(Lvl {their_up.level} | IV: {their_iv_total}%)</code> [#{their_p.id}]"
        )
    else:
        their_display = "🎁 <i>Gift / Free Transfer</i>"

    text = (
        f"🤝 <b>POKÉMON TRADE PROPOSAL</b> 🤝\n"
        f"◈ ────────────────── ◈\n"
        f"👤 <b>Proposer:</b> Trainer <b>{html.escape(sender_user.nickname or 'Trainer')}</b>\n"
        f"👉 <b>Offering:</b> {my_display}\n\n"
        f"👤 <b>Trade Partner:</b> Trainer <b>{html.escape(target_user.nickname or 'Trainer')}</b>\n"
        f"👉 <b>Requesting:</b> {their_display}\n"
        f"◈ ────────────────── ◈\n"
        f"⏳ <i>Waiting for Trainer <b>{html.escape(target_user.nickname or 'Trainer')}</b> to respond...</i>"
    )

    builder = InlineKeyboardBuilder()
    their_upid_val = their_up.id if their_up else 0
    callback_accept = f"t_acc_{sender_id}_{target_id}_{my_up.id}_{their_upid_val}"
    callback_decline = f"t_dec_{sender_id}_{target_id}_{my_up.id}_{their_upid_val}"

    builder.row(
        create_styled_button(text="✅ Accept Trade", key="confirm", style="success", callback_data=callback_accept),
        create_styled_button(text="❌ Decline Trade", key="cancel", style="danger", callback_data=callback_decline)
    )

    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@router.callback_query(F.data.startswith("t_acc_"))
async def cb_trade_accept(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    proposer_id = int(parts[2])
    target_id = int(parts[3])
    my_upid = int(parts[4])
    their_upid = int(parts[5])

    # Only target user can accept
    if callback.from_user.id != target_id:
        await callback.answer("❌ Only the designated trade partner can accept this trade!", show_alert=True)
        return

    # Fetch players
    p_stmt = select(User).where(User.id == proposer_id)
    p_res = await db.execute(p_stmt)
    proposer = p_res.scalar_one_or_none()

    t_stmt = select(User).where(User.id == target_id)
    t_res = await db.execute(t_stmt)
    target = t_res.scalar_one_or_none()

    if not proposer or not target:
        await callback.answer("❌ Error: One of the trainers is no longer registered.", show_alert=True)
        return

    # Verify Proposer still owns this specific Pokémon instance
    my_poke_stmt = select(UserPokemon, Pokemon).join(Pokemon, UserPokemon.pokemon_id == Pokemon.id).where(UserPokemon.id == my_upid).limit(1)
    my_poke_res = await db.execute(my_poke_stmt)
    my_pair = my_poke_res.first()

    if not my_pair or my_pair[0].user_id != proposer_id:
        await callback.answer("❌ Trade failed! Offering Pokémon is no longer owned by Proposer.", show_alert=True)
        await callback.message.edit_text("❌ <b>TRADE FAILED</b>: Offering Pokémon is no longer owned by Proposer.", parse_mode="HTML")
        return
    my_up, my_p = my_pair

    # Verify Target still owns their specific Pokémon instance (if swap)
    their_up, their_p = None, None
    if their_upid > 0:
        their_poke_stmt = select(UserPokemon, Pokemon).join(Pokemon, UserPokemon.pokemon_id == Pokemon.id).where(UserPokemon.id == their_upid).limit(1)
        their_poke_res = await db.execute(their_poke_stmt)
        their_pair = their_poke_res.first()

        if not their_pair or their_pair[0].user_id != target_id:
            await callback.answer("❌ Trade failed! Partner no longer owns the requested Pokémon.", show_alert=True)
            await callback.message.edit_text("❌ <b>TRADE FAILED</b>: Requested Pokémon is no longer owned by Partner.", parse_mode="HTML")
            return
        their_up, their_p = their_pair

    # Perform trade ownership swap
    my_up.user_id = target_id
    if their_up:
        their_up.user_id = proposer_id

    await db.commit()

    my_shiny = "✨ Shiny " if my_up.is_shiny else ""
    my_rarity = get_rarity_emoji(my_p.rarity)
    my_name = f"{my_rarity} {my_shiny}<b>{html.escape(my_up.nickname or my_p.name.title())}</b>"

    if their_up and their_p:
        their_shiny = "✨ Shiny " if their_up.is_shiny else ""
        their_rarity = get_rarity_emoji(their_p.rarity)
        their_name = f"{their_rarity} {their_shiny}<b>{html.escape(their_up.nickname or their_p.name.title())}</b>"
        
        success_text = (
            f"✅ <b>TRADE COMPLETED SUCCESSFULLY</b> ✅\n"
            f"◈ ────────────────── ◈\n"
            f"🔄 <b>Exchange Summary:</b>\n\n"
            f"👤 Trainer <b>{html.escape(proposer.nickname or 'Trainer')}</b> received:\n"
            f"👉 {their_name} <code>(Lvl {their_up.level})</code>\n\n"
            f"👤 Trainer <b>{html.escape(target.nickname or 'Trainer')}</b> received:\n"
            f"👉 {my_name} <code>(Lvl {my_up.level})</code>\n"
            f"◈ ────────────────── ◈\n"
            f"🎉 <i>Congratulations on your new Pokémon!</i>"
        )
    else:
        success_text = (
            f"🎁 <b>GIFT COMPLETED SUCCESSFULLY</b> 🎁\n"
            f"◈ ────────────────── ◈\n"
            f"👤 Trainer <b>{html.escape(target.nickname or 'Trainer')}</b> received:\n"
            f"👉 {my_name} <code>(Lvl {my_up.level})</code> as a gift from <b>{html.escape(proposer.nickname or 'Trainer')}</b>!\n"
            f"◈ ────────────────── ◈"
        )

    await callback.message.edit_text(success_text, parse_mode="HTML")
    await callback.answer("🎉 Trade completed!")


@router.callback_query(F.data.startswith("t_dec_"))
async def cb_trade_decline(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    proposer_id = int(parts[2])
    target_id = int(parts[3])
    user_clicking = callback.from_user.id

    if user_clicking not in [proposer_id, target_id]:
        await callback.answer("❌ Only participants of this trade can cancel/decline it!", show_alert=True)
        return

    # Fetch players
    p_stmt = select(User).where(User.id == proposer_id)
    p_res = await db.execute(p_stmt)
    proposer = p_res.scalar_one_or_none()

    t_stmt = select(User).where(User.id == target_id)
    t_res = await db.execute(t_stmt)
    target = t_res.scalar_one_or_none()

    proposer_name = html.escape(proposer.nickname or "Proposer") if proposer else "Proposer"
    target_name = html.escape(target.nickname or "Partner") if target else "Partner"

    if user_clicking == proposer_id:
        cancel_text = (
            f"❌ <b>TRADE CANCELLED</b> ❌\n"
            f"◈ ────────────────── ◈\n"
            f"Trainer <b>{proposer_name}</b> cancelled their trade proposal.\n"
            f"◈ ────────────────── ◈"
        )
        await callback.message.edit_text(cancel_text, parse_mode="HTML")
        await callback.answer("Trade Cancelled!")
    else:
        decline_text = (
            f"❌ <b>TRADE DECLINED</b> ❌\n"
            f"◈ ────────────────── ◈\n"
            f"Trainer <b>{target_name}</b> declined the trade proposal from <b>{proposer_name}</b>.\n"
            f"◈ ────────────────── ◈"
        )
        await callback.message.edit_text(decline_text, parse_mode="HTML")
        await callback.answer("Trade Declined!")
