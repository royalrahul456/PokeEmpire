from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import config
from database.models import GroupSetting, User, Pokemon, UserPokemon, ActiveSpawn
from utils.formatters import get_progress_bar, get_rarity_emoji, escape_md

router = Router()

def parse_stored_media_value(media_value: str | None) -> tuple[str, str | None]:
    if not media_value:
        return "photo", None
    if ":" in media_value:
        media_type, clean_value = media_value.split(":", 1)
        if media_type in {"photo", "video", "animation"}:
            return media_type, clean_value
    if media_value.startswith("http"):
        return "photo", media_value
    return "video", media_value

async def get_single_form_media_value(db: AsyncSession, pokemon_id: int, form_index: int) -> str | None:
    if form_index <= 0:
        return None

    from database.models import PokemonFormMedia

    stmt = select(PokemonFormMedia.media_value).where(
        PokemonFormMedia.pokemon_id == pokemon_id,
        PokemonFormMedia.form_index == form_index,
    ).limit(1)
    res = await db.execute(stmt)
    return res.scalar_one_or_none()

async def is_user_admin(message: Message) -> bool:
    """Helper to check if the user is a bot administrator or a group administrator."""
    # Global bot admins bypass checks
    if message.from_user and message.from_user.id in config.ADMIN_IDS:
        return True

    # Private chat actions are allowed
    if message.chat.type == "private":
        return True

    # Check for Anonymous Group Admins / Linked channel postings
    if message.sender_chat and message.sender_chat.id == message.chat.id:
        return True
    if message.from_user and message.from_user.id in [1087788165, 777000]:
        return True

    # Check Telegram group administrator rights
    try:
        if not message.from_user:
            return False
        member = await message.bot.get_chat_member(chat_id=message.chat.id, user_id=message.from_user.id)
        return member.status in ["creator", "administrator"]
    except Exception:
        return False

@router.message(Command("setspawn"))
async def cmd_set_spawn(message: Message, db: AsyncSession):
    chat_id = message.chat.id

    # Enforce admin authorization
    if not await is_user_admin(message):
        await message.answer("❌ Denied. Only group administrators can configure settings.")
        return

    # Check arguments
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.answer("⚠️ Format: `/setspawn <number_of_messages>` (e.g. `/setspawn 75`)")
        return

    threshold = int(parts[1])
    if threshold < 30 or threshold > 300:
        await message.answer("⚠️ Threshold must be between 30 and 300 messages.")
        return

    # Query or create GroupSetting
    stmt = select(GroupSetting).where(GroupSetting.chat_id == chat_id)
    res = await db.execute(stmt)
    setting = res.scalar_one_or_none()

    if not setting:
        setting = GroupSetting(
            chat_id=chat_id,
            message_counter=0,
            spawn_threshold=threshold,
            enabled=True
        )
        db.add(setting)
    else:
        setting.spawn_threshold = threshold

    await db.commit()

    # Sync to group monitor cache
    from utils.group_monitor import group_settings_cache
    group_settings_cache[chat_id] = {
        "spawn_threshold": threshold,
        "enabled": setting.enabled
    }

    await message.answer(f"⚙️ **Configured!** Spawns will occur every **{threshold} messages** in this chat.")

@router.message(Command("toggle_spawns"))
@router.message(Command("toggle"))
async def cmd_toggle_spawns(message: Message, db: AsyncSession):
    chat_id = message.chat.id

    # Enforce admin authorization
    if not await is_user_admin(message):
        await message.answer("❌ Denied. Only group administrators can toggle settings.")
        return

    # Query or create GroupSetting
    stmt = select(GroupSetting).where(GroupSetting.chat_id == chat_id)
    res = await db.execute(stmt)
    setting = res.scalar_one_or_none()

    if not setting:
        setting = GroupSetting(
            chat_id=chat_id,
            message_counter=0,
            spawn_threshold=100,
            enabled=False  # Toggle turns off if creating new
        )
        db.add(setting)
    else:
        setting.enabled = not setting.enabled

    await db.commit()

    # Sync to group monitor cache
    from utils.group_monitor import group_settings_cache
    group_settings_cache[chat_id] = {
        "spawn_threshold": setting.spawn_threshold,
        "enabled": setting.enabled
    }

    if setting.enabled:
        await message.answer("🌲 **Spawns Enabled!** Wild Pokémon will now spawn in this group chat.")
    else:
        await message.answer("🚫 **Spawns Disabled.** Spawning has been turned off for this group chat.")

@router.message(Command("adminlist", "admins"))
async def cmd_admin_list(message: Message, db: AsyncSession):
    if not config.ADMIN_IDS:
        await message.answer("ℹ️ **Bot Administrators**: None configured.")
        return

    # Query database for matching registered bot admins & uploaders
    all_ids = list(set(config.ADMIN_IDS + config.UPLOADER_IDS))
    stmt = select(User).where(User.id.in_(all_ids))
    res = await db.execute(stmt)
    registered_users = res.scalars().all()
    registered_ids = {u.id: u for u in registered_users}

    owner_row = None
    admin_rows = []
    uploader_rows = []

    # We treat the first ID in config.ADMIN_IDS as the Bot Owner, the rest as Administrators
    for idx, admin_id in enumerate(config.ADMIN_IDS):
        nickname = None
        username = None

        if admin_id in registered_ids:
            u = registered_ids[admin_id]
            nickname = u.nickname
            username = u.username
        else:
            # Try to fetch from Telegram directly to get the current profile name/username
            try:
                chat = await message.bot.get_chat(admin_id)
                nickname = chat.first_name
                username = chat.username
            except Exception:
                pass

        if nickname:
            username_str = f" (@{escape_md(username)})" if username else ""
            row = f"• **{escape_md(nickname)}**{username_str} `(ID: {admin_id})`"
        else:
            row = f"• **Admin User** `(ID: {admin_id}, Unregistered)`"

        if idx == 0:
            owner_row = row
        else:
            admin_rows.append(row)

    # Build uploader rows
    for up_id in config.UPLOADER_IDS:
        nickname = None
        username = None
        if up_id in registered_ids:
            u = registered_ids[up_id]
            nickname = u.nickname
            username = u.username
        else:
            try:
                chat = await message.bot.get_chat(up_id)
                nickname = chat.first_name
                username = chat.username
            except Exception:
                pass
        if nickname:
            username_str = f" (@{escape_md(username)})" if username else ""
            row = f"• **{escape_md(nickname)}**{username_str} `(ID: {up_id})`"
        else:
            row = f"• **Uploader User** `(ID: {up_id}, Unregistered)`"
        uploader_rows.append(row)

    text = (
        f"👑 **BOT ROSTER** 👑\n"
        f"───────────────\n\n"
        f"👑 **OWNER**\n"
        f"{owner_row}\n\n"
    )
    if admin_rows:
        text += "🛡️ **ADMIN**\n" + "\n".join(admin_rows) + "\n\n"
    if uploader_rows:
        text += "🎬 **UPLOADER**\n" + "\n".join(uploader_rows) + "\n\n"

    text += "───────────────"
    await message.answer(text, parse_mode="Markdown")

@router.message(Command("spawnsetting", "spawnsettings"))
async def cmd_spawn_setting(message: Message, db: AsyncSession):
    if message.chat.type not in ["group", "supergroup"]:
        await message.answer("⚠️ Spawns only occur in group chats! Use this command in a group.")
        return

    chat_id = message.chat.id

    # Query database for GroupSetting
    stmt = select(GroupSetting).where(GroupSetting.chat_id == chat_id)
    res = await db.execute(stmt)
    setting = res.scalar_one_or_none()

    # If no setting exists yet, initialize it
    if not setting:
        import random
        setting = GroupSetting(
            chat_id=chat_id,
            message_counter=0,
            spawn_threshold=random.randint(50, 100),
            enabled=True
        )
        db.add(setting)
        await db.commit()

    # Sync cache if not already cached
    from utils.group_monitor import group_settings_cache, group_message_counters
    if chat_id not in group_settings_cache:
        group_settings_cache[chat_id] = {
            "spawn_threshold": setting.spawn_threshold,
            "enabled": setting.enabled
        }

    cached_setting = group_settings_cache[chat_id]
    current_count = group_message_counters.get(chat_id, 0)
    threshold = cached_setting["spawn_threshold"]
    enabled = cached_setting["enabled"]

    status_str = "🟢 **Enabled**" if enabled else "🔴 **Disabled**"
    remaining = max(0, threshold - current_count)

    # Generate progress bar
    bar = get_progress_bar(current_count, threshold, 10)

    # Format message
    text = (
        f"⚙️ **SPAWN SETTINGS** ⚙️\n"
        f"───────────────\n"
        f"📡 **Status**: {status_str}\n"
        f"⏱️ **Spawn Interval**: `Every {threshold} messages`\n\n"
        f"📊 **Activity Progress**:\n"
        f"`[{bar}]` `{current_count}/{threshold}`\n\n"
        f"✉️ **Next Spawn**: In **{remaining} messages**!"
    )

    if not enabled:
        text = (
            f"⚙️ **SPAWN SETTINGS** ⚙️\n"
            f"───────────────\n"
            f"📡 **Status**: {status_str}\n\n"
            f"🚫 Spawns are currently disabled in this group. Group admins can enable them using `/toggle_spawns`."
        )

    await message.answer(text, parse_mode="Markdown")

