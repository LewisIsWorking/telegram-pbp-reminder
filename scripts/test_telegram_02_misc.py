"""test_telegram.py — bin 2.

  - misc (part b)
"""
"""Full coverage tests for telegram.py — all network calls mocked.

conftest.py installs a mock 'telegram' in sys.modules before collection.
We load the real implementation directly by file path to bypass this.
"""
import os
import importlib.util
from unittest.mock import patch, MagicMock
import requests as _req

# Load the real telegram.py by path — bypasses sys.modules mock from conftest
_spec = importlib.util.spec_from_file_location(
    "_real_telegram",
    os.path.join(os.path.dirname(__file__), "telegram.py")
)
_tg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_tg)



def _ok(result=True):
    m = MagicMock(); m.status_code = 200
    m.json.return_value = {"ok": True, "result": result}
    return m

def _fail(status=400, text="Bad"):
    m = MagicMock(); m.status_code = status; m.text = text
    m.json.return_value = {"ok": False}
    return m

def _rate(retry=1):
    m = MagicMock(); m.status_code = 429
    m.json.return_value = {"parameters": {"retry_after": retry}}
    return m

def test_edit_message_remove_keyboard():
    _tg.init("t")
    with patch.object(_tg.requests, "post", return_value=_ok(True)) as mp:
        _tg.edit_message(-1, 5, "x", remove_keyboard=True)
        assert mp.call_args[1]["json"]["reply_markup"] == {"inline_keyboard": []}

def test_edit_message_fail():
    _tg.init("t")
    with patch.object(_tg.requests, "post", return_value=_fail()):
        assert _tg.edit_message(-1, 5, "x") is False

def test_answer_callback_success():
    _tg.init("t")
    with patch.object(_tg.requests, "post", return_value=_ok(True)):
        assert _tg.answer_callback("cb1", "ok") is True

def test_answer_callback_fail():
    _tg.init("t")
    with patch.object(_tg.requests, "post", return_value=_fail()):
        assert _tg.answer_callback("cb1") is False

def test_send_poll_success():
    _tg.init("t")
    with patch.object(_tg.requests, "post",
                      return_value=_ok({"message_id": 10, "poll": {"id": "p1"}})):
        assert _tg.send_poll(-1, 42, "Q?", ["A", "B"]) == (10, "p1")

def test_send_poll_no_thread():
    _tg.init("t")
    with patch.object(_tg.requests, "post",
                      return_value=_ok({"message_id": 10, "poll": {"id": "p1"}})) as mp:
        _tg.send_poll(-1, None, "Q?", ["A"])
        assert "message_thread_id" not in mp.call_args[1]["json"]

def test_send_poll_with_thread_multi():
    _tg.init("t")
    with patch.object(_tg.requests, "post",
                      return_value=_ok({"message_id": 10, "poll": {"id": "p1"}})) as mp:
        _tg.send_poll(-1, 42, "Q?", ["A"], allows_multiple_answers=True)
        p = mp.call_args[1]["json"]
        assert p["message_thread_id"] == 42
        assert p["allows_multiple_answers"] is True

def test_send_poll_fail():
    _tg.init("t")
    with patch.object(_tg.requests, "post", return_value=_fail()):
        assert _tg.send_poll(-1, 42, "Q?", ["A"]) is None

def test_pin_success():
    _tg.init("t")
    with patch.object(_tg.requests, "post", return_value=_ok(True)):
        assert _tg.pin_message(-1, 55) is True

def test_pin_fail():
    _tg.init("t")
    with patch.object(_tg.requests, "post", return_value=_fail()):
        assert _tg.pin_message(-1, 55) is False

def test_unpin_success():
    _tg.init("t")
    # unpin is registry-guarded (bot only unpins its own pins), so the ID
    # must be recorded as bot-sent before the HTTP path is reached.
    from posting import bot_sent_registry as reg
    reg.record_sent(55)
    with patch.object(_tg.requests, "post", return_value=_ok(True)):
        assert _tg.unpin_message(-1, 55) is True

def test_unpin_fail():
    _tg.init("t")
    from posting import bot_sent_registry as reg
    reg.record_sent(55)
    with patch.object(_tg.requests, "post", return_value=_fail()):
        assert _tg.unpin_message(-1, 55) is False

def test_unpin_refuses_non_bot_message():
    """A message ID the bot never sent is not unpinned — no HTTP call made.

    Regression for the bot clearing GMs' / players' manual pins.
    """
    _tg.init("t")
    with patch.object(_tg.requests, "post", return_value=_ok(True)) as m_post:
        assert _tg.unpin_message(-1, 987654321) is False
        m_post.assert_not_called()

def test_message_link_public():
    assert _tg.message_link(-1001661053273, 40585, 12345, group_username="Path_Wars") == \
        "https://t.me/Path_Wars/40585/12345"

def test_message_link_private_strips_100():
    link = _tg.message_link(-1001661053273, 40585, 12345)
    assert "t.me/c/1661053273" in link
    assert "12345" in link

def test_message_link_private_no_100_prefix():
    link = _tg.message_link(-1234567890, 100, 99)
    assert "t.me/c/" in link
    assert "99" in link
