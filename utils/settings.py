import os
import json
from sqlalchemy import select, update, delete
from database.database import SessionLocal
from database.models import GroupSetting, GlobalSetting
from aiogram import Bot
from aiogram.types import FSInputFile

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
    """Returns (media_type, media_value) or (None, None)"""
    config_json = global_settings_cache.get(f"cover_{key}", None)
    if config_json:
        try:
            data = json.loads(config_json)
            return data.get("type"), data.get("value")
        except Exception:
            pass
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
    async with SessionLocal() as db:
        stmt = delete(GlobalSetting).where(GlobalSetting.key == f"cover_{key}")
        await db.execute(stmt)
        await db.commit()

async def send_cover_media(chat_id: int, key: str, caption: str, reply_markup, bot: Bot, default_url=None, default_file=None, parse_mode="HTML"):
    """Sends the configured custom media (photo, video, or animation) or falls back to defaults."""
    media_type, media_value = get_custom_cover(key)
    
    if not media_type:
        # Fallback to default
        if default_file and os.path.exists(default_file):
            media_type = "photo"
            media_value = FSInputFile(default_file)
        elif default_url:
            media_type = "photo"
            media_value = default_url
        else:
            # Fallback text if no media
            return await bot.send_message(chat_id, caption, reply_markup=reply_markup, parse_mode=parse_mode)

    # If it is a string representing a local path, wrap it in FSInputFile
    if isinstance(media_value, str) and os.path.exists(media_value):
        media_value = FSInputFile(media_value)

    try:
        if media_type == "photo":
            return await bot.send_photo(chat_id, photo=media_value, caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)
        elif media_type == "video":
            return await bot.send_video(chat_id, video=media_value, caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)
        elif media_type == "animation":
            return await bot.send_animation(chat_id, animation=media_value, caption=caption, reply_markup=reply_markup, parse_mode=parse_mode)
        else:
            return await bot.send_message(chat_id, caption, reply_markup=reply_markup, parse_mode=parse_mode)
    except Exception as e:
        print(f"Error sending cover media: {e}. Falling back to default message...")
        return await bot.send_message(chat_id, caption, reply_markup=reply_markup, parse_mode=parse_mode)


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