@router.message(Command("giftcoins"))
async def cmd_gift_coins(message: Message, db: AsyncSession):
    # Only bot owner can use this
    if not config.ADMIN_IDS or message.from_user.id != config.ADMIN_IDS[0]:
        await message.answer("❌ Denied. Only the Bot Owner can use this command.")
        return

    # Parse arguments
    parts = message.text.split()

    target_user = None
    amount = 0

    # Check if this is a reply
    if message.reply_to_message:
        if len(parts) < 2 or not parts[1].isdigit():
            await message.answer("⚠️ Format: Reply to a user's message with `/giftcoins <amount>`")
            return
        amount = int(parts[1])
        target_tg_user = message.reply_to_message.from_user

        # Ensure target user exists in DB
        user_stmt = select(User).where(User.id == target_tg_user.id)
        user_res = await db.execute(user_stmt)
        target_user = user_res.scalar_one_or_none()
        if not target_user:
            target_user = User(
                id=target_tg_user.id,
                username=target_tg_user.username,
                nickname=target_tg_user.first_name
            )
            db.add(target_user)
            await db.flush()
    else:
        # Not a reply, parse: /giftcoins <@username/user_id> <amount>
        if len(parts) < 3:
            await message.answer("⚠️ Format: `/giftcoins <@username/user_id> <amount>` (or reply to their message with `/giftcoins <amount>`)")
            return

        target_str = parts[1]
        amount_str = parts[2]

        if not amount_str.isdigit():
            await message.answer("⚠️ Amount must be a number.")
            return
        amount = int(amount_str)

        if target_str.isdigit():
            # Target by User ID
            u_id = int(target_str)
            user_stmt = select(User).where(User.id == u_id)
            user_res = await db.execute(user_stmt)
            target_user = user_res.scalar_one_or_none()
            if not target_user:
                await message.answer(f"❌ User ID {u_id} is not registered in the database.")
                return
        elif target_str.startswith("@"):
            # Target by Username
            username = target_str.replace("@", "").strip()
            user_stmt = select(User).where(User.username.ilike(username))
            user_res = await db.execute(user_stmt)
            target_user = user_res.scalar_one_or_none()
            if not target_user:
                await message.answer(f"❌ User with username @{username} not found in database.")
                return
        else:
            await message.answer("⚠️ Target must be a user ID or @username.")
            return

    # Award coins
    target_user.coins += amount
    await db.commit()

    admin_name = message.from_user.first_name
    recipient_name = target_user.nickname or "Trainer"
    caption = (
        f"📣 <b>Coins Given!</b>\n"
        f"<blockquote>👤 Sender: <b>{escape_md(admin_name)}</b>\n"
        f"👤 Recipient: <b>{escape_md(recipient_name)}</b>\n"
        f"💰 Coins: <b>{amount} coins</b>\n"
        f"💰 New Balance: <b>💰 {target_user.coins} coins</b></blockquote>"
    )
    
    from aiogram.types import FSInputFile
    import os

    coin_photo = "https://raw.githubusercontent.com/royalrahul456/PokeEmpire/main/data/coin_gift.png"
    if os.path.exists("data/coin_gift.png"):
        coin_photo = FSInputFile("data/coin_gift.png")

    try:
        await message.answer_photo(photo=coin_photo, caption=caption, parse_mode="HTML")
    except Exception as e:
        print(f"Error sending gifted coins photo: {e}")
        await message.answer(caption, parse_mode="HTML")
        
    # Send private DM to recipient
    dm_text = (
        f"📣 <b>You received a Gift!</b>\n"
        f"<blockquote>👤 Sender: <b>{escape_md(admin_name)}</b>\n"
        f"💰 Coins: <b>{amount} coins</b></blockquote>"
    )
    try:
        await message.bot.send_message(chat_id=target_user.id, text=dm_text, parse_mode="HTML")
    except Exception:
        pass

@router.message(Command("deletecoins", "dltcoins", "removecoins", "takecoins"))
async def cmd_delete_coins(message: Message, db: AsyncSession):
    # Only bot owner can use this
    if not config.ADMIN_IDS or message.from_user.id != config.ADMIN_IDS[0]:
        await message.answer("❌ Denied. Only the Bot Owner can use this command.")
        return

    parts = message.text.split()
    target_user = None
    amount_str = None

    if message.reply_to_message:
        if len(parts) < 2:
            await message.answer("⚠️ Format: Reply to a user's message with `/deletecoins <amount>` (or `all`)")
            return
        amount_str = parts[1]
        target_tg_user = message.reply_to_message.from_user

        user_stmt = select(User).where(User.id == target_tg_user.id)
        user_res = await db.execute(user_stmt)
        target_user = user_res.scalar_one_or_none()
        if not target_user:
            await message.answer("❌ Target user is not registered in the database.")
            return
    else:
        if len(parts) < 3:
            await message.answer("⚠️ Format: `/deletecoins <@username/user_id> <amount>` (or reply with `/deletecoins <amount>`)")
            return
        
        arg1 = parts[1]
        arg2 = parts[2]

        # Determine which argument is target and which is amount
        if arg1.isdigit() or arg1.startswith("@"):
            target_str = arg1
            amount_str = arg2
        else:
            target_str = arg2
            amount_str = arg1

        if target_str.isdigit():
            u_id = int(target_str)
            user_stmt = select(User).where(User.id == u_id)
            user_res = await db.execute(user_stmt)
            target_user = user_res.scalar_one_or_none()
            if not target_user:
                await message.answer(f"❌ User ID {u_id} is not registered in the database.")
                return
        elif target_str.startswith("@"):
            username = target_str.replace("@", "").strip()
            user_stmt = select(User).where(User.username.ilike(username))
            user_res = await db.execute(user_stmt)
            target_user = user_res.scalar_one_or_none()
            if not target_user:
                await message.answer(f"❌ User with username @{username} not found in database.")
                return
        else:
            await message.answer("⚠️ Target must be a user ID or @username.")
            return

    # Deduct coins
    if amount_str.lower() in ["all", "full", "max"]:
        deleted_amount = target_user.coins
        target_user.coins = 0
    elif amount_str.isdigit():
        sub_amount = int(amount_str)
        deleted_amount = min(target_user.coins, sub_amount)
        target_user.coins = max(0, target_user.coins - sub_amount)
    else:
        await message.answer("⚠️ Amount must be a number or `all`.")
        return

    await db.commit()

    admin_name = message.from_user.first_name
    recipient_name = target_user.nickname or "Trainer"
    caption = (
        f"🗑️ <b>Coins Removed!</b>\n"
        f"───────────────\n"
        f"<blockquote>👤 Owner: <b>{escape_md(admin_name)}</b>\n"
        f"👤 Target: <b>{escape_md(recipient_name)}</b>\n"
        f"🔥 Removed: <b>-{deleted_amount:,} coins</b>\n"
        f"💳 New Balance: <b>💰 {target_user.coins:,} coins</b></blockquote>"
    )
    
    await message.answer(caption, parse_mode="HTML")

