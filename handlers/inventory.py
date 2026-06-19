from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
import config
from database.models import User, Inventory, UserMonster
from keyboards.inline import get_bag_keyboard, get_team_management_keyboard
from services.evolution_system import EvolutionSystem
from services.spawn_system import SpawnSystem

router = Router()
evolution_system = EvolutionSystem()
spawn_system = SpawnSystem()

@router.message(Command("bag"))
@router.message(Command("items"))
@router.callback_query(F.data == "menu_bag")
async def cmd_bag(event: Message | CallbackQuery, db: AsyncSession):
    user_id = event.from_user.id
    
    # Check registration
    stmt = select(User).where(User.id == user_id)
    res = await db.execute(stmt)
    user = res.scalar_one_or_none()
    if not user:
        msg = "⚠️ You must register first with /start"
        if isinstance(event, CallbackQuery):
            await event.answer(msg, show_alert=True)
        else:
            await event.answer(msg)
        return

    text = (
        f"🎒 **Trainer Bag & Squad Manager** 🎒\n\n"
        f"Manage your active battle squad, feed items to your monsters, and review stones and capture balls."
    )
    
    if isinstance(event, CallbackQuery):
        await event.message.edit_text(text, reply_markup=get_bag_keyboard(), parse_mode="Markdown")
        await event.answer()
    else:
        await event.answer(text, reply_markup=get_bag_keyboard(), parse_mode="Markdown")

