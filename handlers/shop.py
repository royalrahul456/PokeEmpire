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
        InlineKeyboardButton(text="🎁 Mythical Box (8000c)", callback_data="buy_box_Mythical"),
        InlineKeyboardButton(text="🍬 Rare Candy (300c)", callback_data="buy_candy")
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
        f"• **Rare Candy** (💰 300c)\n"
        f"  _Instantly level up a Pokémon by 1 level._\n"
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
        f"• **Rare Candy** (💰 300c)\n"
        f"  _Instantly level up a Pokémon by 1 level._\n"
        f"• **Shiny Charm** (💰 2000c)\n"
        f"  _Permanently gives a 1% chance to upgrade any normal catch to a Shiny Pokémon!_\n"
        f"───────────────"
    )

    await callback.message.edit_text(text, reply_markup=get_shop_keyboard(user.has_shiny_charm).as_markup(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("buy_box_"))
async def cb_buy_box(callback: CallbackQuery, db: AsyncSession):
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

    # Roll stats/IVs
    iv_hp = random.randint(0, 31)
    iv_atk = random.randint(0, 31)
    iv_def = random.randint(0, 31)
    iv_spd = random.randint(0, 31)
    iv_total = iv_hp + iv_atk + iv_def + iv_spd
    iv_pct = int((iv_total / 124) * 100)

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
    await db.commit()

    shiny_badge = "✨ Shiny " if is_shiny else ""
    r_emoji = get_rarity_emoji(selected_pokemon.rarity)
    
    hp_bar = get_progress_bar(iv_hp, 31, 5, fill_char="▰", empty_char="▱")
    atk_bar = get_progress_bar(iv_atk, 31, 5, fill_char="▰", empty_char="▱")
    def_bar = get_progress_bar(iv_def, 31, 5, fill_char="▰", empty_char="▱")
    spd_bar = get_progress_bar(iv_spd, 31, 5, fill_char="▰", empty_char="▱")

    text = (
        f"🎁 **BOX UNBOXING** 🎁\n"
        f"───────────────\n"
        f"You opened a **{rarity} Box** for `💰 {cost} coins`!\n\n"
        f"🎉 Unlocked: {r_emoji} {shiny_badge}**{selected_pokemon.name.title()}**!\n"
        f"📊 **Level**: `Lvl 1`\n"
        f"🧬 **IV Quality**: `🧬 {iv_pct}%`\n"
        f"• HP IV: `[{hp_bar}]` `({iv_hp}/31)`\n"
        f"• ATK IV: `[{atk_bar}]` `({iv_atk}/31)`\n"
        f"• DEF IV: `[{def_bar}]` `({iv_def}/31)`\n"
        f"• SPD IV: `[{spd_bar}]` `({iv_spd}/31)`\n\n"
        f"💰 **Remaining Balance**: `💰 {user.coins} coins`\n"
        f"───────────────"
    )

    await callback.message.edit_text(text, reply_markup=get_back_to_hub_keyboard(), parse_mode="Markdown")
    await callback.answer(f"Unlocked {selected_pokemon.name.title()}!")

@router.callback_query(F.data == "buy_charm")
async def cb_buy_charm(callback: CallbackQuery, db: AsyncSession):
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
    await db.commit()

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

@router.callback_query(F.data == "buy_candy")
async def cb_buy_candy(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id
    cost = 300

    user_stmt = select(User).where(User.id == user_id)
    user_res = await db.execute(user_stmt)
    user = user_res.scalar_one_or_none()

    if not user or user.coins < cost:
        await callback.answer(f"❌ You don't have enough coins! Need {cost} coins.", show_alert=True)
        return

    # Fetch user's Pokémon
    stmt = select(UserPokemon, Pokemon).join(Pokemon).where(UserPokemon.user_id == user_id).order_by(UserPokemon.caught_at.desc())
    res = await db.execute(stmt)
    pairs = res.all()

    if not pairs:
        await callback.answer("❌ You don't own any Pokémon to level up!", show_alert=True)
        return

    text = (
        f"🍬 **FEED RARE CANDY** 🍬\n"
        f"───────────────\n"
        f"Cost: `💰 300 coins` per feed (Instantly level up a Pokémon by 1 level)\n\n"
        f"👉 Select a Pokémon from your recent catches to feed:\n"
    )
    builder = InlineKeyboardBuilder()

    for up, p in pairs[:10]:  # limit to top 10 most recent catches to prevent keyboard overflow
        shiny_tag = "✨" if up.is_shiny else ""
        name_display = up.nickname if up.nickname else p.name.title()
        builder.row(InlineKeyboardButton(
            text=f"{shiny_tag}{name_display} (Lvl {up.level})",
            callback_data=f"apply_candy_{up.id}"
        ))

    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="dm_shop"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("apply_candy_"))
async def cb_apply_candy(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id
    up_id = int(callback.data.split("_")[2])
    cost = 300

    # Query User
    user_stmt = select(User).where(User.id == user_id)
    user_res = await db.execute(user_stmt)
    user = user_res.scalar_one_or_none()

    if not user or user.coins < cost:
        await callback.answer("❌ You don't have enough coins!", show_alert=True)
        return

    # Query UserPokemon
    stmt = select(UserPokemon, Pokemon).join(Pokemon).where(UserPokemon.id == up_id, UserPokemon.user_id == user_id)
    res = await db.execute(stmt)
    pair = res.first()

    if not pair:
        await callback.answer("❌ Pokémon not found.", show_alert=True)
        return

    up, p = pair
    user.coins -= cost
    up.level += 1
    up.xp = 0  # reset XP on level up
    await db.commit()

    name_display = up.nickname if up.nickname else p.name.title()
    text = (
        f"🍬 **CANDY CONSUMED** 🍬\n"
        f"───────────────\n"
        f"You fed a Rare Candy to your Pokémon!\n\n"
        f"📈 **{name_display}** leveled up to **Lvl {up.level}**!\n"
        f"💰 **Remaining Balance**: `💰 {user.coins} coins`\n"
        f"───────────────"
    )

    await callback.message.edit_text(text, reply_markup=get_back_to_hub_keyboard(), parse_mode="Markdown")
    await callback.answer("Level up!")