@router.message(Command("giftpokemon"))
async def cmd_gift_pokemon(message: Message, db: AsyncSession):
    # Only bot owner can use this
    if not config.ADMIN_IDS or message.from_user.id != config.ADMIN_IDS[0]:
        await message.answer("❌ Denied. Only the Bot Owner can use this command.")
        return

    # Parse arguments
    parts = message.text.split()

    target_user = None
    poke_query = None
    is_shiny = False

    # Check if this is a reply: /giftpokemon <pokemon_name_or_id> [shiny]
    if message.reply_to_message:
        if len(parts) < 2:
            await message.answer("⚠️ Format: Reply to a user's message with `/giftpokemon <pokemon_name/id> [shiny]`")
            return
        poke_query = parts[1].lower()
        extra_parts = [p.lower() for p in parts[2:]]
        if "shiny" in extra_parts or "s" in extra_parts:
            is_shiny = True

        target_tg_user = message.reply_to_message.from_user

        # Ensure target user exists in DB
        user_stmt = select(User).where(User.id == target_tg_user.id)
        user_res = await db.execute(user_stmt)
        target_user = user_res.scalar_one_or_none()
        if not target_user:
            target_user = User(
                id=target_tg_user.id,
                username=target_tg_user.username,
                nickname=target_tg_user.first_name
            )
            db.add(target_user)
            await db.flush()
    else:
        # Not a reply, parse: /giftpokemon <@username/user_id> <pokemon_name_or_id> [shiny]
        if len(parts) < 3:
            await message.answer("⚠️ Format: `/giftpokemon <@username/user_id> <pokemon_name/id> [shiny]` (or reply to their message)")
            return

        target_str = parts[1]
        poke_query = parts[2].lower()

        extra_parts = [p.lower() for p in parts[3:]]
        if "shiny" in extra_parts or "s" in extra_parts:
            is_shiny = True

        if target_str.isdigit():
            # Target by User ID
            u_id = int(target_str)
            user_stmt = select(User).where(User.id == u_id)
            user_res = await db.execute(user_stmt)
            target_user = user_res.scalar_one_or_none()
            if not target_user:
                await message.answer(f"❌ User ID {u_id} is not registered in the database.")
                return
        elif target_str.startswith("@"):
            # Target by Username
            username = target_str.replace("@", "").strip()
            user_stmt = select(User).where(User.username.ilike(username))
            user_res = await db.execute(user_stmt)
            target_user = user_res.scalar_one_or_none()
            if not target_user:
                await message.answer(f"❌ User with username @{username} not found in database.")
                return
        else:
            await message.answer("⚠️ Target must be a user ID or @username.")
            return

    # Parse form index from decimal (e.g. 6.2)
    form_index = 0
    if "." in poke_query:
        pq, fq = poke_query.split(".", 1)
        if fq.isdigit():
            form_index = int(fq)
        poke_query = pq

    # Resolve Pokémon species
    if poke_query.isdigit():
        poke_stmt = select(Pokemon).where(Pokemon.id == int(poke_query))
    else:
        poke_stmt = select(Pokemon).where(Pokemon.name.ilike(poke_query))

    poke_res = await db.execute(poke_stmt)
    pokemon = poke_res.scalar_one_or_none()

    if not pokemon:
        await message.answer(f"❌ Pokémon '{poke_query}' not found in database.")
        return

    # Validate that custom form media is configured for form_index > 0
    if form_index > 0:
        from database.models import PokemonFormMedia
        media_stmt = select(PokemonFormMedia).where(
            PokemonFormMedia.pokemon_id == pokemon.id,
            PokemonFormMedia.form_index == form_index
        )
        media_res = await db.execute(media_stmt)
        if media_res.scalar_one_or_none() is None:
            await message.answer(f"❌ Form {form_index} is not configured for {pokemon.name.title()} yet!\nUse `/setpokemedia {pokemon.id}.{form_index}` first in private DM.")
            return

    # Roll stats/IVs (stored in DB but hidden from message)
    import random
    iv_hp = random.randint(0, 31)
    iv_atk = random.randint(0, 31)
    iv_def = random.randint(0, 31)
    iv_spd = random.randint(0, 31)

    # Generate unique serial number if form index > 0
    serial_number = None
    if form_index > 0:
        serial_number = f"#{pokemon.id:03d}-{random.randint(1000, 9999)}"

    # Insert UserPokemon
    new_poke = UserPokemon(
        user_id=target_user.id,
        pokemon_id=pokemon.id,
        is_shiny=is_shiny,
        is_amv=(form_index == 1),
        form_index=form_index,
        serial_number=serial_number,
        level=1,
        xp=0,
        iv_hp=iv_hp,
        iv_atk=iv_atk,
        iv_def=iv_def,
        iv_spd=iv_spd
    )
    db.add(new_poke)
    await db.commit()

    # Form indicators
    form_names = {
        0: "",
        1: "AMV ",
        2: "Dmax ",
        3: "Gmax ",
        4: "Z-Move ",
        5: "Terastal "
    }
    form_badge = form_names.get(form_index, f"Form {form_index} ")
    shiny_badge = "✨ Shiny " if is_shiny else ""
    serial_str = f"\n🎫 **Serial Number**: `{serial_number}`" if serial_number else ""
    r_emoji = get_rarity_emoji(pokemon.rarity)
    admin_name = message.from_user.first_name

    # Resolve media of the gifted Pokémon
    media_value = pokemon.image_url
    media_type = "photo"
    if form_index > 0:
        form_media = await get_single_form_media_value(db, pokemon.id, form_index)
        if form_media:
            media_type, media_value = parse_stored_media_value(form_media)
    else:
        if pokemon.video_url:
            media_type = "video"
            media_value = pokemon.video_url

    admin_name = message.from_user.first_name
    recipient_name = target_user.nickname or "Trainer"
    shiny_badge = "✨ Shiny " if is_shiny else ""
    form_badge = form_names.get(form_index, f"Form {form_index} ")
    r_emoji = get_rarity_emoji(pokemon.rarity)
    serial_str = f" (🎫 {serial_number})" if serial_number else ""
    pokemon_display = f"{r_emoji} {shiny_badge}{form_badge}<b>{pokemon.name.title()}</b>{serial_str}"

    caption = (
        f"📣 <b>Pokémon Given!</b>\n"
        f"<blockquote>👤 Sender: <b>{escape_md(admin_name)}</b>\n"
        f"👤 Recipient: <b>{escape_md(recipient_name)}</b>\n"
        f"💝 Pokémon: {pokemon_display}</blockquote>"
    )

    import os
    from aiogram.types import FSInputFile
    if isinstance(media_value, str) and os.path.exists(media_value):
        media_value = FSInputFile(media_value)

    try:
        if media_type == "video":
            await message.answer_video(video=media_value, caption=caption, parse_mode="HTML")
        elif media_type == "animation":
            await message.answer_animation(animation=media_value, caption=caption, parse_mode="HTML")
        else:
            await message.answer_photo(photo=media_value, caption=caption, parse_mode="HTML")
    except Exception as e:
        print(f"Error sending gifted pokemon media: {e}")
        await message.answer(caption, parse_mode="HTML")

    # Send private DM to recipient
    dm_text = (
        f"📣 <b>You received a Gift!</b>\n"
        f"<blockquote>👤 Sender: <b>{escape_md(admin_name)}</b>\n"
        f"💝 Pokémon: {pokemon_display}</blockquote>"
    )
    try:
        await message.bot.send_message(chat_id=target_user.id, text=dm_text, parse_mode="HTML")
    except Exception:
        pass

def update_env_admin_ids(new_ids):
    import os
    import re
    env_path = ".env"
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        content = f.read()

    ids_str = ",".join(map(str, new_ids))
    if re.search(r"^ADMIN_IDS=.*", content, flags=re.MULTILINE):
        new_content = re.sub(r"^ADMIN_IDS=.*", f"ADMIN_IDS={ids_str}", content, flags=re.MULTILINE)
    else:
        new_content = content.rstrip() + f"\nADMIN_IDS={ids_str}\n"

    with open(env_path, "w", encoding="utf-8") as f:
        f.write(new_content)

def update_env_uploader_ids(new_ids):
    import os
    import re
    env_path = ".env"
    if not os.path.exists(env_path):
        return
    with open(env_path, "r", encoding="utf-8") as f:
        content = f.read()

    ids_str = ",".join(map(str, new_ids))
    if re.search(r"^UPLOADER_IDS=.*", content, flags=re.MULTILINE):
        new_content = re.sub(r"^UPLOADER_IDS=.*", f"UPLOADER_IDS={ids_str}", content, flags=re.MULTILINE)
    else:
        new_content = content.rstrip() + f"\nUPLOADER_IDS={ids_str}\n"

    with open(env_path, "w", encoding="utf-8") as f:
        f.write(new_content)

async def save_dynamic_settings(db: AsyncSession):
    from database.models import GlobalSetting
    from sqlalchemy import select
    
    # Save admins
    admins_str = ",".join(map(str, config.ADMIN_IDS))
    stmt = select(GlobalSetting).where(GlobalSetting.key == "dynamic_admin_ids")
    res = await db.execute(stmt)
    setting = res.scalar_one_or_none()
    if setting:
        setting.value = admins_str
    else:
        db.add(GlobalSetting(key="dynamic_admin_ids", value=admins_str))
        
    # Save uploaders
    uploaders_str = ",".join(map(str, config.UPLOADER_IDS))
    stmt = select(GlobalSetting).where(GlobalSetting.key == "dynamic_uploader_ids")
    res = await db.execute(stmt)
    setting = res.scalar_one_or_none()
    if setting:
        setting.value = uploaders_str
    else:
        db.add(GlobalSetting(key="dynamic_uploader_ids", value=uploaders_str))
        
    await db.commit()

