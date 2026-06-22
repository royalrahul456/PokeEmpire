import random
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from database.models import User, Pokemon, UserPokemon
from keyboards.inline import get_back_to_hub_keyboard
from utils.formatters import get_progress_bar, get_rarity_emoji

router = Router()

def get_shop_keyboard(user_has_charm: bool) -> InlineKeyboardBuilder:
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🎁 Common Box (200c)", callback_data="buy_box_Common"),
        InlineKeyboardButton(text="🎁 Rare Box (500c)", callback_data="buy_box_Rare")
    )
    builder.row(
        InlineKeyboardButton(text="🎁 Epic Box (1200c)", callback_data="buy_box_Epic"),
        InlineKeyboardButton(text="🎁 Legendary Box (4000c)", callback_data="buy_box_Legendary")
    )
    builder.row(
        InlineKeyboardButton(text="🎁 Mythical Box (8000c)", callback_data="buy_box_Mythical")
    )
    if not user_has_charm:
        builder.row(
            InlineKeyboardButton(text="✨ Shiny Charm (2000c)", callback_data="buy_charm")
        )
    builder.row(InlineKeyboardButton(text="🔙 Back to Hub Menu", callback_data="dm_home"))
    return builder

@router.message(Command("shop"))
async def cmd_shop(message: Message, db: AsyncSession):
    user_id = message.from_user.id
    nickname = message.from_user.first_name

    # Check/Register user
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user:
        user = User(id=user_id, username=message.from_user.username, nickname=nickname)
        db.add(user)
        await db.commit()

    text = (
        f"🛒 **POKÉEMPIRE SHOP** 🛒\n"
        f"💰 Balance: **{user.coins} coins**\n"
        f"───────────────\n"
        f"Welcome, Trainer! Purchase mystery boxes to obtain high-tier Pokémon, or buy upgrades to boost your journey.\n\n"
        f"🎁 **Mystery Boxes**:\n"
        f"• **Common Box** (💰 200c)\n"
        f"  _Contains a random Common Pokémon._\n"
        f"• **Rare Box** (💰 500c)\n"
        f"  _Contains a random Rare Pokémon._\n"
        f"• **Epic Box** (💰 1200c)\n"
        f"  _Contains a random Epic Pokémon._\n"
        f"• **Legendary Box** (💰 4000c)\n"
        f"  _Contains a random Legendary Pokémon._\n"
        f"• **Mythical Box** (💰 8000c)\n"
        f"  _Contains a random Mythical Pokémon._\n\n"
        f"⚡ **Upgrades & Items**:\n"
        f"• **Shiny Charm** (💰 2000c)\n"
        f"  _Permanently gives a 1% chance to upgrade any normal catch to a Shiny Pokémon!_\n"
        f"───────────────"
    )

    await message.answer(text, reply_markup=get_shop_keyboard(user.has_shiny_charm).as_markup(), parse_mode="Markdown")

