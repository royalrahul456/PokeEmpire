import random
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import config
from database.models import User, Pokemon, UserPokemon, RedeemCode, RedeemClaim
from utils.formatters import escape_md, get_progress_bar, get_rarity_emoji
from utils.favorite import get_favorite_id

router = Router()

@router.message(Command("createredeem"))
async def cmd_create_redeem(message: Message, db: AsyncSession):
    # Only bot owner can run this in DM
    if message.chat.type != "private":
        await message.answer("⚠️ This command can only be used in private DMs.")
        return
        
    if not config.ADMIN_IDS or message.from_user.id != config.ADMIN_IDS[0]:
        await message.answer("❌ Denied. Only the Bot Owner can create redeem codes.")
        return
        
    parts = message.text.split()
    if len(parts) < 4:
        await message.answer(
            "⚠️ <b>Format</b>:\n"
            "• <code>/createredeem &lt;code&gt; &lt;limit&gt; &lt;coins_amount&gt;</code>\n"
            "• <code>/createredeem &lt;code&gt; &lt;limit&gt; &lt;pokemon_name/id&gt; [shiny] [amv]</code>\n\n"
            "*(e.g., <code>/createredeem GIFT500 100 500</code> or <code>/createredeem AMVPK 10 charizard amv</code>)*",
            parse_mode="HTML"
        )
        return
        
    code = parts[1].upper()
    
    # Validate limit
    if not parts[2].isdigit():
        await message.answer("❌ Limit must be a positive number.")
        return
    limit = int(parts[2])
    if limit < 1:
        await message.answer("❌ Limit must be at least 1.")
        return
        
    # Check reward type
    reward_str = parts[3].lower()
    
    # Check if reward is coins
    if reward_str.isdigit() and len(parts) == 4:
        coins = int(reward_str)
        # Check if code already exists
        exist_stmt = select(RedeemCode).where(RedeemCode.code == code)
        exist_res = await db.execute(exist_stmt)
        if exist_res.scalar_one_or_none():
            await message.answer(f"❌ Redeem code <code>{code}</code> already exists!", parse_mode="HTML")
            return
            
        new_code = RedeemCode(
            code=code,
            reward_type="coins",
            reward_value=coins,
            usage_limit=limit
        )
        db.add(new_code)
        await db.commit()
        await message.answer(
            f"✅ <b>Redeem Code Created!</b>\n"
            f"• Code: <code>{code}</code>\n"
            f"• Reward: 💰 <code>{coins:,} coins</code>\n"
            f"• Limit: 👥 <code>{limit} redeems</code>",
            parse_mode="HTML"
        )
        return
        
    # Reward is a Pokémon name or id
    is_shiny = False
    is_amv = False
    extra_parts = [p.lower() for p in parts[4:]]
    if "shiny" in extra_parts or "s" in extra_parts:
        is_shiny = True
    if "amv" in extra_parts:
        is_amv = True
        
    if reward_str.isdigit():
        poke_stmt = select(Pokemon).where(Pokemon.id == int(reward_str))
    else:
        poke_stmt = select(Pokemon).where(Pokemon.name.ilike(reward_str))
        
    poke_res = await db.execute(poke_stmt)
    pokemon = poke_res.scalar_one_or_none()
    
    if not pokemon:
        await message.answer(f"❌ Pokémon '{reward_str}' not found in database.")
        return
        
    if is_amv and not pokemon.video_url:
        await message.answer(f"❌ Pokémon '{pokemon.name.title()}' does not have an AMV video edit set.\nUse <code>/setpokemedia {pokemon.id}</code> first in DM.", parse_mode="HTML")
        return
        
    # Check if code already exists
    exist_stmt = select(RedeemCode).where(RedeemCode.code == code)
    exist_res = await db.execute(exist_stmt)
    if exist_res.scalar_one_or_none():
        await message.answer(f"❌ Redeem code <code>{code}</code> already exists!", parse_mode="HTML")
        return
        
    new_code = RedeemCode(
        code=code,
        reward_type="pokemon",
        reward_value=pokemon.id,
        reward_is_shiny=is_shiny,
        reward_is_amv=is_amv,
        usage_limit=limit
    )
    db.add(new_code)
    await db.commit()
    
    shiny_tag = "✨ Shiny " if is_shiny else ""
    amv_tag = "🎬 AMV " if is_amv else ""
    r_emoji = get_rarity_emoji(pokemon.rarity)
    
    await message.answer(
        f"✅ <b>Redeem Code Created!</b>\n"
        f"• Code: <code>{code}</code>\n"
        f"• Reward: {r_emoji} {shiny_tag}{amv_tag}<b>{pokemon.name.title()}</b>\n"
        f"• Limit: 👥 <code>{limit} redeems</code>",
        parse_mode="HTML"
    )