@router.message(Command("makeadmin"))
async def cmd_make_admin(message: Message, db: AsyncSession):
    # Only bot owner can use this (first admin ID in config.ADMIN_IDS)
    if not config.ADMIN_IDS or message.from_user.id != config.ADMIN_IDS[0]:
        await message.answer("❌ Denied. Only the Bot Owner can configure administrators.")
        return

    parts = message.text.split()
    target_id = None
    target_name = None

    if message.reply_to_message:
        target_tg_user = message.reply_to_message.from_user
        target_id = target_tg_user.id
        target_name = target_tg_user.first_name
    else:
        if len(parts) < 2:
            await message.answer("⚠️ Format: `/makeadmin <@username/user_id>` (or reply to a user's message with `/makeadmin`)")
            return
        target_str = parts[1]
        if target_str.isdigit():
            target_id = int(target_str)
            # Try to find in db
            stmt = select(User).where(User.id == target_id)
            res = await db.execute(stmt)
            u = res.scalar_one_or_none()
            if u:
                target_name = u.nickname
            else:
                try:
                    chat = await message.bot.get_chat(target_id)
                    target_name = chat.first_name
                except Exception:
                    target_name = f"User {target_id}"
        elif target_str.startswith("@"):
            username = target_str.replace("@", "").strip()
            stmt = select(User).where(User.username.ilike(username))
            res = await db.execute(stmt)
            u = res.scalar_one_or_none()
            if not u:
                await message.answer(f"❌ User with username @{username} not found in database.")
                return
            target_id = u.id
            target_name = u.nickname
        else:
            await message.answer("⚠️ Target must be a user ID or @username.")
            return

    # Check if already admin
    if target_id in config.ADMIN_IDS:
        await message.answer(f"ℹ️ **{escape_md(target_name)}** is already a Bot Administrator.")
        return

    # Add to in-memory list
    config.ADMIN_IDS.append(target_id)

    # Save to .env and database
    update_env_admin_ids(config.ADMIN_IDS)
    await save_dynamic_settings(db)

    text = (
        f"👑 **ADMINISTRATOR ADDED** 👑\n"
        f"───────────────\n"
        f"User **{escape_md(target_name)}** `(ID: {target_id})` has been appointed as a Bot Administrator!\n"
        f"───────────────"
    )
    await message.answer(text, parse_mode="Markdown")

@router.message(Command("removeadmin"))
async def cmd_remove_admin(message: Message, db: AsyncSession):
    # Only bot owner can use this (first admin ID in config.ADMIN_IDS)
    if not config.ADMIN_IDS or message.from_user.id != config.ADMIN_IDS[0]:
        await message.answer("❌ Denied. Only the Bot Owner can configure administrators.")
        return

    parts = message.text.split()
    target_id = None
    target_name = None

    if message.reply_to_message:
        target_tg_user = message.reply_to_message.from_user
        target_id = target_tg_user.id
        target_name = target_tg_user.first_name
    else:
        if len(parts) < 2:
            await message.answer("⚠️ Format: `/removeadmin <@username/user_id>` (or reply to a user's message with `/removeadmin`)")
            return
        target_str = parts[1]
        if target_str.isdigit():
            target_id = int(target_str)
            # Try to find in db
            stmt = select(User).where(User.id == target_id)
            res = await db.execute(stmt)
            u = res.scalar_one_or_none()
            if u:
                target_name = u.nickname
            else:
                try:
                    chat = await message.bot.get_chat(target_id)
                    target_name = chat.first_name
                except Exception:
                    target_name = f"User {target_id}"
        elif target_str.startswith("@"):
            username = target_str.replace("@", "").strip()
            stmt = select(User).where(User.username.ilike(username))
            res = await db.execute(stmt)
            u = res.scalar_one_or_none()
            if not u:
                await message.answer(f"❌ User with username @{username} not found in database.")
                return
            target_id = u.id
            target_name = u.nickname
        else:
            await message.answer("⚠️ Target must be a user ID or @username.")
            return

    # Check if target is the owner
    if target_id == config.ADMIN_IDS[0]:
        await message.answer("❌ Denied. You cannot remove yourself (the Bot Owner) from the administrator list!")
        return

    # Check if not admin
    if target_id not in config.ADMIN_IDS:
        await message.answer(f"⚠️ **{escape_md(target_name)}** is not a Bot Administrator.")
        return

    # Remove from in-memory list
    config.ADMIN_IDS.remove(target_id)

    # Save to .env and database
    update_env_admin_ids(config.ADMIN_IDS)
    await save_dynamic_settings(db)

    text = (
        f"🛡️ **ADMINISTRATOR REMOVED** 🛡️\n"
        f"───────────────\n"
        f"User **{escape_md(target_name)}** `(ID: {target_id})` has been removed from the Bot Administrator list.\n"
        f"───────────────"
    )
    await message.answer(text, parse_mode="Markdown")


@router.message(Command("makeuploader"))
async def cmd_make_uploader(message: Message, db: AsyncSession):
    # Only bot owner can use this
    if not config.ADMIN_IDS or message.from_user.id != config.ADMIN_IDS[0]:
        await message.answer("❌ Denied. Only the Bot Owner can appoint Uploaders.")
        return

    parts = message.text.split()
    target_id = None
    target_name = None

    if message.reply_to_message:
        target_tg_user = message.reply_to_message.from_user
        target_id = target_tg_user.id
        target_name = target_tg_user.first_name
    else:
        if len(parts) < 2:
            await message.answer("⚠️ Format: `/makeuploader <@username/user_id>` (or reply to a user's message with `/makeuploader`)")
            return
        target_str = parts[1]
        if target_str.isdigit():
            target_id = int(target_str)
            stmt = select(User).where(User.id == target_id)
            res = await db.execute(stmt)
            u = res.scalar_one_or_none()
            if u:
                target_name = u.nickname
            else:
                try:
                    chat = await message.bot.get_chat(target_id)
                    target_name = chat.first_name
                except Exception:
                    target_name = f"User {target_id}"
        elif target_str.startswith("@"):
            username = target_str.replace("@", "").strip()
            stmt = select(User).where(User.username.ilike(username))
            res = await db.execute(stmt)
            u = res.scalar_one_or_none()
            if not u:
                await message.answer(f"❌ User with username @{username} not found in database.")
                return
            target_id = u.id
            target_name = u.nickname
        else:
            await message.answer("⚠️ Target must be a user ID or @username.")
            return

    # Check if already uploader or admin
    if target_id in config.UPLOADER_IDS:
        await message.answer(f"ℹ️ **{escape_md(target_name)}** is already an Uploader.")
        return
    if target_id in config.ADMIN_IDS:
        await message.answer(f"ℹ️ **{escape_md(target_name)}** is already an Admin — they already have full access.")
        return

    # Add to in-memory list
    config.UPLOADER_IDS.append(target_id)

    # Save to .env and database
    update_env_uploader_ids(config.UPLOADER_IDS)
    await save_dynamic_settings(db)

    announcement = (
        f"🎬 **UPLOADER ADDED** 🎬\n"
        f"───────────────\n"
        f"User **{escape_md(target_name)}** `(ID: {target_id})` has been appointed as an Uploader!\n"
        f"───────────────"
    )
    await message.answer(announcement, parse_mode="Markdown")

    # DM the new uploader with their command guide
    dm_text = (
        f"🎬 <b>Welcome, Uploader!</b>\n"
        f"─────────────────────\n\n"
        f"You have been granted <b>Uploader</b> access to <b>PokeEmpire Bot</b>.\n\n"
        f"As an Uploader, you can add and manage Pokémon media (AMV, Art, Dmax, Gmax, Z-Move, Terastal).\n\n"
        f"<b>📋 Your Commands:</b>\n\n"
        f"<b>/setpokemedia &lt;pokemon_name/id&gt;</b>\n"
        f"  Shows a menu to pick which form to update.\n\n"
        f"<b>/setpokemedia &lt;pokemon_id&gt;.&lt;form_index&gt;</b>\n"
        f"  Directly start updating a specific form.\n"
        f"  Then send the photo/video/GIF.\n\n"
        f"<b>📐 Form Index Guide:</b>\n"
        f"  • <code>6.0</code> — Standard Photo\n"
        f"  • <code>6.1</code> — AMV / Art 🎬\n"
        f"  • <code>6.2</code> — Dynamax (Dmax) ⚡\n"
        f"  • <code>6.3</code> — Gigantamax (Gmax) 💥\n"
        f"  • <code>6.4</code> — Z-Move 🌀\n"
        f"  • <code>6.5</code> — Terastal 🔮\n\n"
        f"<b>📌 Examples:</b>\n"
        f"  <code>/setpokemedia charizard</code> → choose form\n"
        f"  <code>/setpokemedia 6.1</code> → update AMV directly\n"
        f"  <code>/setpokemedia 6.2</code> → update Dmax directly\n\n"
        f"<b>/medialist</b>\n"
        f"  View all currently configured Pokémon media IDs.\n\n"
        f"─────────────────────\n"
        f"⚠️ All uploads are announced to the updates channel automatically."
    )
    try:
        await message.bot.send_message(chat_id=target_id, text=dm_text, parse_mode="HTML")
    except Exception:
        await message.answer(f"⚠️ Couldn't DM **{escape_md(target_name)}** — they may not have started the bot yet.", parse_mode="Markdown")