@router.callback_query(F.data == "dm_shop")
async def cb_dm_shop(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id
    nickname = callback.from_user.first_name

    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user:
        user = User(id=user_id, username=callback.from_user.username, nickname=nickname)
        db.add(user)
        await db.commit()

    text = (
        f"🛒 **POKÉEMPIRE SHOP** 🛒\n"
        f"💰 Balance: **{user.coins} coins**\n"
        f"───────────────\n"
        f"Welcome, Trainer! Purchase mystery boxes to obtain high-tier Pokémon, or buy upgrades to boost your journey.\n\n"
        f"🎁 **Mystery Boxes**:\n"
        f"• **Common Box** (💰 200c)\n"
        f"  _Contains a random Common Pokémon._\n"
        f"• **Rare Box** (💰 500c)\n"
        f"  _Contains a random Rare Pokémon._\n"
        f"• **Epic Box** (💰 1200c)\n"
        f"  _Contains a random Epic Pokémon._\n"
        f"• **Legendary Box** (💰 4000c)\n"
        f"  _Contains a random Legendary Pokémon._\n"
        f"• **Mythical Box** (💰 8000c)\n"
        f"  _Contains a random Mythical Pokémon._\n\n"
        f"⚡ **Upgrades & Items**:\n"
        f"• **Shiny Charm** (💰 2000c)\n"
        f"  _Permanently gives a 1% chance to upgrade any normal catch to a Shiny Pokémon!_\n"
        f"───────────────"
    )

    try:
        await callback.message.edit_caption(caption=text, reply_markup=get_shop_keyboard(user.has_shiny_charm).as_markup(), parse_mode="Markdown")
    except Exception:
        try:
            await callback.message.edit_text(text, reply_markup=get_shop_keyboard(user.has_shiny_charm).as_markup(), parse_mode="Markdown")
        except Exception:
            pass
    await callback.answer()

@router.callback_query(F.data.startswith("buy_box_"))
async def cb_buy_box(callback: CallbackQuery, db: AsyncSession):
    import config
    user_id = callback.from_user.id
    rarity = callback.data.split("_")[2]  # Common, Rare, Epic, Legendary

    # Define costs
    costs = {
        "Common": 200,
        "Rare": 500,
        "Epic": 1200,
        "Legendary": 4000,
        "Mythical": 8000
    }
    cost = costs[rarity]

    # Fetch User
    user_stmt = select(User).where(User.id == user_id)
    user_res = await db.execute(user_stmt)
    user = user_res.scalar_one_or_none()

    if not user or user.coins < cost:
        await callback.answer(f"❌ You don't have enough coins! Need {cost} coins.", show_alert=True)
        return

    # Fetch random Pokémon of this rarity
    poke_stmt = select(Pokemon).where(Pokemon.rarity == rarity)
    poke_res = await db.execute(poke_stmt)
    pokemon_list = poke_res.scalars().all()

    if not pokemon_list:
        await callback.answer("❌ No Pokémon found in this rarity tier.", show_alert=True)
        return

    selected_pokemon = random.choice(pokemon_list)

    # Roll stats/IVs (hidden from message but saved in DB)
    iv_hp = random.randint(0, 31)
    iv_atk = random.randint(0, 31)
    iv_def = random.randint(0, 31)
    iv_spd = random.randint(0, 31)

    # 1 in 100 chance of shiny from shop box
    is_shiny = random.randint(1, 100) == 1

    # Deduct coins and add pokemon
    user.coins -= cost
    
    new_poke = UserPokemon(
        user_id=user_id,
        pokemon_id=selected_pokemon.id,
        is_shiny=is_shiny,
        level=1,
        xp=0,
        iv_hp=iv_hp,
        iv_atk=iv_atk,
        iv_def=iv_def,
        iv_spd=iv_spd
    )
    db.add(new_poke)

    # Credit coins to bot owner
    if config.ADMIN_IDS:
        owner_id = config.ADMIN_IDS[0]
        owner_stmt = select(User).where(User.id == owner_id)
        owner_res = await db.execute(owner_stmt)
        owner = owner_res.scalar_one_or_none()
        if owner:
            owner.coins += cost
        else:
            owner = User(id=owner_id, nickname="Owner", username="Owner", coins=cost)
            db.add(owner)
            
    await db.commit()

    # Send DM alert to owner
    if config.ADMIN_IDS:
        try:
            buyer_name = callback.from_user.first_name
            buyer_username = f" (@{callback.from_user.username})" if callback.from_user.username else ""
            await callback.bot.send_message(
                chat_id=config.ADMIN_IDS[0],
                text=f"💰 <b>Shop Revenue Credited!</b>\n"
                     f"• Trainer: {buyer_name}{buyer_username} (<code>{user_id}</code>)\n"
                     f"• Purchase: <b>{rarity} Box</b>\n"
                     f"• Revenue: <code>+{cost} coins</code>",
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ Failed to send DM to owner: {e}")

    shiny_badge = "✨ Shiny " if is_shiny else ""
    r_emoji = get_rarity_emoji(selected_pokemon.rarity)

    text = (
        f"🎁 **BOX UNBOXING** 🎁\n"
        f"───────────────\n"
        f"You opened a **{rarity} Box** for `💰 {cost} coins`!\n\n"
        f"🎉 Unlocked: {r_emoji} {shiny_badge}**{selected_pokemon.name.title()}**!\n\n"
        f"💰 **Remaining Balance**: `💰 {user.coins} coins`\n"
        f"───────────────"
    )

    await callback.message.edit_text(text, reply_markup=get_back_to_hub_keyboard(), parse_mode="Markdown")
    await callback.answer(f"Unlocked {selected_pokemon.name.title()}!")

@router.callback_query(F.data == "buy_charm")
async def cb_buy_charm(callback: CallbackQuery, db: AsyncSession):
    import config
    user_id = callback.from_user.id
    cost = 2000

    user_stmt = select(User).where(User.id == user_id)
    user_res = await db.execute(user_stmt)
    user = user_res.scalar_one_or_none()

    if not user:
        return

    if user.has_shiny_charm:
        await callback.answer("❌ You already own the Shiny Charm!", show_alert=True)
        return

    if user.coins < cost:
        await callback.answer(f"❌ You don't have enough coins! Need {cost} coins.", show_alert=True)
        return

    user.coins -= cost
    user.has_shiny_charm = True

    # Credit coins to bot owner
    if config.ADMIN_IDS:
        owner_id = config.ADMIN_IDS[0]
        owner_stmt = select(User).where(User.id == owner_id)
        owner_res = await db.execute(owner_stmt)
        owner = owner_res.scalar_one_or_none()
        if owner:
            owner.coins += cost
        else:
            owner = User(id=owner_id, nickname="Owner", username="Owner", coins=cost)
            db.add(owner)

    await db.commit()

    # Send DM alert to owner
    if config.ADMIN_IDS:
        try:
            buyer_name = callback.from_user.first_name
            buyer_username = f" (@{callback.from_user.username})" if callback.from_user.username else ""
            await callback.bot.send_message(
                chat_id=config.ADMIN_IDS[0],
                text=f"💰 <b>Shop Revenue Credited!</b>\n"
                     f"• Trainer: {buyer_name}{buyer_username} (<code>{user_id}</code>)\n"
                     f"• Purchase: <b>Shiny Charm Upgrade</b>\n"
                     f"• Revenue: <code>+{cost} coins</code>",
                parse_mode="HTML"
            )
        except Exception as e:
            print(f"⚠️ Failed to send DM to owner: {e}")

    text = (
        f"✨ **SHINY CHARM ACTIVATE** ✨\n"
        f"───────────────\n"
        f"You spent `💰 2000 coins` to purchase the Shiny Charm!\n\n"
        f"🍀 Your shiny encounter rate in group spawns is now permanently increased!\n\n"
        f"💰 **Remaining Balance**: `💰 {user.coins} coins`\n"
        f"───────────────"
    )

    await callback.message.edit_text(text, reply_markup=get_back_to_hub_keyboard(), parse_mode="Markdown")
    await callback.answer("Shiny Charm activated!")
