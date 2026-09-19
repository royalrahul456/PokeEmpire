import os
import json
import config
from sqlalchemy import select, update, delete
from database.database import SessionLocal
from database.models import GroupSetting, GlobalSetting
from typing import Any, Optional
from aiogram import Bot
from aiogram.types import FSInputFile, Message
from aiogram.exceptions import TelegramBadRequest

# Settings & Media cache
scribble_settings_cache = {}
nameguess_settings_cache = {}
global_settings_cache = {}

DEFAULT_SPAWN_SETTINGS = {
    "group_rarity_probabilities": {
        "Common": 70,
        "Rare": 20,
        "Epic": 7,
        "Legendary": 2,
        "Mythical": 1
    }
}

async def load_all_settings_into_cache():
    """Startup initialization: loads all database settings into memory cache and migrates old json files if present."""
    global scribble_settings_cache, nameguess_settings_cache, global_settings_cache
    
    async with SessionLocal() as db:
        # 1. Load Group Settings
        stmt = select(GroupSetting)
        res = await db.execute(stmt)
        for gs in res.scalars().all():
            scribble_settings_cache[gs.chat_id] = gs.scribble_enabled
            nameguess_settings_cache[gs.chat_id] = gs.nameguess_enabled

        # 2. Load Global Settings
        stmt = select(GlobalSetting)
        res = await db.execute(stmt)
        for gs in res.scalars().all():
            global_settings_cache[gs.key] = gs.value

        # 3. Migrate Scribble Settings JSON
        scribble_json = os.path.join("data", "scribble_settings.json")
        if os.path.exists(scribble_json):
            try:
                with open(scribble_json, "r", encoding="utf-8") as f:
                    old_scribble = json.load(f)
                for chat_id_str, enabled in old_scribble.items():
                    try:
                        chat_id = int(chat_id_str)
                        # Store in db and cache
                        gs_stmt = select(GroupSetting).where(GroupSetting.chat_id == chat_id)
                        gs_res = await db.execute(gs_stmt)
                        gs = gs_res.scalar_one_or_none()
                        if gs:
                            gs.scribble_enabled = enabled
                        else:
                            gs = GroupSetting(chat_id=chat_id, scribble_enabled=enabled, nameguess_enabled=True)
                            db.add(gs)
                        scribble_settings_cache[chat_id] = enabled
                    except ValueError:
                        continue
                await db.commit()
                # Remove migrated file
                try:
                    os.remove(scribble_json)
                except Exception:
                    pass
                print(f"✨ Migrated {scribble_json} to DB successfully.")
            except Exception as e:
                print(f"Error migrating scribble json: {e}")

        # 4. Migrate Spawn Settings JSON
        spawn_json = os.path.join("data", "spawn_settings.json")
        if os.path.exists(spawn_json):
            try:
                with open(spawn_json, "r", encoding="utf-8") as f:
                    old_spawn = json.load(f)
                
                if "group_rarity_probabilities" not in global_settings_cache:
                    val = json.dumps(old_spawn.get("group_rarity_probabilities", DEFAULT_SPAWN_SETTINGS["group_rarity_probabilities"]))
                    db.add(GlobalSetting(key="group_rarity_probabilities", value=val))
                    global_settings_cache["group_rarity_probabilities"] = val
                    
                await db.commit()
                # Remove migrated file
                try:
                    os.remove(spawn_json)
                except Exception:
                    pass
                print(f"✨ Migrated {spawn_json} to DB successfully.")
            except Exception as e:
                print(f"Error migrating spawn json: {e}")

def is_scribble_enabled(chat_id: int) -> bool:
    return scribble_settings_cache.get(chat_id, True)

def is_nameguess_enabled(chat_id: int) -> bool:
    return nameguess_settings_cache.get(chat_id, True)

async def set_scribble_status(chat_id: int, enabled: bool):
    scribble_settings_cache[chat_id] = enabled
    async with SessionLocal() as db:
        stmt = select(GroupSetting).where(GroupSetting.chat_id == chat_id)
        res = await db.execute(stmt)
        gs = res.scalar_one_or_none()
        if gs:
            gs.scribble_enabled = enabled
        else:
            gs = GroupSetting(chat_id=chat_id, scribble_enabled=enabled, nameguess_enabled=True)
            db.add(gs)
        await db.commit()

async def set_nameguess_status(chat_id: int, enabled: bool):
    nameguess_settings_cache[chat_id] = enabled
    async with SessionLocal() as db:
        stmt = select(GroupSetting).where(GroupSetting.chat_id == chat_id)
        res = await db.execute(stmt)
        gs = res.scalar_one_or_none()
        if gs:
            gs.nameguess_enabled = enabled
        else:
            gs = GroupSetting(chat_id=chat_id, scribble_enabled=True, nameguess_enabled=enabled)
            db.add(gs)
        await db.commit()