@router.message(Command("removeuploader"))
async def cmd_remove_uploader(message: Message, db: AsyncSession):
    # Only bot owner can use this
    if not config.ADMIN_IDS or message.from_user.id != config.ADMIN_IDS[0]:
        await message.answer("❌ Denied. Only the Bot Owner can remove Uploaders.")
        return

    parts = message.text.split()
    target_id = None
    target_name = None

    if message.reply_to_message:
        target_tg_user = message.reply_to_message.from_user
        target_id = target_tg_user.id
        target_name = target_tg_user.first_name
    else:
        if len(parts) < 2:
            await message.answer("⚠️ Format: `/removeuploader <@username/user_id>` (or reply to a user's message with `/removeuploader`)")
            return
        target_str = parts[1]
        if target_str.isdigit():
            target_id = int(target_str)
            stmt = select(User).where(User.id == target_id)
            res = await db.execute(stmt)
            u = res.scalar_one_or_none()
            if u:
                target_name = u.nickname
            else:
                try:
                    chat = await message.bot.get_chat(target_id)
                    target_name = chat.first_name
                except Exception:
                    target_name = f"User {target_id}"
        elif target_str.startswith("@"):
            username = target_str.replace("@", "").strip()
            stmt = select(User).where(User.username.ilike(username))
            res = await db.execute(stmt)
            u = res.scalar_one_or_none()
            if not u:
                await message.answer(f"❌ User with username @{username} not found in database.")
                return
            target_id = u.id
            target_name = u.nickname
        else:
            await message.answer("⚠️ Target must be a user ID or @username.")
            return

    if target_id not in config.UPLOADER_IDS:
        await message.answer(f"⚠️ **{escape_md(target_name)}** is not in the Uploader list.")
        return

    config.UPLOADER_IDS.remove(target_id)
    update_env_uploader_ids(config.UPLOADER_IDS)
    await save_dynamic_settings(db)

    text = (
        f"🎬 **UPLOADER REMOVED** 🎬\n"
        f"───────────────\n"
        f"User **{escape_md(target_name)}** `(ID: {target_id})` has been removed from the Uploader list.\n"
        f"───────────────"
    )
    await message.answer(text, parse_mode="Markdown")
    # DM the removed uploader
    try:
        await message.bot.send_message(
            chat_id=target_id,
            text=(
                f"⚠️ <b>Uploader Access Revoked</b>\n\n"
                f"Your Uploader permissions for <b>PokeEmpire Bot</b> have been removed.\n"
                f"You can no longer use <code>/setpokemedia</code>."
            ),
            parse_mode="HTML"
        )
    except Exception:
        pass


@router.message(Command("spawn"))
async def cmd_spawn(message: Message, db: AsyncSession):
    # Ensure command is run in a group chat
    if message.chat.type not in ["group", "supergroup"]:
        await message.answer("⚠️ Wild Pokémon only spawn in group chats! Use `/spawn` inside a group chat.")
        return

    # Enforce authorization (group admin or bot owner)
    if not await is_user_admin(message):
        await message.answer("❌ Denied. Only group administrators or bot owners can trigger a manual spawn.")
        return

    parts = message.text.split()
    specified_rarity = None
    if len(parts) >= 2:
        rarity_input = parts[1].strip().title()
        if rarity_input in ["Common", "Rare", "Epic", "Legendary", "Mythical"]:
            specified_rarity = rarity_input
        else:
            await message.answer("⚠️ Invalid rarity. Choose from `Common`, `Rare`, `Epic`, `Legendary`, or `Mythical`.")
            return

    # Trigger a wild encounter spawn in this chat
    from services.spawn_service import SpawnService

    try:
        success = await SpawnService.trigger_spawn(db, message.chat.id, message.bot, rarity=specified_rarity)
        if not success:
            await message.answer("❌ Failed to spawn Pokémon. Ensure the bot has permission to send media/messages in this chat.")
    except Exception as err:
        print(f"[MANUAL SPAWN EXCEPTION] chat={message.chat.id} error={err}")
        await message.answer(f"❌ Error executing spawn: `{err}`")

@router.message(Command("spawnchance"))
async def cmd_spawn_chance(message: Message):
    # Only owner can configure
    if message.from_user.id not in config.ADMIN_IDS:
        await message.answer("❌ Denied. Only the bot owner can configure global spawn chances.")
        return

    parts = message.text.split()
    from utils.settings import load_spawn_settings, save_spawn_settings
    settings = load_spawn_settings()

    if len(parts) < 2:
        # Show current settings
        probs = settings.get("group_rarity_probabilities", {})
        text = (
            "⚙️ **GROUP SPAWN CHANCES (OWNER ONLY)** ⚙️\n"
            "───────────────\n"
            "📈 **Custom Group Rarity Probabilities**:\n"
            f"• Common: `{probs.get('Common', 70)}%`\n"
            f"• Rare: `{probs.get('Rare', 20)}%`\n"
            f"• Epic: `{probs.get('Epic', 7)}%`\n"
            f"• Legendary: `{probs.get('Legendary', 2)}%`\n"
            f"• Mythical: `{probs.get('Mythical', 1)}%`\n"
            "───────────────\n"
            "💡 **Commands to Configure**:\n"
            "👉 `/spawnchance default` - Reset to standard rates\n"
            "👉 `/spawnchance <common> <rare> <epic> <legendary> <mythical>` - Set custom weights"
        )
        await message.answer(text, parse_mode="Markdown")
        return

    arg = parts[1].lower()
    if arg == "default":
        settings["group_rarity_probabilities"] = {
            "Common": 70,
            "Rare": 20,
            "Epic": 7,
            "Legendary": 2,
            "Mythical": 1
        }
        await save_spawn_settings(settings)
        await message.answer("✅ **Reset group spawn chances to default rates (70% C, 20% R, 7% E, 2% L, 1% M).**")
    else:
        # Check for 5 integer weights
        if len(parts) < 6:
            await message.answer("⚠️ Format: `/spawnchance <common> <rare> <epic> <legendary> <mythical>` (e.g. `/spawnchance 50 30 15 4 1`)")
            return

        try:
            weights = [int(p) for p in parts[1:6]]
            if any(w < 0 for w in weights) or sum(weights) == 0:
                raise ValueError()
        except ValueError:
            await message.answer("❌ Error: All weights must be non-negative integers, and the sum must be greater than zero.")
            return

        settings["group_rarity_probabilities"] = {
            "Common": weights[0],
            "Rare": weights[1],
            "Epic": weights[2],
            "Legendary": weights[3],
            "Mythical": weights[4]
        }
        await save_spawn_settings(settings)

        await message.answer(
            "✅ **Group spawn chances configured!**\n"
            "**New custom weights**:\n"
            f"• Common: `{weights[0]}`\n"
            f"• Rare: `{weights[1]}`\n"
            f"• Epic: `{weights[2]}`\n"
            f"• Legendary: `{weights[3]}`\n"
            f"• Mythical: `{weights[4]}`"
        )


# In-memory dictionary to track active pokemon media updates
# Key: user_id, Value: (pokemon_id, form_index)
active_poke_media_updates = {}

