import html
import random
import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
import config
from database.models import User, Pokemon, UserPokemon
from utils.formatters import get_rarity_emoji, escape_md
from keyboards.inline import create_styled_button, get_pay_confirm_keyboard

logger = logging.getLogger(__name__)
router = Router()


@router.message(Command("pay"))
async def cmd_pay(message: Message, db: AsyncSession):
    try:
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
            if not target_tg_user or target_tg_user.is_bot:
                await message.answer("❌ You cannot transfer coins to bots or anonymous senders!", parse_mode="HTML")
                return
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
                        await message.answer(f"❌ User ID <code>{target_id}</code> is not registered.", parse_mode="HTML")
                        return
            elif target_str.startswith("@"):
                username = target_str.lstrip("@").strip()
                user_stmt = select(User).where(func.lower(User.username) == func.lower(username))
                user_res = await db.execute(user_stmt)
                target_user = user_res.scalar_one_or_none()
                if not target_user:
                    await message.answer(f"❌ User with username @{html.escape(username)} not found in database.", parse_mode="HTML")
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

        # Show confirmation prompt with Green Accept and Red Decline buttons
        kb = get_pay_confirm_keyboard(sender_id, target_user.id, amount)
        sender_name = sender_user.nickname or message.from_user.first_name or "Trainer"
        target_name = target_user.nickname or target_user.username or "Trainer"

        text = (
            f"💳 <b>COIN TRANSFER CONFIRMATION</b>\n"
            f"◈ ────────────────── ◈\n"
            f"👤 <b>Sender:</b> {html.escape(sender_name)}\n"
            f"👤 <b>Recipient:</b> {html.escape(target_name)}\n"
            f"💰 <b>Amount:</b> <code>{amount:,} coins</code>\n\n"
            f"Are you sure you want to transfer <b>{amount:,} coins</b> to <b>{html.escape(target_name)}</b>?\n"
            f"◈ ────────────────── ◈"
        )
        await message.answer(text, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        logger.exception("Error in cmd_pay:")
        await message.answer("❌ An error occurred while processing coin transfer.", parse_mode="HTML")


@router.callback_query(F.data.startswith("pay_cnf_"))
async def cb_pay_confirm(callback: CallbackQuery, db: AsyncSession):
    try:
        parts = callback.data.split("_")
        sender_id = int(parts[2])
        target_id = int(parts[3])
        amount = int(parts[4])

        if callback.from_user.id != sender_id:
            await callback.answer("❌ Only the sender can confirm this transfer!", show_alert=True)
            return

        sender_stmt = select(User).where(User.id == sender_id)
        sender_res = await db.execute(sender_stmt)
        sender_user = sender_res.scalar_one_or_none()

        target_stmt = select(User).where(User.id == target_id)
        target_res = await db.execute(target_stmt)
        target_user = target_res.scalar_one_or_none()

        if not sender_user or not target_user:
            await callback.answer("❌ User data not found.", show_alert=True)
            return

        if sender_user.coins < amount:
            await callback.answer("❌ You don't have enough coins!", show_alert=True)
            try:
                await callback.message.edit_text(
                    f"❌ <b>Transfer Failed</b>: Insufficient coins (Balance: 💰 <code>{sender_user.coins:,} coins</code>).",
                    parse_mode="HTML"
                )
            except Exception:
                pass
            return

        # Perform transfer
        sender_user.coins -= amount
        target_user.coins += amount
        try:
            from utils.trainer_level import log_transaction
            await log_transaction(sender_user.id, -amount, "Transfer", f"Transferred to {target_user.nickname or 'Trainer'}", db)
            await log_transaction(target_user.id, amount, "Transfer", f"Received from {sender_user.nickname or 'Trainer'}", db)
        except Exception:
            pass
        await db.commit()

        sender_name = sender_user.nickname or "Trainer"
        target_name = target_user.nickname or target_user.username or "Trainer"

        text = (
            f"💸 <b>COINS TRANSFERRED</b> 💸\n"
            f"◈ ────────────────── ◈\n"
            f"Trainer <b>{html.escape(sender_name)}</b> sent coins to Trainer <b>{html.escape(target_name)}</b>:\n"
            f"💰 <b>-{amount:,} coins</b> ➡️ 💰 <code>+{amount:,} coins</code>\n\n"
            f"👤 <b>Sender Balance:</b> <code>💰 {sender_user.coins:,} coins</code>\n"
            f"👤 <b>Recipient Balance:</b> <code>💰 {target_user.coins:,} coins</code>\n"
            f"◈ ────────────────── ◈"
        )
        try:
            await callback.message.edit_text(text, parse_mode="HTML")
        except Exception:
            await callback.message.answer(text, parse_mode="HTML")

        # Notify recipient via DM if possible
        dm_text = (
            f"💰 <b>You received coins!</b>\n"
            f"◈ ────────────────── ◈\n"
            f"Trainer <b>{html.escape(sender_name)}</b> transferred 💰 <b>{amount:,} coins</b> to you!\n"
            f"👤 <b>Your New Balance:</b> <code>💰 {target_user.coins:,} coins</code>\n"
            f"◈ ────────────────── ◈"
        )
        try:
            await callback.bot.send_message(chat_id=target_id, text=dm_text, parse_mode="HTML")
        except Exception:
            pass

        await callback.answer("✅ Coins transferred successfully!")
    except Exception as e:
        logger.exception("Error in cb_pay_confirm:")
        await callback.answer("❌ Error processing transfer.", show_alert=True)


@router.callback_query(F.data.startswith("pay_dec_"))
async def cb_pay_decline(callback: CallbackQuery):
    try:
        parts = callback.data.split("_")
        sender_id = int(parts[2])

        if callback.from_user.id != sender_id:
            await callback.answer("❌ Only the sender can cancel this transfer!", show_alert=True)
            return

        try:
            await callback.message.edit_text("❌ <b>Coin transfer cancelled.</b>", parse_mode="HTML")
        except Exception:
            pass
        await callback.answer("Transfer cancelled.")
    except Exception as e:
        logger.exception("Error in cb_pay_decline:")
        await callback.answer()


@router.message(Command("trade"))
async def cmd_trade(message: Message, db: AsyncSession):
    try:
        parts = message.text.split()
        sender_id = message.from_user.id
        target_id = None
        target_name = "Trainer"
        my_pokedex_id = None
        their_pokedex_id = None

        # Case 1: Reply to a user's message
        if message.reply_to_message:
            target_tg_user = message.reply_to_message.from_user
            if not target_tg_user:
                await message.answer("❌ Cannot trade with an anonymous message/channel.", parse_mode="HTML")
                return
            if target_tg_user.is_bot:
                await message.answer("❌ You cannot trade Pokémon with bots!", parse_mode="HTML")
                return
            
            target_id = target_tg_user.id
            target_name = target_tg_user.first_name or "Trainer"

            if len(parts) < 2:
                await message.answer(
                    "⚠️ <b>Trade Format Error</b>\n\n"
                    "When replying to a user's message:\n"
                    "• <code>/trade &lt;pokedex_id&gt;</code> (offer a Pokémon)\n"
                    "• <code>/trade &lt;your_pokedex_id&gt; &lt;their_pokedex_id&gt;</code> (swap Pokémon)\n\n"
                    "<i>Example:</i> <code>/trade 150</code>",
                    parse_mode="HTML"
                )
                return

            if not parts[1].isdigit():
                await message.answer("⚠️ Pokédex number must be numeric (e.g. <code>/trade 150</code>).", parse_mode="HTML")
                return
            my_pokedex_id = int(parts[1])

            if len(parts) > 2 and parts[2].isdigit():
                their_pokedex_id = int(parts[2])

        # Case 2: Direct command in group or DM (with @username or user_id)
        else:
            if len(parts) == 1:
                await message.answer(
                    "🤝 <b>POKÉMON TRADE USAGE</b>\n"
                    "◈ ────────────────── ◈\n"
                    "• <b>Reply to user:</b> <code>/trade &lt;your_pokedex_id&gt; [their_pokedex_id]</code>\n"
                    "• <b>Mention user:</b> <code>/trade @username &lt;your_pokedex_id&gt; [their_pokedex_id]</code>\n"
                    "◈ ────────────────── ◈\n"
                    "<i>Example:</i> <code>/trade @AshKetchum 150</code>",
                    parse_mode="HTML"
                )
                return

            if len(parts) == 2:
                if parts[1].isdigit():
                    await message.answer(
                        f"⚠️ <b>Missing Trade Partner</b>\n\n"
                        f"To trade Pokémon <code>#{parts[1]}</code>, you must either:\n"
                        f"1️⃣ <b>Reply</b> to a user's message with <code>/trade {parts[1]}</code>\n"
                        f"2️⃣ <b>Specify</b> target user: <code>/trade @username {parts[1]}</code>",
                        parse_mode="HTML"
                    )
                    return
                else:
                    await message.answer("⚠️ Please specify which Pokémon to trade:\n<code>/trade @username &lt;pokedex_id&gt;</code>", parse_mode="HTML")
                    return

            # len(parts) >= 3: Support both `/trade @user 150` and `/trade 150 @user`
            target_str = None
            if parts[1].startswith("@") or (not parts[1].isdigit() and not parts[2].isdigit()):
                target_str = parts[1]
                if parts[2].isdigit():
                    my_pokedex_id = int(parts[2])
                if len(parts) > 3 and parts[3].isdigit():
                    their_pokedex_id = int(parts[3])
            elif parts[1].isdigit() and (parts[2].startswith("@") or not parts[2].isdigit()):
                my_pokedex_id = int(parts[1])
                target_str = parts[2]
                if len(parts) > 3 and parts[3].isdigit():
                    their_pokedex_id = int(parts[3])
            elif parts[1].isdigit() and parts[2].isdigit():
                # User typed `/trade 123456789 150`
                target_str = parts[1]
                my_pokedex_id = int(parts[2])
                if len(parts) > 3 and parts[3].isdigit():
                    their_pokedex_id = int(parts[3])

            if not target_str or my_pokedex_id is None:
                await message.answer("⚠️ Invalid syntax. Use <code>/trade @username &lt;pokedex_id&gt;</code>", parse_mode="HTML")
                return

            # Resolve target user
            if target_str.startswith("@"):
                username = target_str.lstrip("@").strip()
                user_stmt = select(User).where(func.lower(User.username) == func.lower(username))
                user_res = await db.execute(user_stmt)
                db_target = user_res.scalar_one_or_none()
                if not db_target:
                    await message.answer(f"❌ User @{html.escape(username)} was not found in the bot database.", parse_mode="HTML")
                    return
                target_id = db_target.id
                target_name = db_target.nickname or f"@{username}"
            elif target_str.isdigit():
                t_id = int(target_str)
                user_stmt = select(User).where(User.id == t_id)
                user_res = await db.execute(user_stmt)
                db_target = user_res.scalar_one_or_none()
                if not db_target:
                    await message.answer(f"❌ User ID <code>{t_id}</code> was not found in the bot database.", parse_mode="HTML")
                    return
                target_id = db_target.id
                target_name = db_target.nickname or "Trainer"
            else:
                await message.answer("⚠️ Target must be @username or user ID.", parse_mode="HTML")
                return

        if target_id == sender_id:
            await message.answer("❌ You cannot trade with yourself!", parse_mode="HTML")
            return

        # Ensure Sender is in DB
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

        # Ensure Target is in DB
        target_stmt = select(User).where(User.id == target_id)
        target_res = await db.execute(target_stmt)
        target_user = target_res.scalar_one_or_none()
        if not target_user:
            target_user = User(
                id=target_id,
                username=getattr(target_tg_user, "username", None) if 'target_tg_user' in locals() and target_tg_user else None,
                nickname=target_name
            )
            db.add(target_user)
            await db.flush()

        # 1. Query Proposer's Pokémon
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

        # 2. Query Partner's Pokémon (if swap requested)
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
                    f"Target Trainer <b>{html.escape(target_user.nickname or target_name)}</b> does not own any Pokémon with Pokédex number/ID <code>#{their_pokedex_id}</code>.",
                    parse_mode="HTML"
                )
                return
            their_up, their_p = their_pair

        # Safe IV calculation
        my_iv_hp = my_up.iv_hp or 0
        my_iv_atk = my_up.iv_atk or 0
        my_iv_def = my_up.iv_def or 0
        my_iv_spd = my_up.iv_spd or 0
        my_iv_total = round((my_iv_hp + my_iv_atk + my_iv_def + my_iv_spd) / 124 * 100, 1)

        my_shiny = "✨ Shiny " if my_up.is_shiny else ""
        my_rarity = get_rarity_emoji(my_p.rarity if my_p and my_p.rarity else "Common")
        my_name = html.escape(my_up.nickname or (my_p.name.title() if my_p and my_p.name else "Pokemon"))
        my_level = my_up.level or 1
        my_display = f"{my_rarity} {my_shiny}<b>{my_name}</b> <code>(Lvl {my_level} | IV: {my_iv_total}%)</code> [#{my_p.id}]"

        if their_up and their_p:
            their_iv_hp = their_up.iv_hp or 0
            their_iv_atk = their_up.iv_atk or 0
            their_iv_def = their_up.iv_def or 0
            their_iv_spd = their_up.iv_spd or 0
            their_iv_total = round((their_iv_hp + their_iv_atk + their_iv_def + their_iv_spd) / 124 * 100, 1)

            their_shiny = "✨ Shiny " if their_up.is_shiny else ""
            their_rarity = get_rarity_emoji(their_p.rarity if their_p and their_p.rarity else "Common")
            their_name = html.escape(their_up.nickname or (their_p.name.title() if their_p and their_p.name else "Pokemon"))
            their_level = their_up.level or 1
            their_display = f"{their_rarity} {their_shiny}<b>{their_name}</b> <code>(Lvl {their_level} | IV: {their_iv_total}%)</code> [#{their_p.id}]"
        else:
            their_display = "🎁 <i>Gift / Free Transfer</i>"

        sender_display_name = html.escape(sender_user.nickname or message.from_user.first_name or "Trainer")
        target_display_name = html.escape(target_user.nickname or target_name or "Trainer")

        text = (
            f"🤝 <b>POKÉMON TRADE PROPOSAL</b> 🤝\n"
            f"◈ ────────────────── ◈\n"
            f"👤 <b>Proposer:</b> <b>{sender_display_name}</b>\n"
            f"👉 <b>Offering:</b> {my_display}\n\n"
            f"👤 <b>Trade Partner:</b> <b>{target_display_name}</b>\n"
            f"👉 <b>Requesting:</b> {their_display}\n"
            f"◈ ────────────────── ◈\n"
            f"⏳ <i>Waiting for <b>{target_display_name}</b> to respond...</i>"
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
    except Exception as e:
        logger.exception("Error in cmd_trade:")
        await message.answer("❌ An error occurred while initiating trade.", parse_mode="HTML")


@router.callback_query(F.data.startswith("t_acc_"))
async def cb_trade_accept(callback: CallbackQuery, db: AsyncSession):
    try:
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
        my_rarity = get_rarity_emoji(my_p.rarity if my_p and my_p.rarity else "Common")
        my_name = f"{my_rarity} {my_shiny}<b>{html.escape(my_up.nickname or (my_p.name.title() if my_p and my_p.name else 'Pokemon'))}</b>"
        my_lvl = my_up.level or 1

        if their_up and their_p:
            their_shiny = "✨ Shiny " if their_up.is_shiny else ""
            their_rarity = get_rarity_emoji(their_p.rarity if their_p and their_p.rarity else "Common")
            their_name = f"{their_rarity} {their_shiny}<b>{html.escape(their_up.nickname or (their_p.name.title() if their_p and their_p.name else 'Pokemon'))}</b>"
            their_lvl = their_up.level or 1
            
            success_text = (
                f"✅ <b>TRADE COMPLETED SUCCESSFULLY</b> ✅\n"
                f"◈ ────────────────── ◈\n"
                f"🔄 <b>Exchange Summary:</b>\n\n"
                f"👤 Trainer <b>{html.escape(proposer.nickname or 'Trainer')}</b> received:\n"
                f"👉 {their_name} <code>(Lvl {their_lvl})</code>\n\n"
                f"👤 Trainer <b>{html.escape(target.nickname or 'Trainer')}</b> received:\n"
                f"👉 {my_name} <code>(Lvl {my_lvl})</code>\n"
                f"◈ ────────────────── ◈\n"
                f"🎉 <i>Congratulations on your new Pokémon!</i>"
            )
        else:
            success_text = (
                f"🎁 <b>GIFT COMPLETED SUCCESSFULLY</b> 🎁\n"
                f"◈ ────────────────── ◈\n"
                f"👤 Trainer <b>{html.escape(target.nickname or 'Trainer')}</b> received:\n"
                f"👉 {my_name} <code>(Lvl {my_lvl})</code> as a gift from <b>{html.escape(proposer.nickname or 'Trainer')}</b>!\n"
                f"◈ ────────────────── ◈"
            )

        await callback.message.edit_text(success_text, parse_mode="HTML")
        await callback.answer("🎉 Trade completed!")
    except Exception as e:
        logger.exception("Error in cb_trade_accept:")
        await callback.answer("❌ Error processing trade acceptance.", show_alert=True)


@router.callback_query(F.data.startswith("t_dec_"))
async def cb_trade_decline(callback: CallbackQuery, db: AsyncSession):
    try:
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
    except Exception as e:
        logger.exception("Error in cb_trade_decline:")
        await callback.answer("❌ Error declining trade.", show_alert=True)