def load_spawn_settings() -> dict:
    """Synchronous read from cache with default fallback."""
    probs_val = global_settings_cache.get("group_rarity_probabilities", None)
    if probs_val:
        try:
            group_rarity_probabilities = json.loads(probs_val)
        except Exception:
            group_rarity_probabilities = DEFAULT_SPAWN_SETTINGS["group_rarity_probabilities"]
    else:
        group_rarity_probabilities = DEFAULT_SPAWN_SETTINGS["group_rarity_probabilities"]
        
    return {
        "group_rarity_probabilities": group_rarity_probabilities
    }

async def save_spawn_settings(settings: dict):
    probs = settings.get("group_rarity_probabilities", DEFAULT_SPAWN_SETTINGS["group_rarity_probabilities"])
    global_settings_cache["group_rarity_probabilities"] = json.dumps(probs)
    
    async with SessionLocal() as db:
        k = "group_rarity_probabilities"
        v = global_settings_cache["group_rarity_probabilities"]
        stmt = select(GlobalSetting).where(GlobalSetting.key == k)
        res = await db.execute(stmt)
        gs = res.scalar_one_or_none()
        if gs:
            gs.value = v
        else:
            db.add(GlobalSetting(key=k, value=v))
        await db.commit()

# Custom covers helper functions
def get_custom_cover(key: str) -> tuple:
    """Returns (media_type, media_value) or (None, None). Checks local disk first, then cache."""
    # 1. Check local files on disk
    cover_dirs = [os.path.join("data", "covers")]
    if os.path.exists(getattr(config, "PERSISTENT_VOLUME", "/app/data_volume")):
        cover_dirs.insert(0, os.path.join(getattr(config, "PERSISTENT_VOLUME", "/app/data_volume"), "covers"))

    for c_dir in cover_dirs:
        if os.path.exists(c_dir):
            for ext, mtype in [("mp4", "video"), ("webm", "video"), ("gif", "animation"), ("jpg", "photo"), ("jpeg", "photo"), ("png", "photo")]:
                candidate = os.path.join(c_dir, f"{key}.{ext}")
                if os.path.exists(candidate) and os.path.getsize(candidate) > 0:
                    return mtype, candidate

    # 2. Check global settings cache
    config_json = global_settings_cache.get(f"cover_{key}", None)
    if config_json:
        try:
            data = json.loads(config_json)
            return data.get("type"), data.get("value")
        except Exception:
            pass
    return None, None

async def get_custom_cover_async(key: str) -> tuple:
    """Async retrieval: checks disk, cache, and if missing, queries DB."""
    m_type, m_val = get_custom_cover(key)
    if m_type is not None:
        return m_type, m_val

    try:
        async with SessionLocal() as db:
            stmt = select(GlobalSetting).where(GlobalSetting.key == f"cover_{key}")
            res = await db.execute(stmt)
            gs = res.scalar_one_or_none()
            if gs and gs.value:
                global_settings_cache[f"cover_{key}"] = gs.value
                data = json.loads(gs.value)
                return data.get("type"), data.get("value")
    except Exception as e:
        print(f"Error querying custom cover from DB: {e}")

    return None, None

async def set_custom_cover(key: str, media_type: str, media_value: str):
    data = {"type": media_type, "value": media_value}
    data_str = json.dumps(data)
    global_settings_cache[f"cover_{key}"] = data_str
    
    async with SessionLocal() as db:
        stmt = select(GlobalSetting).where(GlobalSetting.key == f"cover_{key}")
        res = await db.execute(stmt)
        gs = res.scalar_one_or_none()
        if gs:
            gs.value = data_str
        else:
            db.add(GlobalSetting(key=f"cover_{key}", value=data_str))
        await db.commit()

async def delete_custom_cover(key: str):
    if f"cover_{key}" in global_settings_cache:
        del global_settings_cache[f"cover_{key}"]

    # Remove any local files on disk
    cover_dirs = [os.path.join("data", "covers")]
    if os.path.exists(getattr(config, "PERSISTENT_VOLUME", "/app/data_volume")):
        cover_dirs.insert(0, os.path.join(getattr(config, "PERSISTENT_VOLUME", "/app/data_volume"), "covers"))

    for c_dir in cover_dirs:
        if os.path.exists(c_dir):
            for ext in ["mp4", "webm", "gif", "jpg", "jpeg", "png"]:
                candidate = os.path.join(c_dir, f"{key}.{ext}")
                if os.path.exists(candidate):
                    try:
                        os.remove(candidate)
                    except Exception:
                        pass

    async with SessionLocal() as db:
        stmt = delete(GlobalSetting).where(GlobalSetting.key == f"cover_{key}")
        await db.execute(stmt)
        await db.commit()