@router.message(Command("setpokemedia"))
async def cmd_set_poke_media(message: Message, db: AsyncSession):
    if message.chat.type != "private":
        await message.answer("⚠️ This command can only be used in private DMs.")
        return

    # Allow both owner/admins and uploaders
    user_id = message.from_user.id
    is_authorized = user_id in config.ADMIN_IDS or user_id in config.UPLOADER_IDS
    if not is_authorized:
        await message.answer("❌ Denied. Only Bot Admins or Uploaders can configure Pokémon media.")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("⚠️ Format: `/setpokemedia <pokemon_name/id>.<form_index>`")
        return

    query = parts[1].lower()

    # Direct assignment: /setpokemedia <id>.<form> <file_id>
    if len(parts) >= 3:
        target_str = parts[1].lower()
        form_index = 1
        if "." in target_str:
            pq, fq = target_str.split(".", 1)
            if fq.isdigit():
                form_index = int(fq)
            target_str = pq

        # Resolve Pokemon
        if target_str.isdigit():
            stmt = select(Pokemon).where(Pokemon.id == int(target_str))
        else:
            stmt = select(Pokemon).where(Pokemon.name.ilike(target_str))
        res = await db.execute(stmt)
        pokemon = res.scalar_one_or_none()
        if not pokemon:
            await message.answer(f"❌ Pokémon '{target_str}' not found.")
            return

        file_id = parts[2]
        media_prefix = "video:" if file_id.startswith("BAA") else "photo:"
        db_media_value = f"{media_prefix}{file_id}"

        # Save
        if form_index == 0:
            pokemon.image_url = file_id
        else:
            from database.models import PokemonFormMedia
            media_stmt = select(PokemonFormMedia).where(
                PokemonFormMedia.pokemon_id == pokemon.id,
                PokemonFormMedia.form_index == form_index
            )
            media_res = await db.execute(media_stmt)
            form_media = media_res.scalar_one_or_none()
            if form_media:
                form_media.media_value = db_media_value
            else:
                db.add(PokemonFormMedia(pokemon_id=pokemon.id, form_index=form_index, media_value=db_media_value))

            # Backwards compatibility
            if form_index == 1:
                pokemon.video_url = file_id
            elif form_index == 2:
                pokemon.dmax_url = file_id
            elif form_index == 3:
                pokemon.gmax_url = file_id
            elif form_index == 4:
                pokemon.zmove_url = file_id
            elif form_index == 5:
                pokemon.terastal_url = file_id

        await db.commit()

        # Post to updates channel if form_index > 0
        by_user = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
        if form_index > 0:
            await post_media_update_to_channel(message.bot, pokemon, form_index, db_media_value, by_user)

        await message.answer(
            f"✅ <b>MEDIA UPDATED SUCCESS</b>\n"
            f"───────────────\n"
            f"<blockquote>👾 Pokémon: <b>{pokemon.name.title()}</b>\n"
            f"🎭 Form: <b>Form {form_index}</b>\n"
            f"💾 Saved: <code>{db_media_value}</code>\n"
            f"📢 Announcement sent to {config.UPDATES_CHANNEL}!</blockquote>",
            parse_mode="HTML"
        )
        return

    # parse form_index if they provided e.g. /setpokemedia 6.2 without file_id
    form_index = 1
    target_str = query
    if "." in query:
        pq, fq = query.split(".", 1)
        if fq.isdigit():
            form_index = int(fq)
        target_str = pq

    # Resolve Pokemon for inline options
    if target_str.isdigit():
        stmt = select(Pokemon).where(Pokemon.id == int(target_str))
    else:
        stmt = select(Pokemon).where(Pokemon.name.ilike(target_str))
    res = await db.execute(stmt)
    pokemon = res.scalar_one_or_none()
    if not pokemon:
        await message.answer(f"❌ Pokémon '{target_str}' not found.")
        return

    # If they typed the dot index directly (e.g. /setpokemedia 6.2)
    if "." in parts[1]:
        active_poke_media_updates[message.from_user.id] = (pokemon.id, form_index)
        form_names = {
            0: "Standard Photo",
            1: "AMV / Art",
            2: "Dynamax (Dmax)",
            3: "Gigantamax (Gmax)",
            4: "Z-Move",
            5: "Terastal"
        }
        name = form_names.get(form_index, f"Form {form_index}")
        await message.answer(
            f"📥 <b>Ready to update {name} media for {pokemon.name.title()}!</b>\n\n"
            f"Please send the photo, video, or animation (GIF) now.",
            parse_mode="HTML"
        )
        return

    # Show inline choices
    builder = InlineKeyboardBuilder()
    builder.button(text="📸 Standard Photo (6.0)", callback_data=f"setpm_0_{pokemon.id}_{message.from_user.id}")
    builder.button(text="🎥 AMV / Art (6.1)", callback_data=f"setpm_1_{pokemon.id}_{message.from_user.id}")
    builder.button(text="⚡ Dynamax Dmax (6.2)", callback_data=f"setpm_2_{pokemon.id}_{message.from_user.id}")
    builder.button(text="💥 Gigantamax Gmax (6.3)", callback_data=f"setpm_3_{pokemon.id}_{message.from_user.id}")
    builder.button(text="🌀 Z-Move (6.4)", callback_data=f"setpm_4_{pokemon.id}_{message.from_user.id}")
    builder.button(text="🔮 Terastal (6.5)", callback_data=f"setpm_5_{pokemon.id}_{message.from_user.id}")
    builder.adjust(2)

    await message.answer(
        f"⚙️ <b>Configure Media for {pokemon.name.title()} (#{pokemon.id:03d})</b>\n\n"
        f"Choose which media field you would like to set:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("setpm_"))
async def cb_set_poke_media_choice(callback: CallbackQuery):
    parts = callback.data.split("_")
    # Structure: setpm_<form_index>_<pokemon_id>_<owner_id>
    form_index = int(parts[1])
    pokemon_id = int(parts[2])
    owner_id = int(parts[3])

    if callback.from_user.id != owner_id:
        await callback.answer("❌ Denied.", show_alert=True)
        return

    active_poke_media_updates[owner_id] = (pokemon_id, form_index)

    form_names = {
        0: "Standard Photo",
        1: "AMV / Art",
        2: "Dynamax (Dmax)",
        3: "Gigantamax (Gmax)",
        4: "Z-Move",
        5: "Terastal"
    }
    name = form_names.get(form_index, f"Form {form_index}")

    await callback.message.edit_text(
        f"📥 <b>Ready to update {name} media!</b>\n\n"
        f"Please send the photo, video, or animation (GIF) now.",
        parse_mode="HTML"
    )
    await callback.answer()


# Media receiver for admin/uploader pokemon edits
@router.message(F.chat.type == "private", lambda msg: msg.from_user.id in config.ADMIN_IDS or msg.from_user.id in config.UPLOADER_IDS, lambda msg: msg.from_user.id in active_poke_media_updates)
async def on_poke_media_received(message: Message, db: AsyncSession):
    user_id = message.from_user.id
    update_info = active_poke_media_updates.pop(user_id, None)
    if not update_info:
        return

    pokemon_id, form_index = update_info

    # Check media type in the sent message
    media_prefix = "video:"
    media_value = None

    if message.photo:
        media_prefix = "photo:"
        media_value = message.photo[-1].file_id
    elif message.video:
        media_prefix = "video:"
        media_value = message.video.file_id
    elif message.animation:
        media_prefix = "animation:"
        media_value = message.animation.file_id
    elif message.document:
        media_prefix = "video:"
        media_value = message.document.file_id

    if not media_value:
        await message.answer("❌ No valid media detected. Operation cancelled. Please use the command again.")
        return

    stmt = select(Pokemon).where(Pokemon.id == pokemon_id)
    res = await db.execute(stmt)
    pokemon = res.scalar_one_or_none()

    if not pokemon:
        await message.answer("❌ Pokémon no longer exists in database.")
        return

    # Save media value
    db_media_value = f"{media_prefix}{media_value}"

    # Standard Form (form_index == 0) gets saved to pokemon.image_url directly
    if form_index == 0:
        pokemon.image_url = media_value
    else:
        # Save to PokemonFormMedia
        from database.models import PokemonFormMedia
        media_stmt = select(PokemonFormMedia).where(
            PokemonFormMedia.pokemon_id == pokemon_id,
            PokemonFormMedia.form_index == form_index
        )
        media_res = await db.execute(media_stmt)
        form_media = media_res.scalar_one_or_none()

        if form_media:
            form_media.media_value = db_media_value
        else:
            db.add(PokemonFormMedia(pokemon_id=pokemon_id, form_index=form_index, media_value=db_media_value))

        # Backwards compatibility: update Pokemon columns
        if form_index == 1:
            pokemon.video_url = media_value
        elif form_index == 2:
            pokemon.dmax_url = media_value
        elif form_index == 3:
            pokemon.gmax_url = media_value
        elif form_index == 4:
            pokemon.zmove_url = media_value
        elif form_index == 5:
            pokemon.terastal_url = media_value

    await db.commit()

    # Post to updates channel if form_index > 0
    by_user = f"@{message.from_user.username}" if message.from_user.username else message.from_user.first_name
    if form_index > 0:
        await post_media_update_to_channel(message.bot, pokemon, form_index, db_media_value, by_user)

    await message.answer(
        f"✅ <b>MEDIA UPDATED SUCCESS</b>\n"
        f"───────────────\n"
        f"<blockquote>👾 Pokémon: <b>{pokemon.name.title()}</b>\n"
        f"🎭 Form: <b>Form {form_index}</b>\n"
        f"💾 Saved: <code>{db_media_value}</code>\n"
        f"📢 Announcement sent to {config.UPDATES_CHANNEL}!</blockquote>",
        parse_mode="HTML"
    )


async def get_media_list_text(db: AsyncSession) -> str:
    from utils.settings import get_custom_cover

    # 1. Covers
    covers = ["start", "xo", "pokedex"]
    cover_lines = []
    for c in covers:
        media_type, media_value = get_custom_cover(c)
        if media_type and media_value:
            cover_lines.append(f"• <b>{c.upper()} Cover:</b> ({media_type}) <code>{media_value}</code>")
        else:
            cover_lines.append(f"• <b>{c.upper()} Cover:</b> <i>Not set (using default)</i>")

    # 2. Pokémon custom media
    from database.models import PokemonFormMedia
    stmt = select(PokemonFormMedia, Pokemon).join(Pokemon).order_by(Pokemon.id, PokemonFormMedia.form_index)
    res = await db.execute(stmt)
    records = res.all()

    poke_media = {}
    for pfm, p in records:
        if p not in poke_media:
            poke_media[p] = []
        poke_media[p].append(pfm)

    form_names = {
        1: "AMV/Art",
        2: "Dmax",
        3: "Gmax",
        4: "Z-Move",
        5: "Terastal"
    }

    poke_lines = []
    for p, pfms in poke_media.items():
        details = []
        for pfm in pfms:
            fname = form_names.get(pfm.form_index, f"Form {pfm.form_index}")
            details.append(f"{fname} (.{pfm.form_index}): <code>{pfm.media_value}</code>")

        if details:
            details_str = "\n  - ".join(details)
            poke_lines.append(f"• <b>#{p.id:03d} {p.name.title()}</b>:\n  - {details_str}")

    # Build the final message
    response = (
        "📋 <b>PokeEmpire Configured Media IDs</b>\n"
        "───────────────────\n\n"
        "<b>🖼️ CUSTOM COVERS</b>\n"
        + "\n".join(cover_lines) + "\n\n"
        "<b>🎨 CUSTOM POKÉMON MEDIA</b>\n"
    )
    if poke_lines:
        response += "\n".join(poke_lines)
    else:
        response += "<i>No custom Pokémon media (photos/AMVs) set yet.</i>"

    return response


@router.message(Command("medialist"))
async def cmd_media_list(message: Message, db: AsyncSession):
    if not config.ADMIN_IDS or (message.from_user.id not in config.ADMIN_IDS and message.from_user.id not in config.UPLOADER_IDS):
        await message.answer("❌ Denied. Only Admins or Uploaders can view configured media IDs.")
        return

    text = await get_media_list_text(db)
    await message.answer(text, parse_mode="HTML")


@router.callback_query(F.data == "owner_medialist")
async def cb_owner_medialist(callback: CallbackQuery, db: AsyncSession):
    if callback.from_user.id not in config.ADMIN_IDS and callback.from_user.id not in config.UPLOADER_IDS:
        await callback.answer("❌ Denied. Admin/Uploader only.", show_alert=True)
        return

    text = await get_media_list_text(db)
    # Send a new message so we don't hit the 1024-character caption limit on the home menu
    await callback.message.answer(text, parse_mode="HTML")
    await callback.answer()


@router.message(Command("emojiid"))
async def cmd_emoji_id(message: Message):
    if not config.ADMIN_IDS or message.from_user.id not in config.ADMIN_IDS:
        await message.answer("❌ Denied. Owner only.")
        return

    if not message.reply_to_message:
        await message.answer("⚠️ Reply to a message containing a custom/premium emoji to get its ID.")
        return

    entities = message.reply_to_message.entities or message.reply_to_message.caption_entities
    if not entities:
        await message.answer("❌ No custom/premium emojis detected in that message.")
        return

    found = False
    for ent in entities:
        if ent.type == "custom_emoji":
            await message.answer(
                f"✨ <b>Custom Emoji Detected!</b>\n\n"
                f"• ID: <code>{ent.custom_emoji_id}</code>\n"
                f"• HTML Tag: <code>&lt;tg-emoji emoji-id=\"{ent.custom_emoji_id}\"&gt;😀&lt;/tg-emoji&gt;</code>",
                parse_mode="HTML"
            )
            found = True
            break

    if not found:
        await message.answer("❌ No Telegram Premium/Custom emojis detected in that message.")


async def post_media_update_to_channel(bot: Bot, pokemon: Pokemon, form_index: int, media_value: str, by_user: str):
    from datetime import datetime, timezone, timedelta

    # 1. Resolve form index to name / rarity
    form_names = {
        0: "Standard",
        1: "AMV",
        2: "Dmax",
        3: "Gmax",
        4: "Z-Move",
        5: "Terastal"
    }
    form_name = form_names.get(form_index, f"Form {form_index}")

    # Map to rarity label
    rarity_label = form_name
    if form_index == 1:
        if media_value.startswith("photo:"):
            rarity_label = "Art"
        else:
            rarity_label = "AMV"

    # Clean media value (strip prefix)
    media_id = media_value
    media_type = "video"
    if media_value.startswith("video:"):
        media_id = media_value.replace("video:", "")
        media_type = "video"
    elif media_value.startswith("photo:"):
        media_id = media_value.replace("photo:", "")
        media_type = "photo"
    elif media_value.startswith("animation:"):
        media_id = media_value.replace("animation:", "")
        media_type = "animation"
    else:
        if media_value.startswith("http"):
            media_type = "photo"
        else:
            media_type = "video"

    # Checkbox checks
    is_img = "✅" if media_type == "photo" else "❌"
    is_vid = "✅" if media_type in ["video", "animation"] else "❌"

    # Time in IST
    utc_now = datetime.now(timezone.utc)
    ist_time = utc_now + timedelta(hours=5, minutes=30)
    time_str = ist_time.strftime("%d %b %Y, %I:%M %p IST")

    caption = (
        f"✨ <b>NEW POKÉMON MEDIA ADDED!</b>\n\n"
        f"<blockquote>🆔 <b>ID</b>: #{pokemon.id:03d}.{form_index}\n"
        f"📛 <b>Name</b>: {pokemon.name.title()}\n"
        f"📺 <b>Generation</b>: Gen {pokemon.generation}\n"
        f"💎 <b>Rarity</b>: {rarity_label}\n"
        f"🖼️ <b>Image</b>: {is_img}\n"
        f"🎥 <b>Video</b>: {is_vid}\n"
        f"👤 <b>By</b>: {by_user}\n"
        f"⌛ <b>Time</b>: {time_str}</blockquote>"
    )

    try:
        if media_type == "video":
            await bot.send_video(chat_id=config.UPDATES_CHANNEL, video=media_id, caption=caption, parse_mode="HTML")
        elif media_type == "animation":
            await bot.send_animation(chat_id=config.UPDATES_CHANNEL, animation=media_id, caption=caption, parse_mode="HTML")
        else:
            await bot.send_photo(chat_id=config.UPDATES_CHANNEL, photo=media_id, caption=caption, parse_mode="HTML")
    except Exception as e:
        print(f"⚠️ Failed to post update to channel {config.UPDATES_CHANNEL}: {e}")

@router.message(Command("banword"))
async def cmd_ban_word(message: Message):
    import html
    if message.from_user.id not in config.ADMIN_IDS:
        await message.answer("❌ Denied. Only bot administrators can ban words.")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("⚠️ Format: `/banword <word>`")
        return

    word = parts[1].strip()
    from utils.ban_words import add_ban_word
    added = add_ban_word(word)

    if added:
        await message.answer(f"✅ Banned word '<b>{html.escape(word)}</b>' has been added to the filter list.", parse_mode="HTML")
    else:
        await message.answer(f"⚠️ Word '<b>{html.escape(word)}</b>' is already banned.", parse_mode="HTML")

@router.message(Command("removebanword"))
async def cmd_remove_ban_word(message: Message):
    import html
    if message.from_user.id not in config.ADMIN_IDS:
        await message.answer("❌ Denied. Only bot administrators can manage banned words.")
        return

    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("⚠️ Format: `/removebanword <word>`")
        return

    word = parts[1].strip()
    from utils.ban_words import remove_ban_word
    removed = remove_ban_word(word)

    if removed:
        await message.answer(f"✅ Banned word '<b>{html.escape(word)}</b>' has been removed from the filter list.", parse_mode="HTML")
    else:
        await message.answer(f"⚠️ Word '<b>{html.escape(word)}</b>' was not found in the banned list.", parse_mode="HTML")

@router.message(Command("banwords"))
async def cmd_ban_words(message: Message):
    import html
    if message.from_user.id not in config.ADMIN_IDS:
        await message.answer("❌ Denied. Only bot administrators can check banned words.")
        return

    from utils.ban_words import load_ban_words
    words = load_ban_words()
    if not words:
        await message.answer("📋 No words are currently banned.")
        return

    word_list = "\n".join([f"• <code>{html.escape(w)}</code>" for w in words])
    await message.answer(
        f"📋 <b>BANNED WORDS LIST</b>\n"
        f"───────────────\n"
        f"{word_list}\n"
        f"───────────────",
        parse_mode="HTML"
    )

# -------------------------------------------------------------
# EXECUTIVE OWNER PANEL (/panel) & PLAYER ANALYTICS
# -------------------------------------------------------------

async def send_or_edit_panel(event: Message | CallbackQuery, db: AsyncSession, owner_name: str):
    from sqlalchemy import func
    import html
    
    u_count = await db.execute(select(func.count(User.id)))
    total_users = u_count.scalar() or 0

    c_count = await db.execute(select(func.count(UserPokemon.id)))
    total_catches = c_count.scalar() or 0

    s_count = await db.execute(select(func.count(ActiveSpawn.chat_id)))
    active_spawns = s_count.scalar() or 0

    coins_sum = await db.execute(select(func.sum(User.coins)))
    total_coins = coins_sum.scalar() or 0

    shiny_count = await db.execute(select(func.count(UserPokemon.id)).where(UserPokemon.is_shiny == True))
    total_shinies = shiny_count.scalar() or 0

    text = (
        f"👑 <b>EXECUTIVE OWNER PANEL</b> 👑\n"
        f"💎 <i>System Analytics & Control Center</i>\n"
        f"───────────────\n"
        f"👤 Creator: <b>{html.escape(owner_name)}</b>\n\n"
        f"<blockquote>📊 <b>EMPIRE METRICS</b>\n"
        f"• 👥 Trainers: <code>{total_users:,}</code>\n"
        f"• ⚡ Catches: <code>{total_catches:,}</code> (✨ <code>{total_shinies:,}</code>)\n"
        f"• 💰 Economy: <code>{total_coins:,} coins</code>\n"
        f"• 🌳 Spawns: <code>{active_spawns:,} active</code></blockquote>\n\n"
        f"<blockquote>⚡ <b>EXECUTIVE SHORTCUTS</b>\n"
        f"• <code>/spawn [rarity]</code> | <code>/spawnchance</code>\n"
        f"• <code>/giftcoins</code> | <code>/deletecoins</code> | <code>/balance</code>\n"
        f"• <code>/giftpokemon</code> | <code>/gen</code> | <code>/addadmin</code></blockquote>\n"
        f"───────────────"
    )

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="👥 Browse Players", callback_data="panel_players_1"),
        InlineKeyboardButton(text="🏆 Wealth Ranks", callback_data="panel_wealth_1")
    )
    builder.row(
        InlineKeyboardButton(text="⚡ Trigger Spawn", callback_data="panel_spawn_prompt"),
        InlineKeyboardButton(text="🎫 Redeem Codes", callback_data="panel_gen_prompt")
    )
    builder.row(
        InlineKeyboardButton(text="👑 Manage Admins", callback_data="owner_adminlist"),
        InlineKeyboardButton(text="📋 Custom Media", callback_data="owner_medialist")
    )
    builder.row(InlineKeyboardButton(text="🔙 Back to Hub Menu", callback_data="dm_home"))

    if isinstance(event, Message):
        await event.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    else:
        try:
            await event.message.edit_caption(caption=text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception:
            try:
                await event.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
            except Exception:
                try:
                    await event.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
                except Exception:
                    pass
        await event.answer()

@router.message(Command("panel", "p", "ownerpanel", "adminpanel", "control", "admin"))
async def cmd_owner_panel(message: Message, db: AsyncSession):
    try:
        owner_name = message.from_user.first_name if message.from_user else "Creator"
        await send_or_edit_panel(message, db, owner_name)
    except Exception as e:
        print(f"Error in cmd_owner_panel: {e}")
        import traceback
        traceback.print_exc()

@router.callback_query(F.data == "owner_panel")
async def cb_owner_panel(callback: CallbackQuery, db: AsyncSession):
    owner_name = callback.from_user.first_name if callback.from_user else "Creator"
    await send_or_edit_panel(callback, db, owner_name)

@router.callback_query(F.data.startswith("panel_players_"))
async def cb_panel_players(callback: CallbackQuery, db: AsyncSession):
    page = int(callback.data.replace("panel_players_", ""))
    per_page = 5

    # Count total users
    count_res = await db.execute(select(func.count(User.id)))
    total_users = count_res.scalar() or 0
    max_pages = max(1, (total_users + per_page - 1) // per_page)
    page = max(1, min(page, max_pages))

    offset = (page - 1) * per_page
    stmt = select(User).order_by(User.id).offset(offset).limit(per_page)
    res = await db.execute(stmt)
    users = res.scalars().all()

    import html
    lines = [f"👥 <b>ALL TRAINERS DIRECTORY (Page {page}/{max_pages})</b>\n───────────────────────────────"]
    
    for u in users:
        u_name = html.escape(u.nickname or u.username or "Trainer")
        u_handle = f" (@{html.escape(u.username)})" if u.username else ""
        
        # Count catches for this user
        c_stmt = select(func.count(UserPokemon.id)).where(UserPokemon.user_id == u.id)
        c_res = await db.execute(c_stmt)
        u_catches = c_res.scalar() or 0

        lines.append(
            f"• 👤 <b>{u_name}</b>{u_handle}\n"
            f"  └ 🆔 <code>{u.id}</code> | 💰 <code>{u.coins:,}</code> coins | 🎒 <code>{u_catches:,}</code> caught"
        )

    lines.append("───────────────────────────────")
    text = "\n\n".join(lines)

    builder = InlineKeyboardBuilder()
    nav_btns = []
    if page > 1:
        nav_btns.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"panel_players_{page-1}"))
    if page < max_pages:
        nav_btns.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"panel_players_{page+1}"))
    if nav_btns:
        builder.row(*nav_btns)
    builder.row(InlineKeyboardButton(text="🔙 Back to Executive Panel", callback_data="owner_panel"))

    try:
        await callback.message.edit_caption(caption=text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        try:
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception:
            try:
                await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
            except Exception:
                pass
    await callback.answer()

@router.callback_query(F.data.startswith("panel_wealth_"))
async def cb_panel_wealth(callback: CallbackQuery, db: AsyncSession):
    page = int(callback.data.replace("panel_wealth_", ""))
    per_page = 5

    count_res = await db.execute(select(func.count(User.id)))
    total_users = count_res.scalar() or 0
    max_pages = max(1, (total_users + per_page - 1) // per_page)
    page = max(1, min(page, max_pages))

    offset = (page - 1) * per_page
    stmt = select(User).order_by(User.coins.desc()).offset(offset).limit(per_page)
    res = await db.execute(stmt)
    users = res.scalars().all()

    import html
    lines = [f"🏆 <b>WEALTHY TRAINERS RANKINGS (Page {page}/{max_pages})</b>\n───────────────────────────────"]
    
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    for idx, u in enumerate(users):
        rank_idx = offset + idx
        medal = medals[rank_idx] if rank_idx < len(medals) else f"{rank_idx+1}."
        u_name = html.escape(u.nickname or u.username or "Trainer")
        lines.append(f"{medal} 👤 <b>{u_name}</b> (<code>{u.id}</code>)\n   └ 💰 Balance: <b>{u.coins:,} coins</b>")

    lines.append("───────────────────────────────")
    text = "\n\n".join(lines)

    builder = InlineKeyboardBuilder()
    nav_btns = []
    if page > 1:
        nav_btns.append(InlineKeyboardButton(text="◀️ Prev", callback_data=f"panel_wealth_{page-1}"))
    if page < max_pages:
        nav_btns.append(InlineKeyboardButton(text="Next ➡️", callback_data=f"panel_wealth_{page+1}"))
    if nav_btns:
        builder.row(*nav_btns)
    builder.row(InlineKeyboardButton(text="🔙 Back to Executive Panel", callback_data="owner_panel"))

    try:
        await callback.message.edit_caption(caption=text, reply_markup=builder.as_markup(), parse_mode="HTML")
    except Exception:
        try:
            await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        except Exception:
            pass
    await callback.answer()

@router.callback_query(F.data == "panel_spawn_prompt")
async def cb_panel_spawn_prompt(callback: CallbackQuery):
    await callback.answer("👉 Use /spawn or /spawn <rarity> in any group chat to trigger a wild encounter!", show_alert=True)

@router.callback_query(F.data == "panel_gen_prompt")
async def cb_panel_gen_prompt(callback: CallbackQuery):
    await callback.answer("👉 Use /gen <code_name> <usage_limit> <coins|pokemon_id> <value> to generate a redeem code!", show_alert=True)
