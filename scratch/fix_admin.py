import sys
sys.stdout.reconfigure(encoding='utf-8')

with open("handlers/admin.py", encoding="utf-8") as f:
    content = f.read()

# Find the start of the _spam_state section
spam_marker = "_spam_state: dict = {}"
spam_start = content.find(spam_marker)
if spam_start == -1:
    print("ERROR: _spam_state not found")
    exit(1)

# Go back to find the comment line before it
comment_marker = "# /spam"
comment_start = content.rfind(comment_marker, 0, spam_start)
print(f"Comment start: {comment_start}")
print(f"Spam dict start: {spam_start}")

# Cut the file just before the comment line
cut_point = content.rfind("\n", 0, comment_start) + 1
print(f"Cut point (line start): {cut_point}")
print(f"Content just before cut: {repr(content[cut_point-50:cut_point+100])}")

# The clean content up to where spam section begins
clean_content = content[:cut_point]

# Write the new clean spam section
new_spam_section = '''
# ─────────────────────────────────────────────────────────────────────────────
# /spam — Spam a message to a chosen group (Owner only)
# ─────────────────────────────────────────────────────────────────────────────

_spam_state: dict = {}


@router.message(Command("spam"))
async def cmd_spam_start(message: Message, db: AsyncSession):
    if not message.from_user or message.from_user.id not in config.ADMIN_IDS:
        await message.answer("Denied. Only Bot Owners can use this command.")
        return

    stmt = select(GroupSetting.chat_id)
    res = await db.execute(stmt)
    chat_ids = res.scalars().all()

    if not chat_ids:
        await message.answer("The bot is not in any groups.")
        return

    builder = InlineKeyboardBuilder()
    fetched = []
    for chat_id in chat_ids:
        try:
            chat = await message.bot.get_chat(chat_id)
            name = (chat.title or "Unnamed")[:30]
            fetched.append((chat_id, name))
        except Exception:
            pass

    for chat_id, name in fetched:
        builder.button(text=f"[GRP] {name}", callback_data=f"spam_grp_{chat_id}")
    builder.adjust(1)
    builder.row(InlineKeyboardButton(text="Cancel", callback_data="spam_cancel"))

    _spam_state[message.from_user.id] = {"step": "choose_group"}
    await message.answer(
        "<b>Spam Wizard</b>\\n"
        "Step 1: Choose the group to spam:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )


@router.callback_query(F.data.startswith("spam_grp_"))
async def cb_spam_group_chosen(callback: CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in config.ADMIN_IDS:
        await callback.answer("Not authorized.", show_alert=True)
        return

    chat_id = int(callback.data.replace("spam_grp_", ""))
    _spam_state[user_id] = {"step": "enter_msg", "chat_id": chat_id}

    try:
        chat = await callback.bot.get_chat(chat_id)
        group_name = html.escape(chat.title or "the group")
    except Exception:
        group_name = f"<code>{chat_id}</code>"

    await callback.message.edit_text(
        f"<b>Spam Wizard</b>\\n"
        f"Group: <b>{group_name}</b>\\n\\n"
        f"Step 2: Send me the message to spam:",
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "spam_cancel")
async def cb_spam_cancel(callback: CallbackQuery):
    user_id = callback.from_user.id
    _spam_state.pop(user_id, None)
    await callback.message.edit_text("Spam wizard cancelled.")
    await callback.answer()


@router.message(F.chat.type == "private", F.text & ~F.text.startswith("/"))
async def handle_spam_wizard_text(message: Message):
    user_id = message.from_user.id if message.from_user else None
    if not user_id or user_id not in config.ADMIN_IDS:
        return
    state = _spam_state.get(user_id)
    if not state:
        return

    step = state.get("step")

    if step == "enter_msg":
        _spam_state[user_id]["msg_text"] = message.text
        _spam_state[user_id]["step"] = "enter_count"
        await message.answer(
            "<b>Spam Wizard</b>\\n"
            "Message saved!\\n\\n"
            "Step 3: How many times to send it? (1 to 50):",
            parse_mode="HTML"
        )

    elif step == "enter_count":
        count_str = message.text.strip()
        if not count_str.isdigit() or not (1 <= int(count_str) <= 50):
            await message.answer("Please enter a valid number between 1 and 50.")
            return

        count = int(count_str)
        chat_id = state["chat_id"]
        msg_text = state.get("msg_text", "")
        _spam_state.pop(user_id, None)

        try:
            group = await message.bot.get_chat(chat_id)
            group_name = html.escape(group.title or "the group")
        except Exception:
            group_name = f"<code>{chat_id}</code>"

        status_msg = await message.answer(
            f"Sending <b>{count}</b> messages to <b>{group_name}</b>...",
            parse_mode="HTML"
        )

        sent = 0
        failed = 0
        for i in range(count):
            try:
                await message.bot.send_message(chat_id=chat_id, text=msg_text)
                sent += 1
                await asyncio.sleep(0.5)
            except Exception as e:
                failed += 1
                print(f"Spam send failed [{i+1}/{count}]: {e}")

        await status_msg.edit_text(
            f"<b>Spam Complete!</b>\\n"
            f"<blockquote>Group: <b>{group_name}</b>\\n"
            f"Sent: <b>{sent}</b>\\n"
            f"Failed: <b>{failed}</b></blockquote>",
            parse_mode="HTML"
        )
'''

final_content = clean_content + new_spam_section

with open("handlers/admin.py", "w", encoding="utf-8") as f:
    f.write(final_content)

total = final_content.count('\n')
print(f"Done! Total lines now: {total}")