@router.message(Command("redeem"))
async def cmd_redeem(message: Message, db: AsyncSession):
    user_id = message.from_user.id
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer("⚠️ Format: `/redeem <code>`")
        return
        
    code_str = parts[1].upper()
    
    # Fetch code
    stmt = select(RedeemCode).where(RedeemCode.code == code_str)
    res = await db.execute(stmt)
    code = res.scalar_one_or_none()
    
    if not code:
        await message.answer("❌ Invalid redeem code. Please check spelling and try again.")
        return
        
    # Check limit
    if code.usage_count >= code.usage_limit:
        await message.answer("❌ This redeem code has expired (limit reached).")
        return
        
    # Ensure user exists in database
    u_stmt = select(User).where(User.id == user_id)
    u_res = await db.execute(u_stmt)
    user = u_res.scalar_one_or_none()
    if not user:
        # Create user
        user = User(
            id=user_id,
            username=message.from_user.username,
            nickname=message.from_user.first_name
        )
        db.add(user)
        await db.flush()
        
    # Check if already claimed by this user
    claim_stmt = select(RedeemClaim).where(RedeemClaim.code_id == code.id, RedeemClaim.user_id == user_id)
    claim_res = await db.execute(claim_stmt)
    if claim_res.scalar_one_or_none():
        await message.answer("❌ You have already claimed this redeem code!")
        return
        
    # Process reward
    try:
        # Register claim
        claim = RedeemClaim(user_id=user_id, code_id=code.id)
        db.add(claim)
        
        # Increment code count
        code.usage_count += 1
        
        if code.reward_type == "coins":
            user.coins += code.reward_value
            await db.commit()
            
            await message.answer(
                f"🎉 <b>REDEEM SUCCESSFUL!</b> 🎉\n"
                f"───────────────\n"
                f"Trainer <b>{escape_md(user.nickname or 'Trainer')}</b> claimed code <code>{code.code}</code>!\n\n"
                f"💰 Reward: <code>💰 +{code.reward_value:,} coins</code>\n"
                f"Balance: <code>💰 {user.coins:,} coins</code>",
                parse_mode="HTML"
            )
        else:
            # Grant Pokémon
            poke_stmt = select(Pokemon).where(Pokemon.id == code.reward_value)
            poke_res = await db.execute(poke_stmt)
            pokemon = poke_res.scalar_one()
            
            # Roll stats/IVs
            iv_hp = random.randint(0, 31)
            iv_atk = random.randint(0, 31)
            iv_def = random.randint(0, 31)
            iv_spd = random.randint(0, 31)
            iv_total = iv_hp + iv_atk + iv_def + iv_spd
            iv_pct = int((iv_total / 124) * 100)
            
            serial_number = None
            if code.reward_is_amv:
                serial_number = f"#{pokemon.id:03d}-{random.randint(1000, 9999)}"
                
            new_poke = UserPokemon(
                user_id=user_id,
                pokemon_id=pokemon.id,
                is_shiny=code.reward_is_shiny,
                is_amv=code.reward_is_amv,
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
            
            hp_bar = get_progress_bar(iv_hp, 31, 5, fill_char="▰", empty_char="▱")
            atk_bar = get_progress_bar(iv_atk, 31, 5, fill_char="▰", empty_char="▱")
            def_bar = get_progress_bar(iv_def, 31, 5, fill_char="▰", empty_char="▱")
            spd_bar = get_progress_bar(iv_spd, 31, 5, fill_char="▰", empty_char="▱")
            
            shiny_badge = "✨ Shiny " if code.reward_is_shiny else ""
            amv_badge = "🎬 AMV " if code.reward_is_amv else ""
            serial_str = f"\n🎫 **Serial Number**: `{serial_number}`" if serial_number else ""
            r_emoji = get_rarity_emoji(pokemon.rarity)
            
            text = (
                f"🎉 <b>REDEEM SUCCESSFUL!</b> 🎉\n"
                f"───────────────\n"
                f"Trainer <b>{escape_md(user.nickname or 'Trainer')}</b> claimed code <code>{code.code}</code>!\n\n"
                f"🎁 Reward: {r_emoji} {shiny_badge}{amv_badge}<b>{pokemon.name.title()}</b> `(Lvl 1)`{serial_str}\n"
                f"🧬 **IV Quality**: `🧬 {iv_pct}%`\n"
                f"• HP IV: `[{hp_bar}]` `({iv_hp}/31)`\n"
                f"• ATK IV: `[{atk_bar}]` `({iv_atk}/31)`\n"
                f"• DEF IV: `[{def_bar}]` `({iv_def}/31)`\n"
                f"• SPD IV: `[{spd_bar}]` `({iv_spd}/31)`\n"
                f"───────────────"
            )
            await message.answer(text, parse_mode="HTML")
            
    except Exception as e:
        await db.rollback()
        print(f"[REDEEM CLAIM ERROR] user={user_id} code={code_str} error={e}")
        await message.answer("❌ An error occurred during redemption. Please try again.")
