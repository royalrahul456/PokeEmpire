from aiogram import Router, F, Bot
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct, case
from database.models import User, Pokemon, UserPokemon, ActiveSpawn, GroupSetting
from keyboards.inline import get_dm_menu_keyboard, get_bag_pagination_keyboard, get_back_to_hub_keyboard, get_dex_pagination_keyboard
from utils.formatters import get_hp_bar, get_progress_bar, get_rarity_emoji, escape_md
from utils.settings import (
    send_cover_media, 
    get_custom_cover, 
    set_custom_cover, 
    delete_custom_cover,
    is_scribble_enabled,
    is_nameguess_enabled
)
import config
import random

router = Router()

# State for cover customization
active_cover_updates = {}

@router.message(CommandStart())
async def cmd_start(message: Message, db: AsyncSession):
    user_id = message.from_user.id
    username = message.from_user.username
    nickname = message.from_user.first_name

    # Check and register user
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()

    if not user:
        user = User(
            id=user_id,
            username=username,
            nickname=nickname
        )
        db.add(user)
        await db.commit()

    if message.chat.type == "private":
        # Check if the user is the bot owner
        if user_id in config.ADMIN_IDS:
            # Query db metrics for Owner Dashboard
            u_count = await db.execute(select(func.count(User.id)))
            total_users = u_count.scalar() or 0
            
            c_count = await db.execute(select(func.count(UserPokemon.id)))
            total_catches = c_count.scalar() or 0
            
            s_count = await db.execute(select(func.count(ActiveSpawn.chat_id)))
            active_spawns = s_count.scalar() or 0

            text = (
                f"⚡ <b>POKÉEMPIRE OWNER DASHBOARD</b> ⚡\n"
                f"───────────────────────────────\n"
                f"👑 Welcome, Creator <b>{escape_md(nickname)}</b>!\n\n"
                f"📊 <b>System Metrics</b>:\n"
                f"• 👥 Total Trainers: <code>{total_users}</code>\n"
                f"• ⚡ Total Catches: <code>{total_catches}</code>\n"
                f"• 🌳 Active Spawns: <code>{active_spawns}</code>\n\n"
                f"Use the console below to manage your profile, view checklists, or configure cover media and global settings!"
            )
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="👤 Profile", callback_data="dm_profile"),
                InlineKeyboardButton(text="🔥 Streak", callback_data="dm_streak")
            )
            builder.row(
                InlineKeyboardButton(text="🏆 Pokédex", callback_data="dm_dex_1"),
                InlineKeyboardButton(text="🛒 Shop", callback_data="dm_shop")
            )
            builder.row(
                InlineKeyboardButton(text="🎮 Games Center", callback_data="dm_games"),
                InlineKeyboardButton(text="❓ Guide", callback_data="dm_help")
            )
            builder.row(
                InlineKeyboardButton(text="🛠️ Owner Tools", callback_data="owner_tools")
            )
            
            await send_cover_media(
                chat_id=message.chat.id,
                key="start",
                caption=text,
                reply_markup=builder.as_markup(),
                bot=message.bot,
                default_file="data/pokeempire_banner.png"
            )
        else:
            # Standard premium player dashboard
            text = (
                f"⚡ <b>POKÉEMPIRE HUB</b> ⚡\n"
                f"───────────────────────────────\n"
                f"✨ Welcome, Trainer <b>{escape_md(nickname)}</b>!\n\n"
                f"I spawn wild Pokémon in your active Telegram Groups based on group message activity. "
                f"Be the first to guess their names and catch them!\n\n"
                f"Use the premium interactive dashboard below to view your profile, browse your collection bag, track your Pokédex checklist, or read the game guide.\n\n"
                f"👉 <i>Select an option from the menu:</i>"
            )
            await send_cover_media(
                chat_id=message.chat.id,
                key="start",
                caption=text,
                reply_markup=get_dm_menu_keyboard(),
                bot=message.bot,
                default_file="data/pokeempire_banner.png"
            )
    else:
        # Group chats start command
        # Check if the user is a group administrator
        from handlers.admin import is_user_admin
        is_admin = await is_user_admin(message)
        
        if is_admin:
            # Query group settings
            stmt = select(GroupSetting).where(GroupSetting.chat_id == message.chat.id)
            res = await db.execute(stmt)
            gs = res.scalar_one_or_none()
            if not gs:
                gs = GroupSetting(
                    chat_id=message.chat.id,
                    message_counter=0,
                    spawn_threshold=100,
                    enabled=True
                )
                db.add(gs)
                await db.commit()
                
            spawn_status = "Enabled 🟢" if gs.enabled else "Disabled 🔴"
            scribble_status = "Enabled 🟢" if is_scribble_enabled(message.chat.id) else "Disabled 🔴"
            nameguess_status = "Enabled 🟢" if is_nameguess_enabled(message.chat.id) else "Disabled 🔴"
            
            text = (
                f"⚙️ <b>POKÉEMPIRE ADMIN CONSOLE</b> ⚙️\n"
                f"───────────────────────────────\n"
                f"Welcome, Administrator <b>{escape_md(nickname)}</b>!\n\n"
                f"Configure the bot settings in this group:\n"
                f"• 🌳 Wild Spawns: <b>{spawn_status}</b>\n"
                f"• 📈 Spawn Frequency: every <b>{gs.spawn_threshold} messages</b>\n"
                f"• ✏️ Word Scribble: <b>{scribble_status}</b>\n"
                f"• 🖼️ Pokémon Nameguess: <b>{nameguess_status}</b>\n"
                f"───────────────────────────────"
            )
            
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="🔔 Toggle Spawns", callback_data=f"adm_toggle_spawns_{message.chat.id}"),
                InlineKeyboardButton(text="📈 Adjust Spawns", callback_data=f"adm_adjust_threshold_{message.chat.id}")
            )
            builder.row(
                InlineKeyboardButton(text="✏️ Toggle Scribble", callback_data=f"adm_toggle_scribble_{message.chat.id}"),
                InlineKeyboardButton(text="🖼️ Toggle Nameguess", callback_data=f"adm_toggle_nameguess_{message.chat.id}")
            )
            me = await message.bot.get_me()
            builder.row(InlineKeyboardButton(text="💬 Open Private DMs", url=f"https://t.me/{me.username}?start=help"))
            
            await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        else:
            # Generic member group welcome card
            me = await message.bot.get_me()
            welcome_text = (
                f"🌲 <b>POKÉEMPIRE ACTIVE</b> 🌲\n"
                f"───────────────\n\n"
                f"Start chatting in this group, and a wild Pokémon will eventually appear!\n\n"
                f"💬 <b>How to Play</b>:\n"
                f"• Catch wild spawns with <code>/catch &lt;name&gt;</code>\n"
                f"• Play Scramble & Guess the Pokémon games\n"
                f"• Earn coins to spend in the shop\n\n"
                f"👉 Click the buttons below to open private DMs or join our official group chat!"
            )
            builder = InlineKeyboardBuilder()
            builder.row(
                InlineKeyboardButton(text="💬 Open Private DMs", url=f"https://t.me/{me.username}?start=help"),
                InlineKeyboardButton(text="🌲 Union Group", url="https://t.me/pokeempireunion")
            )
            await message.answer(welcome_text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.message(Command("help"))
async def cmd_help(message: Message):
    help_text = (
        "❓ **POKÉEMPIRE GUIDE** ❓\n"
        "───────────────\n\n"
        "🌲 **Trainer Commands**:\n"
        "• `/profile` - View your Trainer level, coins, and titles.\n"
        "• `/pokemon <page>` - View your bag and paginated collection of caught Pokémon.\n"
        "• `/pokedex` - Review your caught species checklist & completion.\n"
        "• `/leaderboard` - Check the global leaderboard for coins and catches (alias `/lb`).\n"
        "• `/catch <name>` - Catch a wild Pokémon when one spawns in the group.\n"
        "• `/shop` - Purchase mystery boxes, Rare Candies, and Shiny Charms.\n"
        "• `/help` - Show this complete guide.\n\n"
        "🎮 **Earning Coins (Games)**:\n"
        "• `/daily` - Claim your daily reward (24h cooldown).\n"
        "• `/spin` - Spin the wheel of fortune (4h cooldown).\n"
        "• `/coinflip <amount> <heads/tails>` - Bet coins on a coin flip.\n"
        "• `/rps <amount> <rock/paper/scissors>` - Play rock-paper-scissors.\n"
        "• `/trivia` - Answer Pokémon questions for coins.\n"
        "• `/scribble` - Unscramble a Pokémon's name.\n\n"
        "🛡️ **Admin Group Commands**:\n"
        "• `/setspawn <threshold>` - Configure group spawn message threshold (Admins only).\n"
        "• `/toggle_spawns` - Enable or disable spawns in this group chat (Admins only)."
    )
    if message.chat.type == "private":
        await message.answer(help_text, reply_markup=get_back_to_hub_keyboard(), parse_mode="Markdown")
    else:
        await message.answer(help_text, parse_mode="Markdown")

@router.callback_query(F.data == "dm_home")
async def cb_dm_home(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id
    nickname = callback.from_user.first_name

    welcome_text = (
        f"🎮 **POKÉEMPIRE HUB** 🎮\n"
        f"👑 Welcome, Trainer **{escape_md(nickname)}**! 👑\n"
        f"───────────────\n\n"
        f"I spawn wild Pokémon in your active Telegram Groups based on message activity. "
        f"Be the first to guess their names and catch them!\n\n"
        f"Use the menu below to check your profile, view your caught Pokémon bag, browse the Pokédex checklist, or read the game guide.\n\n"
        f"👉 *Use the dashboard below to navigate:* "
    )
    # Check registration
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        user = User(
            id=user_id,
            username=callback.from_user.username,
            nickname=nickname
        )
        db.add(user)
        await db.commit()

    await callback.message.edit_text(welcome_text, reply_markup=get_dm_menu_keyboard(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "dm_profile")
async def cb_dm_profile(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id

    # Check registration
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        user = User(
            id=user_id,
            username=callback.from_user.username,
            nickname=callback.from_user.first_name
        )
        db.add(user)
        await db.commit()

    # Count total caught Pokémon
    count_stmt = select(func.count(UserPokemon.id)).where(UserPokemon.user_id == user_id)
    count_res = await db.execute(count_stmt)
    total_caught = count_res.scalar() or 0

    # Count unique caught Pokémon
    unique_stmt = select(func.count(distinct(UserPokemon.pokemon_id))).where(UserPokemon.user_id == user_id)
    unique_res = await db.execute(unique_stmt)
    unique_caught = unique_res.scalar() or 0

    # Count shiny Pokémon
    shiny_stmt = select(func.count(UserPokemon.id)).where(UserPokemon.user_id == user_id, UserPokemon.is_shiny == True)
    shiny_res = await db.execute(shiny_stmt)
    total_shiny = shiny_res.scalar() or 0

    # Count total species in database
    total_species_stmt = select(func.count(Pokemon.id))
    total_species_res = await db.execute(total_species_stmt)
    total_species = total_species_res.scalar() or 1

    # Calculate percentage
    dex_pct = (unique_caught / total_species) * 100
    dex_bar = get_progress_bar(unique_caught, total_species, 10, fill_char="▰", empty_char="▱")

    # Count caught by rarity
    rarity_stmt = select(Pokemon.rarity, func.count(UserPokemon.id)).join(UserPokemon).where(UserPokemon.user_id == user_id).group_by(Pokemon.rarity)
    rarity_res = await db.execute(rarity_stmt)
    rarity_counts = {r: count for r, count in rarity_res.all()}

    commons = rarity_counts.get("Common", 0)
    rares = rarity_counts.get("Rare", 0)
    epics = rarity_counts.get("Epic", 0)
    legendaries = rarity_counts.get("Legendary", 0)
    mythicals = rarity_counts.get("Mythical", 0)

    # Formatted coins
    formatted_coins = f"{user.coins:,}"
    user_nickname = user.nickname if (user and user.nickname) else (callback.from_user.first_name or "Trainer")

    # Calculate global rank position based on catches
    rank_stmt = (
        select(func.count())
        .select_from(
            select(User.id)
            .join(UserPokemon, UserPokemon.user_id == User.id)
            .group_by(User.id)
            .having(func.count(UserPokemon.id) > total_caught)
            .subquery()
        )
    )
    rank_res = await db.execute(rank_stmt)
    rank_position = (rank_res.scalar() or 0) + 1

    profile_card = (
        f"╭──「 🏆 Trainer Profile 」\n"
        f"├─➩ 🏓 User: {escape_md(user_nickname)}\n"
        f"├─➩ 🆔 ID: `{user.id}`\n"
        f"├─➩ 💰 Balance: `{formatted_coins} coins`\n"
        f"├─➩ ⚡ Pokémon: {unique_caught} (Total Catches: {total_caught})\n"
        f"├─➩ 🌍 Pokédex: {unique_caught}/{total_species} ({dex_pct:.3f}%)\n"
        f"├─➩ 🎁 Progress:\n"
        f"╰         {dex_bar}\n\n"
        f"╭─ Rarity Breakdown ─\n"
        f"├─➩ ⚪️ Common: {commons}\n"
        f"├─➩ 🔵 Rare: {rares}\n"
        f"├─➩ 🟣 Epic: {epics}\n"
        f"├─➩ 🟡 Legendary: {legendaries}\n"
        f"├─➩ 🌌 Mythical: {mythicals}\n"
        f"├─➩ ✨ Shiny: {total_shiny}\n"
        f"╰───────────────────\n\n"
        f"╭─ Global Rank ─\n"
        f"├─➩ 🏆 Position: #{rank_position}\n"
        f"╰───────────────────"
    )

    await callback.message.edit_text(profile_card, reply_markup=get_back_to_hub_keyboard(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data == "dm_help")
async def cb_dm_help(callback: CallbackQuery):
    help_text = (
        "❓ **POKÉEMPIRE GUIDE** ❓\n"
        "───────────────\n\n"
        "🌲 **Trainer Commands**:\n"
        "• `/profile` - View your Trainer level, coins, and titles.\n"
        "• `/pokemon <page>` - View your bag and paginated collection of caught Pokémon.\n"
        "• `/pokedex` - Review your caught species checklist & completion.\n"
        "• `/leaderboard` - Check the global leaderboard for coins and catches (alias `/lb`).\n"
        "• `/catch <name>` - Catch a wild Pokémon when one spawns in the group.\n"
        "• `/shop` - Purchase mystery boxes, Rare Candies, and Shiny Charms.\n"
        "• `/help` - Show this complete guide.\n\n"
        "🎮 **Earning Coins (Games)**:\n"
        "• `/daily` - Claim your daily reward (24h cooldown).\n"
        "• `/spin` - Spin the wheel of fortune (4h cooldown).\n"
        "• `/coinflip <amount> <heads/tails>` - Bet coins on a coin flip.\n"
        "• `/rps <amount> <rock/paper/scissors>` - Play rock-paper-scissors.\n"
        "• `/trivia` - Answer Pokémon questions for coins.\n"
        "• `/scribble` - Unscramble a Pokémon's name.\n\n"
        "🛡️ **Admin Group Commands**:\n"
        "• `/setspawn <threshold>` - Configure group spawn message threshold (Admins only).\n"
        "• `/toggle_spawns` - Enable or disable spawns in this group chat (Admins only).\n\n"
        "🎮 **Interactive Hub**: Use the buttons here to explore your trainer collection instantly!"
    )
    await callback.message.edit_text(help_text, reply_markup=get_back_to_hub_keyboard(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("dm_dex_"))
async def cb_dm_dex(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id
    
    # Parse page number
    try:
        page = int(callback.data.split("_")[2])
    except (IndexError, ValueError):
        page = 1

    # Count total species in database
    total_stmt = select(func.count(Pokemon.id))
    total_res = await db.execute(total_stmt)
    total_species = total_res.scalar() or 1

    # Count unique species caught by user
    caught_count_stmt = select(func.count(distinct(UserPokemon.pokemon_id))).where(UserPokemon.user_id == user_id)
    caught_count_res = await db.execute(caught_count_stmt)
    caught_count = caught_count_res.scalar() or 0

    # Get nickname
    u_stmt = select(User).where(User.id == user_id)
    u_res = await db.execute(u_stmt)
    user = u_res.scalar_one_or_none()
    nickname = user.nickname if (user and user.nickname) else (callback.from_user.first_name or "Trainer")

    if caught_count == 0:
        text = (
            f"👑 **{escape_md(nickname)}'s Pokédex** 👑\n"
            f"───────────────\n\n"
            f"⚠️ **Your Pokédex is empty!**\n"
            f"Catch wild Pokémon in a group chat first to register them in your Pokédex."
        )
        await callback.message.edit_text(text, reply_markup=get_back_to_hub_keyboard(), parse_mode="Markdown")
        await callback.answer()
        return

    per_page = 15
    max_page = (caught_count + per_page - 1) // per_page
    if page < 1: page = 1
    if page > max_page: page = max_page

    offset = (page - 1) * per_page

    # Query unique caught species sorted by ID for the current page
    poke_stmt = (
        select(
            Pokemon,
            func.count(UserPokemon.id).label("total_caught"),
            func.max(case((UserPokemon.is_shiny == True, 1), else_=0)).label("has_shiny")
        )
        .join(UserPokemon)
        .where(UserPokemon.user_id == user_id)
        .group_by(Pokemon.id)
        .order_by(Pokemon.id)
        .offset(offset)
        .limit(per_page)
    )
    poke_res = await db.execute(poke_stmt)
    pairs = poke_res.all()

    # Query stats per generation
    gen_stats_stmt = (
        select(Pokemon.generation, func.count(distinct(UserPokemon.pokemon_id)))
        .join(UserPokemon)
        .where(UserPokemon.user_id == user_id)
        .group_by(Pokemon.generation)
    )
    gen_stats_res = await db.execute(gen_stats_stmt)
    gen_stats = {gen: count for gen, count in gen_stats_res.all()}

    gen_totals_stmt = select(Pokemon.generation, func.count(Pokemon.id)).group_by(Pokemon.generation)
    gen_totals_res = await db.execute(gen_totals_stmt)
    gen_totals = {gen: count for gen, count in gen_totals_res.all()}

    # Determine Pokedex Cover Image
    from utils.favorite import get_favorite_id
    fav_id = get_favorite_id(user_id)
    cover_image = None
    if fav_id:
        fav_stmt = select(Pokemon.image_url).join(UserPokemon, UserPokemon.pokemon_id == Pokemon.id).where(Pokemon.id == fav_id, UserPokemon.user_id == user_id)
        fav_res = await db.execute(fav_stmt)
        cover_image = fav_res.scalar_one_or_none()
    
    if not cover_image:
        rand_stmt = select(Pokemon.image_url).join(UserPokemon, UserPokemon.pokemon_id == Pokemon.id).where(UserPokemon.user_id == user_id).order_by(func.random()).limit(1)
        rand_res = await db.execute(rand_stmt)
        cover_image = rand_res.scalar_one_or_none()

    percent = int((caught_count / total_species) * 100)
    bar = get_progress_bar(caught_count, total_species, 10, fill_char="█", empty_char="░")

    cover_link = f"[​]({cover_image})" if cover_image else ""
    text = (
        f"{cover_link}"
        f"👑 **{escape_md(nickname)}'s Pokédex** 👑 — Page {page}/{max_page}\n"
        f"Completion: **{caught_count}/{total_species}** species (**{percent}%**)\n"
        f"`[{bar}]` 🔴\n"
        f"───────────────\n"
    )

    current_gen = None
    rarity_badges = {
        "Common": "⚪️",
        "Rare": "🔵",
        "Epic": "🟣",
        "Legendary": "🟡",
        "Mythical": "🌌"
    }

    for p, total, has_shiny in pairs:
        if p.generation != current_gen:
            current_gen = p.generation
            text += f"\n**Generation {current_gen}** {gen_stats.get(current_gen, 0)}/{gen_totals.get(current_gen, 0)}\n"
            
        badge = rarity_badges.get(p.rarity, "⚪️")
        shiny_tag = " [✨]" if has_shiny else ""
        text += f"◈⌠{badge}⌡ #{p.id:03d} {p.name.title()}{shiny_tag} ×{total}\n"

    text += "\n───────────────"

    await callback.message.edit_text(text, reply_markup=get_dex_pagination_keyboard(page, max_page), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("dm_bag_"))
async def cb_dm_bag(callback: CallbackQuery, db: AsyncSession):
    text = (
        "🎒 **The Pokémon Bag is now retired!**\n"
        "All collections are managed directly via your Pokédex.\n\n"
        "👉 Use `/pokedex` to view your collection checklist and progress!"
    )
    await callback.message.edit_text(text, reply_markup=get_back_to_hub_keyboard(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("dm_detail_"))
async def cb_dm_detail(callback: CallbackQuery, db: AsyncSession):
    text = (
        "🎒 **The Pokémon Bag is now retired!**\n"
        "All collections are managed directly via your Pokédex.\n\n"
        "👉 Use `/pokedex` to view your collection checklist and progress!"
    )
    await callback.message.edit_text(text, reply_markup=get_back_to_hub_keyboard(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("dm_rename_"))
async def cb_dm_rename(callback: CallbackQuery):
    await callback.answer("❌ Rename is disabled (Pokémon Bag is retired).", show_alert=True)

@router.callback_query(F.data.startswith("dm_release_"))
async def cb_dm_release(callback: CallbackQuery, db: AsyncSession):
    await callback.answer("❌ Release is disabled (Pokémon Bag is retired).", show_alert=True)

@router.callback_query(F.data.startswith("dm_train_"))
async def cb_dm_train(callback: CallbackQuery, db: AsyncSession):
    await callback.answer("❌ Training from the bag is disabled (Pokémon Bag is retired).", show_alert=True)

@router.callback_query(F.data.startswith("bat_"))
async def cb_battle_action(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id
    if user_id not in active_battles:
        await callback.answer("❌ No active battle session.", show_alert=True)
        return

    parts = callback.data.split("_")
    action = parts[1]  # atk, def, run
    up_id = int(parts[2])
    page = int(parts[3])

    battle = active_battles[user_id]
    
    if action == "run":
        del active_battles[user_id]
        text = (
            f"🏃 **SURRENDERED** 🏃\n"
            f"───────────────\n\n"
            f"You surrendered and fled safely from wild **{battle['wild_name']}**.\n"
            f"───────────────"
        )
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Back to Pokémon Detail", callback_data=f"dm_detail_{up_id}_{page}"))
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        await callback.answer("Escaped!")
        return

    # Fetch User & Pokémon
    stmt = select(UserPokemon, Pokemon).join(Pokemon).where(UserPokemon.id == up_id)
    res = await db.execute(stmt)
    pair = res.first()

    if not pair:
        del active_battles[user_id]
        await callback.answer("❌ Pokémon not found.", show_alert=True)
        return

    up, p = pair
    level = up.level

    user_defending = action == "def"
    wild_defending = random.choice([True, False]) if battle["turn"] > 1 else False # wild has a chance to defend

    # Calculate damage formula helper
    def deal_dmg(atk_val, def_val, is_defending):
        base_dmg = (((2 * level // 5 + 2) * atk_val * 40 // def_val) // 50) + random.randint(2, 5)
        if is_defending:
            base_dmg = base_dmg // 2
        return max(1, base_dmg)

    logs = []
    
    # Order turns based on speed
    if battle["user_mon_spd"] >= battle["wild_spd"]:
        # User goes first
        if not user_defending:
            dmg = deal_dmg(battle["user_mon_atk"], battle["wild_def"], wild_defending)
            battle["wild_hp"] = max(0, battle["wild_hp"] - dmg)
            logs.append(f"💥 {battle['user_mon_name']} attacked wild {battle['wild_name']} for {dmg} damage!")
        else:
            logs.append(f"🛡️ {battle['user_mon_name']} braced for impact (defending)!")

        # Wild responds if alive
        if battle["wild_hp"] > 0:
            if not wild_defending:
                dmg = deal_dmg(battle["wild_atk"], battle["user_mon_def"], user_defending)
                battle["user_mon_hp"] = max(0, battle["user_mon_hp"] - dmg)
                logs.append(f"💥 Wild {battle['wild_name']} hit {battle['user_mon_name']} for {dmg} damage!")
            else:
                logs.append(f"🛡️ Wild {battle['wild_name']} is defending!")
    else:
        # Wild goes first
        if not wild_defending:
            dmg = deal_dmg(battle["wild_atk"], battle["user_mon_def"], user_defending)
            battle["user_mon_hp"] = max(0, battle["user_mon_hp"] - dmg)
            logs.append(f"💥 Wild {battle['wild_name']} hit {battle['user_mon_name']} for {dmg} damage!")
        else:
            logs.append(f"🛡️ Wild {battle['wild_name']} is defending!")

        # User responds if alive
        if battle["user_mon_hp"] > 0:
            if not user_defending:
                dmg = deal_dmg(battle["user_mon_atk"], battle["wild_def"], wild_defending)
                battle["wild_hp"] = max(0, battle["wild_hp"] - dmg)
                logs.append(f"💥 {battle['user_mon_name']} attacked wild {battle['wild_name']} for {dmg} damage!")
            else:
                logs.append(f"🛡️ {battle['user_mon_name']} braced for impact (defending)!")

    battle["turn"] += 1
    battle["log"] = "\n".join(logs)

    # Check outcomes
    if battle["wild_hp"] <= 0:
        # Victory!
        del active_battles[user_id]
        
        # Award XP & Coins
        xp_gain = random.randint(30, 60) * level
        coins_gain = random.randint(20, 50)
        
        up.xp += xp_gain
        xp_needed = level * 100
        
        # Fetch user from DB
        user_stmt = select(User).where(User.id == user_id)
        user_res = await db.execute(user_stmt)
        user = user_res.scalar_one()
        user.coins += coins_gain
        
        lvl_up_text = ""
        if up.xp >= xp_needed:
            up.level += 1
            up.xp = 0
            lvl_up_text = f"🌟 **LEVEL UP!** 🌟\n**{battle['user_mon_name']}** reached **Lvl {up.level}**!\n"
            
        await db.commit()

        victory_text = (
            f"🏆 **BATTLE VICTORY** 🏆\n"
            f"───────────────\n\n"
            f"🎉 **{battle['user_mon_name']}** defeated wild **{battle['wild_name']}**!\n\n"
            f"📈 **Rewards**:\n"
            f"• Experience: **+{xp_gain} XP**\n"
            f"• Coins earned: `💰 +{coins_gain} coins`\n"
            f"• New Balance: `💰 {user.coins} coins`\n\n"
            f"{lvl_up_text}"
            f"───────────────"
        )

        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Return to Pokémon Detail", callback_data=f"dm_detail_{up_id}_{page}"))
        await callback.message.edit_text(victory_text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        await callback.answer("Victory!")
        return

    elif battle["user_mon_hp"] <= 0:
        # Defeat!
        del active_battles[user_id]
        defeat_text = (
            f"💀 **BATTLE DEFEAT** 💀\n"
            f"───────────────\n\n"
            f"💀 **{battle['user_mon_name']}** fainted in battle against wild **{battle['wild_name']}**.\n\n"
            f"Train your Pokémon more or feed them Rare Candy to grow stronger!\n"
            f"───────────────"
        )
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Return to Pokémon Detail", callback_data=f"dm_detail_{up_id}_{page}"))
        await callback.message.edit_text(defeat_text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        await callback.answer("Defeated!")
        return

    # Update turn details
    hp_bar_user = get_hp_bar(battle['user_mon_hp'], battle['user_mon_hp_max'])
    hp_bar_wild = get_hp_bar(battle['wild_hp'], battle['wild_hp_max'])
    text = (
        f"⚔️ **BATTLE: TURN {battle['turn']}** ⚔️\n"
        f"───────────────\n\n"
        f"Trainer's **{battle['user_mon_name']}** `(Lvl {level})`\n"
        f"{hp_bar_user}\n\n"
        f"Wild **{battle['wild_name']}** `(Lvl {level})`\n"
        f"{hp_bar_wild}\n\n"
        f"───────────────\n"
        f"💬 **Log**:\n{battle['log']}\n"
        f"───────────────"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="⚔️ Attack", callback_data=f"bat_atk_{up_id}_{page}"),
        InlineKeyboardButton(text="🛡️ Defend", callback_data=f"bat_def_{up_id}_{page}")
    )
    builder.row(
        InlineKeyboardButton(text="🏃 Run", callback_data=f"bat_run_{up_id}_{page}")
    )

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

def is_renaming(message: Message) -> bool:
    return message.from_user.id in active_renames

@router.message(F.chat.type == "private", F.text, ~F.text.startswith("/"), is_renaming)
async def check_dm_text_messages(message: Message, db: AsyncSession):
    user_id = message.from_user.id
    session_data = active_renames[user_id]
    new_name = message.text.strip()
    
    if len(new_name) > 15:
        await message.answer("⚠️ Nickname must be 15 characters or less. Try again:")
        return
        
    up_id = session_data["up_id"]
    page = session_data["page"]
    
    # Update nickname in DB
    stmt = select(UserPokemon).where(UserPokemon.id == up_id)
    res = await db.execute(stmt)
    up = res.scalar_one_or_none()
    
    if up:
        up.nickname = new_name
        await db.commit()
        
        # Remove from active rename session
        del active_renames[user_id]
        
        builder = InlineKeyboardBuilder()
        builder.row(InlineKeyboardButton(text="🔙 Back to Pokémon Detail", callback_data=f"dm_detail_{up_id}_{page}"))
        await message.answer(f"✅ Nickname updated to **{escape_md(new_name)}** successfully!", reply_markup=builder.as_markup(), parse_mode="Markdown")
    else:
        del active_renames[user_id]
        await message.answer("❌ Error: Pokémon not found.")
    return

@router.message(Command("ping"))
async def cmd_ping(message: Message):
    import time
    from datetime import datetime, timezone
    
    start_time = time.time()
    sent_message = await message.answer("🏓 **Pinging...**", parse_mode="Markdown")
    latency_ms = int((time.time() - start_time) * 1000)
    
    transit_latency = int((datetime.now(timezone.utc) - message.date).total_seconds() * 1000)
    
    text = (
        f"🏓 **PONG!** 🏓\n"
        f"───────────────\n"
        f"📡 **API Latency**: `{latency_ms}ms`\n"
        f"⚡ **Transit Latency**: `{max(0, transit_latency)}ms`\n"
        f"───────────────"
    )
    await sent_message.edit_text(text, parse_mode="Markdown")

@router.message(F.new_chat_members)
async def on_new_chat_members(message: Message):
    # Check if the bot itself is in the new chat members list
    bot_user = await message.bot.get_me()
    if any(member.id == bot_user.id for member in message.new_chat_members):
        welcome_text = (
            f"🎮 **POKÉEMPIRE ACTIVATED** 🎮\n"
            f"───────────────\n\n"
            f"Hello everyone! I am **PokéEmpire Bot**, and I have just joined this group. 🌲\n\n"
            f"I spawn wild Pokémon in this chat based on message activity. "
            f"The first player to guess their name and use `/catch <name>` catches them!\n\n"
            f"⚙️ **Default Settings**:\n"
            f"• Spawns are **Enabled**.\n"
            f"• Spawn interval is initialized randomly (every 50-100 messages).\n\n"
            f"🛡️ **Admin Group Commands**:\n"
            f"• `/setspawn <threshold>` - Configure group spawn message threshold.\n"
            f"• `/toggle_spawns` - Enable/Disable spawns in this group.\n"
            f"• `/spawnsetting` - Check current spawn status and progress.\n\n"
            f"👤 **Player Commands**:\n"
            f"• `/help` - Show the complete game guide.\n"
            f"• `/leaderboard` (or `/lb`) - Check global rankings.\n\n"
            f"👉 Chat here to start triggering spawns, or message me in private DMs to check your profile, bag, and shop!"
        )
        await message.answer(welcome_text, parse_mode="Markdown")


# -------------------------------------------------------------
# Bot Owner & Group Admin Dashboard Callbacks / Commands
# -------------------------------------------------------------

@router.callback_query(F.data == "owner_tools")
async def cb_owner_tools(callback: CallbackQuery):
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("❌ Denied. Owner only.", show_alert=True)
        return
        
    text = (
        f"🛠️ <b>POKÉEMPIRE OWNER CONSOLE</b> 🛠️\n"
        f"───────────────\n\n"
        f"<b>🖼️ Cover Media</b>\n"
        f"• <code>/setcover start</code> — Set start screen cover\n"
        f"• <code>/setcover xo</code> — Set XO game cover\n"
        f"• <code>/setcover pokedex</code> — Set Pokédex cover\n"
        f"• <code>/resetcover &lt;key&gt;</code> — Reset to default\n\n"
        f"<b>🎁 Gifts</b>\n"
        f"• <code>/giftcoins @user &lt;amount&gt;</code> — Give coins\n"
        f"• <code>/giftpokemon @user &lt;name&gt; [shiny] [amv]</code> — Gift Pokémon\n\n"
        f"<b>🎫 Redeem Codes</b>\n"
        f"• <code>/createredeem &lt;code&gt; &lt;limit&gt; &lt;coins/pokemon&gt; [shiny] [amv]</code>\n\n"
        f"<b>🎨 Pokémon Media</b>\n"
        f"• <code>/setpokemedia &lt;name or id&gt;</code> — Set photo/AMV for a Pokémon\n"
        f"• <code>/medialist</code> — View file IDs of custom covers & Pokémon media\n\n"
        f"<b>⚙️ Spawn Controls</b>\n"
        f"• <code>/spawnchance</code> — View/set rarity rates\n"
        f"• <code>/spawn</code> — Force a manual spawn\n"
        f"• <code>/setspawn &lt;chat_id&gt; &lt;threshold&gt;</code> — Set spawn rate\n\n"
        f"<b>👑 Admin Management</b>\n"
        f"• <code>/makeadmin @user</code> — Grant admin\n"
        f"• <code>/removeadmin @user</code> — Revoke admin\n"
        f"• <code>/adminlist</code> — List all admins"
    )
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🖼️ Set Start Cover", callback_data="owner_setcover_start"),
        InlineKeyboardButton(text="🎮 Set XO Cover", callback_data="owner_setcover_xo")
    )
    builder.row(
        InlineKeyboardButton(text="📖 Set Pokédex Cover", callback_data="owner_setcover_pokedex"),
        InlineKeyboardButton(text="📊 Spawn Rates", callback_data="owner_spawnchance")
    )
    builder.row(
        InlineKeyboardButton(text="📋 View Media IDs", callback_data="owner_medialist"),
        InlineKeyboardButton(text="🔙 Back to Menu", callback_data="dm_home")
    )
    await callback.message.edit_caption(caption=text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("owner_setcover_"))
async def cb_owner_setcover(callback: CallbackQuery):
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("❌ Denied. Owner only.", show_alert=True)
        return
    key = callback.data.replace("owner_setcover_", "")
    active_cover_updates[callback.from_user.id] = key
    await callback.answer(f"Ready! Now send the photo/video for '{key}' cover.", show_alert=True)

@router.callback_query(F.data == "owner_spawnchance")
async def cb_owner_spawnchance(callback: CallbackQuery):
    if callback.from_user.id not in config.ADMIN_IDS:
        await callback.answer("❌ Denied. Owner only.", show_alert=True)
        return
    from utils.settings import get_spawn_settings
    settings = get_spawn_settings()
    probs = settings.get("group_rarity_probabilities", {})
    text = (
        f"📊 <b>Current Spawn Rates</b>\n"
        f"───────────────\n"
    )
    for rarity, chance in probs.items():
        text += f"• {rarity.title()}: <code>{chance*100:.1f}%</code>\n"
    text += f"\nUse <code>/spawnchance</code> in DM to modify rates."
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔙 Back to Owner Tools", callback_data="owner_tools"))
    await callback.message.edit_caption(caption=text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

@router.message(Command("setcover"))
async def cmd_set_cover(message: Message):
    if message.chat.type != "private":
        await message.answer("⚠️ This command can only be used in private DMs.")
        return
        
    if message.from_user.id not in config.ADMIN_IDS:
        await message.answer("❌ Denied. Only the bot owner can configure covers.")
        return
        
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("⚠️ Format: `/setcover <start/xo/pokedex> [file_id]`")
        return
        
    key = parts[1].lower()
    if key not in ["start", "xo", "pokedex"]:
        await message.answer("❌ Invalid cover key. Choose `start`, `xo`, or `pokedex`.")
        return
        
    if len(parts) >= 3:
        file_id = parts[2]
        media_type = "video" if file_id.startswith("BAA") else "photo"
        await set_custom_cover(key, media_type, file_id)
        await message.answer(f"✅ <b>Success!</b> Cover media for <code>{key}</code> has been updated to this custom {media_type} using the provided ID.", parse_mode="HTML")
        return
        
    active_cover_updates[message.from_user.id] = key
    await message.answer(f"📷 <b>Ready!</b> Send the photo, video, or animation (GIF) you want to use as the cover for <code>{key}</code>.", parse_mode="HTML")

@router.message(Command("resetcover"))
async def cmd_reset_cover(message: Message):
    if message.from_user.id not in config.ADMIN_IDS:
        await message.answer("❌ Denied. Only the bot owner can configure covers.")
        return
        
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("⚠️ Format: `/resetcover <start/xo/pokedex>`")
        return
        
    key = parts[1].lower()
    if key not in ["start", "xo", "pokedex"]:
        await message.answer("❌ Invalid cover key. Choose `start`, `xo`, or `pokedex`.")
        return
        
    await delete_custom_cover(key)
    await message.answer(f"✅ Cover for <code>{key}</code> has been reset to default.", parse_mode="HTML")

# Owner cover media receiver
@router.message(F.chat.type == "private", F.from_user.id.in_(config.ADMIN_IDS), lambda msg: msg.from_user.id in active_cover_updates)
async def on_owner_media_received(message: Message):
    user_id = message.from_user.id
    key = active_cover_updates.pop(user_id, None)
    if not key:
        return
        
    media_type = None
    media_value = None
    
    if message.photo:
        media_type = "photo"
        media_value = message.photo[-1].file_id
    elif message.video:
        media_type = "video"
        media_value = message.video.file_id
    elif message.animation:
        media_type = "animation"
        media_value = message.animation.file_id
        
    if not media_type:
        await message.answer("❌ Invalid message type. Please send a photo, video, or animation (GIF) to update the cover.")
        # Restore state so they can try again
        active_cover_updates[user_id] = key
        return
        
    await set_custom_cover(key, media_type, media_value)
    await message.answer(f"✅ <b>Success!</b> The cover media for <code>{key}</code> has been updated to this {media_type}.", parse_mode="HTML")

# Group Admin Settings Console Callbacks
async def check_admin_cb(callback: CallbackQuery, chat_id: int) -> bool:
    user_id = callback.from_user.id
    if user_id in config.ADMIN_IDS:
        return True
    try:
        member = await callback.bot.get_chat_member(chat_id=chat_id, user_id=user_id)
        if member.status in ["creator", "administrator"]:
            return True
    except Exception:
        pass
    await callback.answer("❌ Denied. Only group administrators can edit configurations.", show_alert=True)
    return False

async def refresh_admin_console(callback: CallbackQuery, chat_id: int, db: AsyncSession):
    stmt = select(GroupSetting).where(GroupSetting.chat_id == chat_id)
    res = await db.execute(stmt)
    gs = res.scalar_one_or_none()
    if not gs:
        gs = GroupSetting(chat_id=chat_id, spawn_threshold=100, enabled=True)
        db.add(gs)
        await db.commit()
        
    spawn_status = "Enabled 🟢" if gs.enabled else "Disabled 🔴"
    scribble_status = "Enabled 🟢" if is_scribble_enabled(chat_id) else "Disabled 🔴"
    nameguess_status = "Enabled 🟢" if is_nameguess_enabled(chat_id) else "Disabled 🔴"
    
    # Try to fetch chat title
    try:
        chat = await callback.bot.get_chat(chat_id)
        group_name = chat.title
    except Exception:
        group_name = "this group"

    text = (
        f"⚙️ <b>POKÉEMPIRE ADMIN CONSOLE</b> ⚙️\n"
        f"───────────────────────────────\n"
        f"Configure the bot settings in group <b>{escape_md(group_name)}</b>:\n"
        f"• 🌳 Wild Spawns: <b>{spawn_status}</b>\n"
        f"• 📈 Spawn Frequency: every <b>{gs.spawn_threshold} messages</b>\n"
        f"• ✏️ Word Scribble: <b>{scribble_status}</b>\n"
        f"• 🖼️ Pokémon Nameguess: <b>{nameguess_status}</b>\n"
        f"───────────────────────────────"
    )
    
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="🔔 Toggle Spawns", callback_data=f"adm_toggle_spawns_{chat_id}"),
        InlineKeyboardButton(text="📈 Adjust Spawns", callback_data=f"adm_adjust_threshold_{chat_id}")
    )
    builder.row(
        InlineKeyboardButton(text="✏️ Toggle Scribble", callback_data=f"adm_toggle_scribble_{chat_id}"),
        InlineKeyboardButton(text="🖼️ Toggle Nameguess", callback_data=f"adm_toggle_nameguess_{chat_id}")
    )
    me = await callback.bot.get_me()
    builder.row(InlineKeyboardButton(text="💬 Open Private DMs", url=f"https://t.me/{me.username}?start=help"))
    
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")

@router.callback_query(F.data.startswith("adm_toggle_spawns_"))
async def cb_adm_toggle_spawns(callback: CallbackQuery, db: AsyncSession):
    chat_id = int(callback.data.replace("adm_toggle_spawns_", ""))
    if not await check_admin_cb(callback, chat_id):
        return
        
    stmt = select(GroupSetting).where(GroupSetting.chat_id == chat_id)
    res = await db.execute(stmt)
    gs = res.scalar_one_or_none()
    if gs:
        gs.enabled = not gs.enabled
        await db.commit()
        await callback.answer(f"Spawns {'enabled' if gs.enabled else 'disabled'}.")
        await refresh_admin_console(callback, chat_id, db)

@router.callback_query(F.data.startswith("adm_adjust_threshold_"))
async def cb_adm_adjust_threshold(callback: CallbackQuery, db: AsyncSession):
    chat_id = int(callback.data.replace("adm_adjust_threshold_", ""))
    if not await check_admin_cb(callback, chat_id):
        return
        
    stmt = select(GroupSetting).where(GroupSetting.chat_id == chat_id)
    res = await db.execute(stmt)
    gs = res.scalar_one_or_none()
    if gs:
        # Loop threshold values: 30, 50, 75, 100, 150, 200, 300
        thresholds = [30, 50, 75, 100, 150, 200, 300]
        curr = gs.spawn_threshold
        try:
            next_idx = (thresholds.index(curr) + 1) % len(thresholds)
        except ValueError:
            next_idx = 3 # fallback to 100
        gs.spawn_threshold = thresholds[next_idx]
        await db.commit()
        await callback.answer(f"Spawn threshold set to {gs.spawn_threshold} messages.")
        await refresh_admin_console(callback, chat_id, db)

@router.callback_query(F.data.startswith("adm_toggle_scribble_"))
async def cb_adm_toggle_scribble(callback: CallbackQuery, db: AsyncSession):
    chat_id = int(callback.data.replace("adm_toggle_scribble_", ""))
    if not await check_admin_cb(callback, chat_id):
        return
        
    from utils.settings import is_scribble_enabled, set_scribble_status
    curr = is_scribble_enabled(chat_id)
    await set_scribble_status(chat_id, not curr)
    await callback.answer(f"Scribble {'enabled' if not curr else 'disabled'}.")
    await refresh_admin_console(callback, chat_id, db)

@router.callback_query(F.data.startswith("adm_toggle_nameguess_"))
async def cb_adm_toggle_nameguess(callback: CallbackQuery, db: AsyncSession):
    chat_id = int(callback.data.replace("adm_toggle_nameguess_", ""))
    if not await check_admin_cb(callback, chat_id):
        return
        
    from utils.settings import is_nameguess_enabled, set_nameguess_status
    curr = is_nameguess_enabled(chat_id)
    await set_nameguess_status(chat_id, not curr)
    await callback.answer(f"Nameguess {'enabled' if not curr else 'disabled'}.")
    await refresh_admin_console(callback, chat_id, db)

