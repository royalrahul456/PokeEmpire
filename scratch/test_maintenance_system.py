import asyncio
from unittest.mock import MagicMock
from aiogram.types import Message, CallbackQuery, Chat, User as TgUser
import config
from utils.maintenance import (
    is_maintenance_mode,
    is_maintenance_exempt,
    get_maintenance_info,
    get_maintenance_message,
    set_maintenance_mode,
    should_warn_maintenance
)
from utils.anti_spam import AntiSpamMiddleware

async def run_tests():
    print("=== Testing Maintenance System ===")

    # 1. Check exemptions
    print("\n1. Testing Exemptions:")
    owner_id = config.OWNER_IDS[0]
    co_owner_id = config.CO_OWNER_IDS[0]
    dev_id = config.DEV_IDS[0]
    regular_user = 999999999

    assert is_maintenance_exempt(owner_id) is True, "Owner should be exempt"
    assert is_maintenance_exempt(co_owner_id) is True, "Co-Owner should be exempt"
    assert is_maintenance_exempt(dev_id) is True, "Developer should be exempt"
    assert is_maintenance_exempt(regular_user) is False, "Regular user should NOT be exempt"
    assert is_maintenance_exempt(None) is False, "None should NOT be exempt"
    print("PASS: Exemption checks")

    # 2. Toggle maintenance ON
    print("\n2. Testing set_maintenance_mode ON:")
    await set_maintenance_mode(True, reason="Database migration in progress", enabled_by=owner_id)
    assert is_maintenance_mode() is True, "Maintenance mode should be True"
    info = get_maintenance_info()
    assert info["enabled"] is True
    assert info["reason"] == "Database migration in progress"
    assert info["enabled_by"] == owner_id

    card = get_maintenance_message()
    assert "BOT UNDER MAINTENANCE" in card
    assert "Database migration in progress" in card
    print("PASS: Maintenance ON & message generation")

    # 3. Test throttling
    print("\n3. Testing Cooldown / Throttling:")
    assert should_warn_maintenance(regular_user, -100123) is True
    # Immediate repeat should be throttled
    assert should_warn_maintenance(regular_user, -100123) is False
    # Different chat should allow
    assert should_warn_maintenance(regular_user, -100456) is True
    print("PASS: Throttling")

    # 4. Test Middleware interception
    print("\n4. Testing AntiSpamMiddleware behavior:")
    middleware = AntiSpamMiddleware()

    handler_called = []
    async def dummy_handler(event, data):
        handler_called.append(True)
        return "OK"

    def create_mock_message(text, user_id, chat_id, chat_type="supergroup"):
        msg = MagicMock(spec=Message)
        msg.text = text
        msg.caption = None
        user = MagicMock(spec=TgUser)
        user.id = user_id
        msg.from_user = user
        chat = MagicMock(spec=Chat)
        chat.id = chat_id
        chat.type = chat_type
        msg.chat = chat
        msg.answered = []
        async def mock_answer(t, parse_mode=None):
            msg.answered.append(t)
        msg.answer = mock_answer
        return msg

    def create_mock_callback(user_id):
        cb = MagicMock(spec=CallbackQuery)
        user = MagicMock(spec=TgUser)
        user.id = user_id
        cb.from_user = user
        cb.answered_alerts = []
        async def mock_answer(t=None, show_alert=False):
            cb.answered_alerts.append((t, show_alert))
        cb.answer = mock_answer
        return cb

    # A) Regular user typing command in group -> blocked with notice
    handler_called.clear()
    msg = create_mock_message("/pokedex", regular_user, -100777, "supergroup")
    data = {"event_from_user": msg.from_user}
    await middleware(dummy_handler, msg, data)
    assert len(handler_called) == 0, "Handler should NOT be called for regular user command"
    assert len(msg.answered) == 1, "Regular user should receive maintenance answer"
    assert "BOT UNDER MAINTENANCE" in msg.answered[0]
    print("PASS: Regular user command intercepted with notice")

    # B) Regular user chatting normally in group -> silently dropped, NO spam notice
    handler_called.clear()
    msg_chat = create_mock_message("Hello guys what's up", regular_user, -100777, "supergroup")
    data = {"event_from_user": msg_chat.from_user}
    await middleware(dummy_handler, msg_chat, data)
    assert len(handler_called) == 0, "Handler should NOT be called"
    assert len(msg_chat.answered) == 0, "Bot should NOT spam group on casual chat during maintenance"
    print("PASS: Casual chatter silently ignored without group spam")

    # C) Regular user clicking callback query -> alert shown
    handler_called.clear()
    cb = create_mock_callback(regular_user)
    data = {"event_from_user": cb.from_user}
    await middleware(dummy_handler, cb, data)
    assert len(handler_called) == 0, "Handler should NOT be called for callback"
    assert len(cb.answered_alerts) == 1
    assert "under maintenance" in cb.answered_alerts[0][0]
    print("PASS: Callback intercepted with alert popup")

    # D) Exempt Owner running command -> executes normally!
    handler_called.clear()
    msg_owner = create_mock_message("/panel", owner_id, -100777, "supergroup")
    data = {"event_from_user": msg_owner.from_user}
    await middleware(dummy_handler, msg_owner, data)
    assert len(handler_called) == 1, "Handler MUST be called for exempt Owner"
    print("PASS: Owner can use commands during maintenance")

    # E) Exempt Developer running command -> executes normally!
    handler_called.clear()
    msg_dev = create_mock_message("/ping", dev_id, -100777, "supergroup")
    data = {"event_from_user": msg_dev.from_user}
    await middleware(dummy_handler, msg_dev, data)
    assert len(handler_called) == 1, "Handler MUST be called for exempt Developer"
    print("PASS: Developer can use commands during maintenance")

    # F) Exempt Co-Owner running command -> executes normally!
    handler_called.clear()
    msg_co = create_mock_message("/profile", co_owner_id, -100777, "supergroup")
    data = {"event_from_user": msg_co.from_user}
    await middleware(dummy_handler, msg_co, data)
    assert len(handler_called) == 1, "Handler MUST be called for exempt Co-Owner"
    print("PASS: Co-Owner can use commands during maintenance")

    # 5. Disable maintenance OFF
    print("\n5. Testing set_maintenance_mode OFF:")
    await set_maintenance_mode(False)
    assert is_maintenance_mode() is False
    handler_called.clear()
    msg_resumed = create_mock_message("/balance", regular_user, -100888, "supergroup")
    data = {"event_from_user": msg_resumed.from_user}
    await middleware(dummy_handler, msg_resumed, data)
    assert len(handler_called) == 1, "Handler should be called for regular user once maintenance is OFF"
    print("PASS: Normal users resume full access once maintenance is OFF")

    print("\nALL 5 TESTS PASSED PERFECTLY!")

if __name__ == "__main__":
    asyncio.run(run_tests())