@router.callback_query(F.data == "bag_team_menu")
@router.callback_query(F.data.startswith("team_page_"))
async def callback_team_menu(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id
    page = 0
    if callback.data.startswith("team_page_"):
        page = int(callback.data.split("_")[2])

    # Query active team
    stmt_team = select(UserMonster).where(
        UserMonster.user_id == user_id,
        UserMonster.is_in_team == True
    ).order_by(UserMonster.team_slot)
    res_team = await db.execute(stmt_team)
    team_monsters = res_team.scalars().all()

    # Query PC storage monsters
    stmt_pc = select(UserMonster).where(
        UserMonster.user_id == user_id,
        UserMonster.is_in_team == False
    )
    res_pc = await db.execute(stmt_pc)
    pc_monsters = res_pc.scalars().all()

    text = (
        f"💪 **Active Combat Team** ({len(team_monsters)}/6)\n"
        f"Your active team is used during fights and PvE training. "
        f"Click a slot to remove, or click storage monsters to add them to your active slots."
    )

    keyboard = get_team_management_keyboard(team_monsters, pc_monsters, page=page)
    await callback.message.edit_text(text, reply_markup=keyboard, parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("team_add_"))
async def callback_team_add(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id
    monster_id_db = int(callback.data.split("_")[2])

    # Check team size
    stmt_team = select(UserMonster).where(
        UserMonster.user_id == user_id,
        UserMonster.is_in_team == True
    )
    res_team = await db.execute(stmt_team)
    team_size = len(res_team.scalars().all())

    if team_size >= 6:
        await callback.answer("⚠️ Active team is full! Remove a monster first.", show_alert=True)
        return

    # Find monster and set in team
    stmt_mon = select(UserMonster).where(
        UserMonster.id == monster_id_db,
        UserMonster.user_id == user_id
    )
    res_mon = await db.execute(stmt_mon)
    monster = res_mon.scalar_one_or_none()

    if monster:
        monster.is_in_team = True
        monster.team_slot = team_size + 1
        await db.commit()
        await callback.answer(f"Added {monster.name} to team!")
    
    # Reload menu
    callback.data = "bag_team_menu"
    await callback_team_menu(callback, db)

@router.callback_query(F.data.startswith("team_remove_"))
async def callback_team_remove(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id
    monster_id_db = int(callback.data.split("_")[2])

    stmt_mon = select(UserMonster).where(
        UserMonster.id == monster_id_db,
        UserMonster.user_id == user_id
    )
    res_mon = await db.execute(stmt_mon)
    monster = res_mon.scalar_one_or_none()

    if monster:
        monster.is_in_team = False
        monster.team_slot = None
        await db.commit()
        
        # Shift slots of other team members to fill gap
        stmt_team = select(UserMonster).where(
            UserMonster.user_id == user_id,
            UserMonster.is_in_team == True
        ).order_by(UserMonster.team_slot)
        res_team = await db.execute(stmt_team)
        team = res_team.scalars().all()
        for idx, m in enumerate(team):
            m.team_slot = idx + 1
        await db.commit()
        
        await callback.answer(f"Removed {monster.name} from team!")

    # Reload menu
    callback.data = "bag_team_menu"
    await callback_team_menu(callback, db)

@router.callback_query(F.data == "bag_items_menu")
async def callback_items_menu(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id
    
    # Query inventory items with qty > 0
    stmt = select(Inventory).where(
        Inventory.user_id == user_id,
        Inventory.quantity > 0
    )
    res = await db.execute(stmt)
    items = res.scalars().all()

    # Load item details
    items_file = os.path.join(config.DATA_DIR, "items.json")
    with open(items_file, "r") as f:
        items_db = json.load(f)

    text = "⚡ **Trainer Items Bag** ⚡\nSelect an item to use on one of your monsters:\n\n"
    builder = InlineKeyboardBuilder()

    if items:
        for item in items:
            details = items_db.get(item.item_id, {})
            name = details.get("name", item.item_id)
            text += f"• **{name}** x{item.quantity} - _{details.get('description', '')}_\n"
            
            # Exclude balls from standard bag "Use" menu since they are used during hunts
            if details.get("category") != "ball":
                builder.row(InlineKeyboardButton(text=f"Use {name}", callback_data=f"item_use_{item.item_id}"))
    else:
        text += "_No items in bag! Purchase items in the Shop._"

    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="menu_bag"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("item_use_"))
async def callback_item_select_target(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id
    item_id = callback.data.replace("item_use_", "")

    # Query all user's monsters
    stmt = select(UserMonster).where(UserMonster.user_id == user_id)
    res = await db.execute(stmt)
    monsters = res.scalars().all()

    text = f"🧪 Choose which monster to apply this item to:\n\n"
    builder = InlineKeyboardBuilder()

    if monsters:
        for mon in monsters:
            shiny_tag = "✨" if mon.is_shiny else ""
            builder.row(InlineKeyboardButton(
                text=f"{shiny_tag}{mon.name} (Lvl {mon.level}) - HP: {mon.current_hp}",
                callback_data=f"apply_{item_id}_{mon.id}"
            ))
    else:
        text += "_You don't own any monsters yet! Use /hunt to catch some._"

    builder.row(InlineKeyboardButton(text="🔙 Back", callback_data="bag_items_menu"))
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    await callback.answer()

@router.callback_query(F.data.startswith("apply_"))
async def callback_item_apply(callback: CallbackQuery, db: AsyncSession):
    user_id = callback.from_user.id
    parts = callback.data.split("_")
    
    # Format: apply_<item_id>_<mon_db_id>
    # Note: item_id might contain underscores like potion_basic.
    # We should reconstruct item_id.
    mon_db_id = int(parts[-1])
    item_id = "_".join(parts[1:-1])

    # Fetch inventory item
    inv_stmt = select(Inventory).where(
        Inventory.user_id == user_id,
        Inventory.item_id == item_id
    )
    inv_res = await db.execute(inv_stmt)
    inv = inv_res.scalar_one_or_none()

    if not inv or inv.quantity <= 0:
        await callback.answer("❌ You don't have this item in your inventory!", show_alert=True)
        return

    # Fetch user monster
    mon_stmt = select(UserMonster).where(
        UserMonster.id == mon_db_id,
        UserMonster.user_id == user_id
    )
    mon_res = await db.execute(mon_stmt)
    monster = mon_res.scalar_one_or_none()

    if not monster:
        await callback.answer("❌ Monster not found.", show_alert=True)
        return

    # Load item details
    items_file = os.path.join(config.DATA_DIR, "items.json")
    with open(items_file, "r") as f:
        items_db = json.load(f)
    item_details = items_db.get(item_id, {})
    category = item_details.get("category")

    monster_spec = spawn_system.monsters_db.get(monster.monster_id)
    base_hp = monster_spec["base_stats"]["hp"]
    max_hp = ((2 * base_hp + monster.hp_iv) * monster.level) // 100 + monster.level + 10

    # 1. Handle Potion
    if category == "potion":
        if monster.current_hp >= max_hp:
            await callback.answer("💚 This monster is already at full health!", show_alert=True)
            return
        if monster.current_hp <= 0:
            await callback.answer("💀 Use a Revive first on fainted monsters!", show_alert=True)
            return

        heal_amount = item_details.get("value", 50)
        monster.current_hp = min(max_hp, monster.current_hp + heal_amount)
        inv.quantity -= 1
        await db.commit()
        await callback.answer(f"Healed {monster.name} by {heal_amount} HP!")

    # 2. Handle Revive
    elif category == "revive":
        if monster.current_hp > 0:
            await callback.answer("💚 This monster is not fainted!", show_alert=True)
            return
        
        percent = item_details.get("value", 0.5)
        monster.current_hp = int(max_hp * percent)
        inv.quantity -= 1
        await db.commit()
        await callback.answer(f"Revived {monster.name} with {monster.current_hp} HP!")

    # 3. Handle XP Candy / Boost
    elif category == "xp_boost":
        # Level up instantly
        monster.level += 1
        monster.xp = 0
        monster.current_hp = max_hp  # Heal to full on level up
        inv.quantity -= 1
        await db.commit()
        await callback.answer(f"{monster.name} leveled up to Lvl {monster.level}!")

    # 4. Handle Evolution Stone
    elif category == "stone":
        can_evo, reason = evolution_system.can_evolve(monster, has_stone=True)
        if not can_evo:
            await callback.answer(reason, show_alert=True)
            return

        success, msg = await evolution_system.evolve_monster(db, monster, stone_id=item_id)
        if success:
            await callback.answer("Evolved successfully!")
            await callback.message.edit_text(msg, reply_markup=get_bag_keyboard(), parse_mode="Markdown")
            return
        else:
            await callback.answer(msg, show_alert=True)
            return

    # Return to bag items menu
    callback.data = "bag_items_menu"
    await callback_items_menu(callback, db)
