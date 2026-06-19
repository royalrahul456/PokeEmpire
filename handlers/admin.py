from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
import config
from database.models import GroupSetting, User, Pokemon, UserPokemon
from utils.formatters import get_progress_bar, get_rarity_emoji, escape_md

router = Router()

async def is_user_admin(message: Message) -> bool:
    """Helper to check if the user is a bot administrator or a group administrator."""
    # Global bot admins bypass checks
    if message.from_user.id in config.ADMIN_IDS:
        return True

    # Private chat actions are allowed
    if message.chat.type == "private":
        return True

    # Check Telegram group administrator rights
    try:
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
    if threshold < 5 or threshold > 1000:
        await message.answer("⚠️ Threshold must be between 5 and 1000 messages.")
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
            spawn_threshold=3,
            enabled=False  # Toggle turns off if creating new
        )
        db.add(setting)
    else:
        setting.enabled = not setting.enabled

    await db.commit()

    if setting.enabled:
        await message.answer("🌲 **Spawns Enabled!** Wild Pokémon will now spawn in this group chat.")
    else:
        await message.answer("🚫 **Spawns Disabled.** Spawning has been turned off for this group chat.")

@router.message(Command("adminlist", "admins"))
async def cmd_admin_list(message: Message, db: AsyncSession):
    if not config.ADMIN_IDS:
        await message.answer("ℹ️ **Bot Administrators**: None configured.")
        return

    # Query database for matching registered bot admins
    stmt = select(User).where(User.id.in_(config.ADMIN_IDS))
    res = await db.execute(stmt)
    registered_users = res.scalars().all()
    registered_ids = {u.id: u for u in registered_users}

    owner_row = None
    admin_rows = []
    
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

    text = (
        f"👑 **BOT ROSTER** 👑\n"
        f"───────────────\n\n"
        f"👑 **OWNER**\n"
        f"{owner_row}\n\n"
    )
    if admin_rows:
        text += "🛡️ **ADMIN**\n" + "\n".join(admin_rows) + "\n\n"
    
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
            spawn_threshold=random.randint(3, 5),
            enabled=True
        )
        db.add(setting)
        await db.commit()

    status_str = "🟢 **Enabled**" if setting.enabled else "🔴 **Disabled**"
    remaining = max(0, setting.spawn_threshold - setting.message_counter)
    
    # Generate progress bar
    bar = get_progress_bar(setting.message_counter, setting.spawn_threshold, 10)
    
    # Format message
    text = (
        f"⚙️ **SPAWN SETTINGS** ⚙️\n"
        f"───────────────\n"
        f"📡 **Status**: {status_str}\n"
        f"⏱️ **Spawn Interval**: `Every {setting.spawn_threshold} messages`\n\n"
        f"📊 **Activity Progress**:\n"
        f"`[{bar}]` `{setting.message_counter}/{setting.spawn_threshold}`\n\n"
        f"✉️ **Next Spawn**: In **{remaining} messages**!"
    )
    
    if not setting.enabled:
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
    text = (
        f"🎁 **COINS GIFTED** 🎁\n"
        f"───────────────\n"
        f"Bot Owner **{escape_md(admin_name)}** gifted:\n"
        f"💰 **+{amount} coins**\n\n"
        f"👤 Recipient: **{escape_md(target_user.nickname)}**\n"
        f"💰 New Balance: `💰 {target_user.coins} coins`\n"
        f"───────────────"
    )
    await message.answer(text, parse_mode="Markdown")

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
        if len(parts) > 2 and parts[2].lower() in ["shiny", "s"]:
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
        
        if len(parts) > 3 and parts[3].lower() in ["shiny", "s"]:
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

    # Roll stats/IVs
    import random
    iv_hp = random.randint(0, 31)
    iv_atk = random.randint(0, 31)
    iv_def = random.randint(0, 31)
    iv_spd = random.randint(0, 31)
    iv_total = iv_hp + iv_atk + iv_def + iv_spd
    iv_pct = int((iv_total / 124) * 100)

    # Insert UserPokemon
    new_poke = UserPokemon(
        user_id=target_user.id,
        pokemon_id=pokemon.id,
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

    hp_bar = get_progress_bar(iv_hp, 31, 5, fill_char="▰", empty_char="▱")
    atk_bar = get_progress_bar(iv_atk, 31, 5, fill_char="▰", empty_char="▱")
    def_bar = get_progress_bar(iv_def, 31, 5, fill_char="▰", empty_char="▱")
    spd_bar = get_progress_bar(iv_spd, 31, 5, fill_char="▰", empty_char="▱")

    shiny_badge = "✨ Shiny " if is_shiny else ""
    r_emoji = get_rarity_emoji(pokemon.rarity)
    admin_name = message.from_user.first_name

    text = (
        f"🎁 **POKÉMON GIFTED** 🎁\n"
        f"───────────────\n"
        f"Bot Owner **{escape_md(admin_name)}** gifted a Pokémon!\n\n"
        f"👤 Recipient: **{escape_md(target_user.nickname)}**\n"
        f"🎉 Unwrapped: {r_emoji} {shiny_badge}**{pokemon.name.title()}** `(Lvl 1)`\n"
        f"🧬 **IV Quality**: `🧬 {iv_pct}%`\n"
        f"• HP IV: `[{hp_bar}]` `({iv_hp}/31)`\n"
        f"• ATK IV: `[{atk_bar}]` `({iv_atk}/31)`\n"
        f"• DEF IV: `[{def_bar}]` `({iv_def}/31)`\n"
        f"• SPD IV: `[{spd_bar}]` `({iv_spd}/31)`\n"
        f"───────────────"
    )
    await message.answer(text, parse_mode="Markdown")

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
    
    # Save to .env
    update_env_admin_ids(config.ADMIN_IDS)

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
    
    # Save to .env
    update_env_admin_ids(config.ADMIN_IDS)

    text = (
        f"🛡️ **ADMINISTRATOR REMOVED** 🛡️\n"
        f"───────────────\n"
        f"User **{escape_md(target_name)}** `(ID: {target_id})` has been removed from the Bot Administrator list.\n"
        f"───────────────"
    )
    await message.answer(text, parse_mode="Markdown")