async def send_safe_media(
    bot: Bot,
    chat_id: int,
    media_type: Optional[str],
    media_value: Any,
    caption: Optional[str] = None,
    reply_markup: Any = None,
    parse_mode: str = "HTML",
    message_to_reply: Optional[Message] = None
) -> Message:
    """
    Safely sends media (photo, video, animation) with automatic type fallback.
    If a video file_id is stored but Telegram considers it a photo (or vice versa),
    it retries with alternative media types before falling back to plain text.
    """
    if not media_value:
        if message_to_reply:
            return await message_to_reply.answer(text=caption or "", reply_markup=reply_markup, parse_mode=parse_mode)
        return await bot.send_message(chat_id=chat_id, text=caption or "", reply_markup=reply_markup, parse_mode=parse_mode)

    if isinstance(media_value, str) and os.path.exists(media_value):
        media_value = FSInputFile(media_value)

    primary = (media_type or "photo").lower()
    if primary == "video":
        attempts = ["video", "photo", "animation"]
    elif primary == "animation":
        attempts = ["animation", "video", "photo"]
    else:
        attempts = ["photo", "video", "animation"]

    last_error = None
    for mtype in attempts:
        try:
            if message_to_reply:
                if mtype == "video":
                    return await message_to_reply.answer_video(video=media_value, caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)
                elif mtype == "animation":
                    return await message_to_reply.answer_animation(animation=media_value, caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)
                else:
                    return await message_to_reply.answer_photo(photo=media_value, caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)
            else:
                if mtype == "video":
                    return await bot.send_video(chat_id=chat_id, video=media_value, caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)
                elif mtype == "animation":
                    return await bot.send_animation(chat_id=chat_id, animation=media_value, caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)
                else:
                    return await bot.send_photo(chat_id=chat_id, photo=media_value, caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)
        except TelegramBadRequest as e:
            err_msg = str(e).lower()
            last_error = e
            if any(p in err_msg for p in ["can't use file of type", "wrong file type", "failed to get http url", "wrong type", "invalid file", "failed to get url", "type"]):
                print(f"⚠️ send_safe_media: {mtype} failed with '{e}'. Trying fallback media type...")
                continue
            print(f"⚠️ send_safe_media TelegramBadRequest on {mtype}: {e}. Falling back to text.")
            break
        except Exception as e:
            last_error = e
            print(f"⚠️ send_safe_media error on {mtype}: {e}")
            continue

    # Final fallback: text message (first with parse_mode, then raw plain text)
    try:
        if message_to_reply:
            return await message_to_reply.answer(text=caption or "", reply_markup=reply_markup, parse_mode=parse_mode)
        return await bot.send_message(chat_id=chat_id, text=caption or "", reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        print(f"⚠️ send_safe_media formatted text failed: {e}. Retrying without formatting...")
        try:
            if message_to_reply:
                return await message_to_reply.answer(text=caption or "", reply_markup=reply_markup, parse_mode=None)
            return await bot.send_message(chat_id=chat_id, text=caption or "", reply_markup=reply_markup, parse_mode=None)
        except Exception as e2:
            print(f"❌ send_safe_media plain text fallback failed: {e2}")
            try:
                return await bot.send_message(chat_id=chat_id, text=caption or "", reply_markup=reply_markup, parse_mode=None)
            except Exception as e3:
                if last_error:
                    raise last_error
                raise e3


async def send_cover_media(chat_id: int, key: str, caption: str, reply_markup, bot: Bot, default_url=None, default_file=None, parse_mode="HTML"):
    """Sends the configured custom media (photo, video, or animation) or falls back to defaults."""
    media_type, media_value = await get_custom_cover_async(key)
    
    # If media_value is a file_id, try to download and cache locally for cross-bot sharing
    if media_value and isinstance(media_value, str) and not os.path.exists(media_value) and not media_value.startswith("http"):
        cover_dir = os.path.join("data", "covers")
        if os.path.exists(getattr(config, "PERSISTENT_VOLUME", "/app/data_volume")):
            cover_dir = os.path.join(getattr(config, "PERSISTENT_VOLUME", "/app/data_volume"), "covers")
        os.makedirs(cover_dir, exist_ok=True)
        ext = "mp4" if media_type == "video" else ("gif" if media_type == "animation" else "jpg")
        dest = os.path.join(cover_dir, f"{key}.{ext}")
        
        # 1. Try downloading with current bot
        downloaded = False
        try:
            await bot.download(file=media_value, destination=dest)
            if os.path.exists(dest) and os.path.getsize(dest) > 0:
                media_value = dest
                downloaded = True
        except Exception:
            pass

        # 2. If current bot cannot access file_id, try with other bot token (e.g. Main Bot token)
        if not downloaded:
            for candidate_token in [getattr(config, "BOT_TOKEN", None), getattr(config, "GAMES_BOT_TOKEN", None)]:
                if candidate_token and candidate_token != getattr(bot, "token", None):
                    fallback_bot = None
                    try:
                        fallback_bot = Bot(token=candidate_token)
                        await fallback_bot.download(file=media_value, destination=dest)
                        if os.path.exists(dest) and os.path.getsize(dest) > 0:
                            media_value = dest
                            downloaded = True
                            break
                    except Exception:
                        pass
                    finally:
                        if fallback_bot:
                            try:
                                await fallback_bot.session.close()
                            except Exception:
                                pass

    if not media_type or (isinstance(media_value, str) and not os.path.exists(media_value) and not media_value.startswith("http") and not media_type):
        if default_file and os.path.exists(default_file):
            media_type = "photo"
            media_value = default_file
        elif default_url:
            media_type = "photo"
            media_value = default_url

    try:
        return await send_safe_media(
            bot=bot,
            chat_id=chat_id,
            media_type=media_type,
            media_value=media_value,
            caption=caption,
            reply_markup=reply_markup,
            parse_mode=parse_mode
        )
    except Exception as e:
        print(f"⚠️ send_cover_media failed for {key} with custom media ({e}). Retrying with default fallback...")
        fb_val = default_file if (default_file and os.path.exists(default_file)) else default_url
        if fb_val:
            try:
                return await send_safe_media(
                    bot=bot,
                    chat_id=chat_id,
                    media_type="photo",
                    media_value=fb_val,
                    caption=caption,
                    reply_markup=reply_markup,
                    parse_mode=parse_mode
                )
            except Exception:
                pass
        return await bot.send_message(chat_id=chat_id, text=caption, reply_markup=reply_markup, parse_mode=parse_mode)


async def get_all_custom_rarities(db) -> dict:
    from database.models import GlobalSetting
    import json
    stmt = select(GlobalSetting).where(GlobalSetting.key == "custom_rarities")
    res = await db.execute(stmt)
    setting = res.scalar_one_or_none()
    if setting and setting.value:
        try:
            return json.loads(setting.value)
        except Exception:
            pass
    return {}

async def get_custom_rarity_forms(db) -> dict[int, tuple[str, str]]:
    custom_rarities = await get_all_custom_rarities(db)
    standard = {"Common", "Uncommon", "Medium", "Rare", "Epic", "Legendary", "Mythical", "Limited", "Limited Edition"}
    custom_list = [r for r in custom_rarities.keys() if r not in standard]
    
    mapping = {}
    
    shiny_name = None
    for r in custom_list:
        if r.lower() == "shiny":
            shiny_name = r
            break
            
    if shiny_name:
        mapping[6] = (shiny_name, custom_rarities[shiny_name])
    else:
        mapping[6] = ("Shiny", "✨")
        
    next_idx = 7
    for r in custom_list:
        if r.lower() == "shiny":
            continue
        mapping[next_idx] = (r, custom_rarities[r])
        next_idx += 1
        
    return mapping


async def is_pokemon_soulbound(pokemon, user_pokemon=None, db=None) -> bool:
    """Checks if a Pokémon or its form belongs to the soulbound/event-winner exclusive rarity tier."""
    keywords = ("exclusive", "event", "winner", "bound")

    # 1. Check Pokémon base rarity
    if pokemon and getattr(pokemon, "rarity", None):
        r = str(pokemon.rarity).lower()
        if any(k in r for k in keywords):
            return True

    # 2. Check UserPokemon form_index (custom form rarity)
    if user_pokemon and getattr(user_pokemon, "form_index", 0) > 0 and db:
        try:
            custom_forms = await get_custom_rarity_forms(db)
            if user_pokemon.form_index in custom_forms:
                form_name, _ = custom_forms[user_pokemon.form_index]
                fn = str(form_name).lower()
                if any(k in fn for k in keywords):
                    return True
        except Exception:
            pass

    # 3. Check custom_rarities list in DB if available
    if db and pokemon and getattr(pokemon, "rarity", None):
        try:
            custom_rarities = await get_all_custom_rarities(db)
            for r_name in custom_rarities.keys():
                rn_lower = str(r_name).lower()
                if any(k in rn_lower for k in keywords):
                    if str(pokemon.rarity).lower() == rn_lower:
                        return True
        except Exception:
            pass

    return False

