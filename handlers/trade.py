import random
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import config
from database.models import User, Pokemon, UserPokemon
from utils.formatters import get_rarity_emoji, escape_md

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
            await message.answer("⚠️ Format: Reply to a user's message with `/pay <amount>`")
            return
        amount = int(parts[1])
        target_tg_user = message.reply_to_message.from_user
        target_id = target_tg_user.id
        
        if target_id == sender_id:
            await message.answer("❌ You cannot transfer coins to yourself!")
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
            await message.answer("⚠️ Format: `/pay <@username/user_id> <amount>` (or reply to their message with `/pay <amount>`)")
            return
            
        target_str = parts[1]
        amount_str = parts[2]
        
        if not amount_str.isdigit():
            await message.answer("⚠️ Amount must be a positive integer.")
            return
        amount = int(amount_str)
        
        if target_str.isdigit():
            target_id = int(target_str)
            if target_id == sender_id:
                await message.answer("❌ You cannot transfer coins to yourself!")
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
                    await message.answer(f"❌ User ID {target_id} is not registered and couldn't be resolved.")
                    return
        elif target_str.startswith("@"):
            username = target_str.replace("@", "").strip()
            user_stmt = select(User).where(User.username.ilike(username))
            user_res = await db.execute(user_stmt)
            target_user = user_res.scalar_one_or_none()
            if not target_user:
                await message.answer(f"❌ User with username @{username} not found in database.")
                return
            if target_user.id == sender_id:
                await message.answer("❌ You cannot transfer coins to yourself!")
                return
        else:
            await message.answer("⚠️ Target must be a user ID or @username.")
            return

    if amount <= 0:
        await message.answer("⚠️ Amount must be greater than zero.")
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
        await message.answer(f"❌ Transaction failed. You don't have enough coins! (Balance: `💰 {sender_user.coins} coins`)")
        return

    # Transfer coins
    sender_user.coins -= amount
    target_user.coins += amount
    await db.commit()

    text = (
        f"💸 **COINS TRANSFERRED** 💸\n"
        f"───────────────\n"
        f"Trainer **{escape_md(sender_user.nickname)}** sent coins to Trainer **{escape_md(target_user.nickname)}**:\n"
        f"💰 **-{amount} coins** ➡️ `💰 {amount} coins`\n\n"
        f"👤 Sender Balance: `💰 {sender_user.coins} coins`\n"
        f"👤 Recipient Balance: `💰 {target_user.coins} coins`\n"
        f"───────────────"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(Command("trade"))
async def cmd_trade(message: Message, db: AsyncSession):
    parts = message.text.split()
    sender_id = message.from_user.id
    target_tg_user = None
    my_pokemon_id = None
    their_pokemon_id = None
    
    # 1. Parse arguments
    if message.reply_to_message:
        if len(parts) < 2 or not parts[1].isdigit():
            await message.answer("⚠️ Format: Reply to a user with `/trade <your_pokemon_id> [their_pokemon_id]`")
            return
        my_pokemon_id = int(parts[1])
        if len(parts) > 2 and parts[2].isdigit():
            their_pokemon_id = int(parts[2])
        target_tg_user = message.reply_to_message.from_user
    else:
        if len(parts) < 3 or not parts[2].isdigit():
            await message.answer("⚠️ Format: `/trade <@username/user_id> <your_pokemon_id> [their_pokemon_id]`")
            return
        target_str = parts[1]
        my_pokemon_id = int(parts[2])
        if len(parts) > 3 and parts[3].isdigit():
            their_pokemon_id = int(parts[3])
            
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
                    await message.answer(f"❌ User ID {t_id} is not registered in the database.")
                    return
        elif target_str.startswith("@"):
            username = target_str.replace("@", "").strip()
            user_stmt = select(User).where(User.username.ilike(username))
            user_res = await db.execute(user_stmt)
            db_user = user_res.scalar_one_or_none()
            if not db_user:
                await message.answer(f"❌ User with username @{username} not found in database.")
                return
            class TempUser:
                def __init__(self, id, first_name, username):
                    self.id = id
                    self.first_name = first_name
                    self.username = username
            target_tg_user = TempUser(db_user.id, db_user.nickname, db_user.username)
        else:
            await message.answer("⚠️ Target must be a user ID or @username.")
            return

    target_id = target_tg_user.id
    if target_id == sender_id:
        await message.answer("❌ You cannot trade with yourself!")
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
        target_user = User(id=target_id, username=getattr(target_tg_user, "username", None), nickname=target_tg_user.first_name)
        db.add(target_user)
        await db.flush()

    # Query Proposer's Pokémon
    my_poke_stmt = select(UserPokemon, Pokemon).join(Pokemon).where(UserPokemon.id == my_pokemon_id, UserPokemon.user_id == sender_id)
    my_poke_res = await db.execute(my_poke_stmt)
    my_pair = my_poke_res.first()
    if not my_pair:
        await message.answer(f"❌ You do not own any Pokémon with database ID `{my_pokemon_id}`!")
        return
    my_up, my_p = my_pair

    # Query Partner's Pokémon (if swap)
    their_up, their_p = None, None
    if their_pokemon_id is not None:
        their_poke_stmt = select(UserPokemon, Pokemon).join(Pokemon).where(UserPokemon.id == their_pokemon_id, UserPokemon.user_id == target_id)
        their_poke_res = await db.execute(their_poke_stmt)
        their_pair = their_poke_res.first()
        if not their_pair:
            await message.answer(f"❌ Target Trainer **{escape_md(target_user.nickname)}** does not own any Pokémon with database ID `{their_pokemon_id}`!")
            return
        their_up, their_p = their_pair

    # Form text representation
    my_shiny = "✨ Shiny " if my_up.is_shiny else ""
    my_rarity = get_rarity_emoji(my_p.rarity)
    my_display = f"{my_rarity} {my_shiny}**{escape_md(my_up.nickname or my_p.name.title())}** `(Lvl {my_up.level})`"

    if their_pokemon_id is not None:
        their_shiny = "✨ Shiny " if their_up.is_shiny else ""
        their_rarity = get_rarity_emoji(their_p.rarity)
        their_display = f"{their_rarity} {their_shiny}**{escape_md(their_up.nickname or their_p.name.title())}** `(Lvl {their_up.level})`"
    else:
        their_display = "🎁 *Gift (Free Transfer)*"

    text = (
        f"🤝 **TRADE PROPOSAL** 🤝\n"
        f"───────────────\n"
        f"👤 **Proposer**: Trainer **{escape_md(sender_user.nickname)}**\n"
        f"👉 Offering: {my_display}\n\n"
        f"👤 **Partner**: Trainer **{escape_md(target_user.nickname)}**\n"
        f"👉 Offering: {their_display}\n"
        f"───────────────\n"
        f"⚠️ *Trainer {escape_md(target_user.nickname)}, please accept or decline below.*"
    )

    builder = InlineKeyboardBuilder()
    their_pid_str = str(their_pokemon_id) if their_pokemon_id is not None else "none"
    callback_accept = f"t_acc_{sender_id}_{target_id}_{my_pokemon_id}_{their_pid_str}"
    callback_decline = f"t_dec_{sender_id}_{target_id}_{my_pokemon_id}_{their_pid_str}"

    builder.row(
        InlineKeyboardButton(text="✅ Accept", callback_data=callback_accept),
        InlineKeyboardButton(text="❌ Decline", callback_data=callback_decline)
    )

    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

@router.callback_query(F.data.startswith("t_acc_"))
async def cb_trade_accept(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    proposer_id = int(parts[2])
    target_id = int(parts[3])
    my_pokemon_id = int(parts[4])
    their_pid_str = parts[5]
    their_pokemon_id = int(their_pid_str) if their_pid_str != "none" else None

    # Only target can accept
    if callback.from_user.id != target_id:
        await callback.answer("❌ Only the trade partner can accept this trade proposal!", show_alert=True)
        return

    # Check/Fetch players
    p_stmt = select(User).where(User.id == proposer_id)
    p_res = await db.execute(p_stmt)
    proposer = p_res.scalar_one_or_none()

    t_stmt = select(User).where(User.id == target_id)
    t_res = await db.execute(t_stmt)
    target = t_res.scalar_one_or_none()

    if not proposer or not target:
        await callback.answer("❌ Error: One of the trainers is not registered.", show_alert=True)
        return

    # Verify Proposer still owns Pokémon
    my_poke_stmt = select(UserPokemon, Pokemon).join(Pokemon).where(UserPokemon.id == my_pokemon_id, UserPokemon.user_id == proposer_id)
    my_poke_res = await db.execute(my_poke_stmt)
    my_pair = my_poke_res.first()

    if not my_pair:
        await callback.answer("❌ Trade failed! Proposer no longer owns the Pokémon.", show_alert=True)
        await callback.message.edit_text("❌ **TRADE FAILED**: Offering Pokémon is no longer owned by Proposer.")
        return
    my_up, my_p = my_pair

    # Verify Target still owns Pokémon (if swap)
    their_up, their_p = None, None
    if their_pokemon_id is not None:
        their_poke_stmt = select(UserPokemon, Pokemon).join(Pokemon).where(UserPokemon.id == their_pokemon_id, UserPokemon.user_id == target_id)
        their_poke_res = await db.execute(their_poke_stmt)
        their_pair = their_poke_res.first()

        if not their_pair:
            await callback.answer("❌ Trade failed! Partner no longer owns the Pokémon.", show_alert=True)
            await callback.message.edit_text("❌ **TRADE FAILED**: Demanded Pokémon is no longer owned by Partner.")
            return
        their_up, their_p = their_pair

    # Perform trade transfer
    my_up.user_id = target_id
    if their_up:
        their_up.user_id = proposer_id

    await db.commit()

    my_shiny = "✨ Shiny " if my_up.is_shiny else ""
    my_rarity = get_rarity_emoji(my_p.rarity)
    my_name = f"{my_rarity} {my_shiny}**{my_up.nickname or my_p.name.title()}**"

    if their_up:
        their_shiny = "✨ Shiny " if their_up.is_shiny else ""
        their_rarity = get_rarity_emoji(their_p.rarity)
        their_name = f"{their_rarity} {their_shiny}**{their_up.nickname or their_p.name.title()}**"
        
        success_text = (
            f"✅ **TRADE COMPLETED** ✅\n"
            f"───────────────\n"
            f"🔄 **Exchange Successful!**\n\n"
            f"👤 Trainer **{escape_md(proposer.nickname)}** received:\n"
            f"👉 {their_name} `(Lvl {their_up.level})`\n\n"
            f"👤 Trainer **{escape_md(target.nickname)}** received:\n"
            f"👉 {my_name} `(Lvl {my_up.level})`\n"
            f"───────────────"
        )
    else:
        success_text = (
            f"🎁 **GIFT COMPLETED** 🎁\n"
            f"───────────────\n"
            f"🎉 **Pokémon Transferred!**\n\n"
            f"👤 Trainer **{escape_md(target.nickname)}** received:\n"
            f"👉 {my_name} `(Lvl {my_up.level})` as a gift from **{escape_md(proposer.nickname)}**!\n"
            f"───────────────"
        )

    await callback.message.edit_text(success_text, parse_mode="Markdown")
    await callback.answer("Trade Completed!")

@router.callback_query(F.data.startswith("t_dec_"))
async def cb_trade_decline(callback: CallbackQuery, db: AsyncSession):
    parts = callback.data.split("_")
    proposer_id = int(parts[2])
    target_id = int(parts[3])
    user_clicking = callback.from_user.id

    if user_clicking not in [proposer_id, target_id]:
        await callback.answer("❌ Only participants of this trade can cancel/decline it!", show_alert=True)
        return

    # Check/Fetch players
    p_stmt = select(User).where(User.id == proposer_id)
    p_res = await db.execute(p_stmt)
    proposer = p_res.scalar_one_or_none()

    t_stmt = select(User).where(User.id == target_id)
    t_res = await db.execute(t_stmt)
    target = t_res.scalar_one_or_none()

    proposer_name = escape_md(proposer.nickname) if proposer else "Proposer"
    target_name = escape_md(target.nickname) if target else "Partner"

    if user_clicking == proposer_id:
        cancel_text = (
            f"❌ **TRADE CANCELLED** ❌\n"
            f"───────────────\n"
            f"Trainer **{proposer_name}** cancelled their trade proposal.\n"
            f"───────────────"
        )
        await callback.message.edit_text(cancel_text, parse_mode="Markdown")
        await callback.answer("Trade Cancelled!")
    else:
        decline_text = (
            f"❌ **TRADE DECLINED** ❌\n"
            f"───────────────\n"
            f"Trainer **{target_name}** declined the trade proposal from **{proposer_name}**.\n"
            f"───────────────"
        )
        await callback.message.edit_text(decline_text, parse_mode="Markdown")
        await callback.answer("Trade Declined!")
