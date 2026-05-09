"""test_telegram.py — bin 1.

  - misc (part a)
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

def test_init():
    _tg.init("tok123")
    assert "tok123" in _tg.TELEGRAM_API

def test_post_success():
    _tg.init("t")
    with patch.object(_tg.requests, "post", return_value=_ok({"message_id": 1})):
        assert _tg._post("sendMessage", {}) == {"message_id": 1}

def test_post_ok_false():
    _tg.init("t")
    m = MagicMock(); m.status_code = 200; m.json.return_value = {"ok": False}
    with patch.object(_tg.requests, "post", return_value=m):
        assert _tg._post("sendMessage", {}) is None

def test_post_http_error():
    _tg.init("t")
    with patch.object(_tg.requests, "post", return_value=_fail(500, "err")):
        assert _tg._post("sendMessage", {}, "lbl") is None

def test_post_rate_limit_retry_success():
    _tg.init("t")
    with patch.object(_tg, "time") as mt:
        with patch.object(_tg.requests, "post", side_effect=[_rate(2), _ok("done")]):
            assert _tg._post("sendMessage", {}) == "done"
            mt.sleep.assert_called_once_with(3)

def test_post_rate_limit_both_fail():
    _tg.init("t")
    with patch.object(_tg, "time"):
        with patch.object(_tg.requests, "post", side_effect=[_rate(1), _rate(1)]):
            assert _tg._post("sendMessage", {}) is None

def test_post_network_exception():
    _tg.init("t")
    with patch.object(_tg.requests, "post", side_effect=_req.RequestException("x")):
        assert _tg._post("sendMessage", {}) is None

def test_get_updates_success():
    _tg.init("t")
    m = MagicMock(); m.status_code = 200
    m.json.return_value = {"ok": True, "result": [{"update_id": 1}]}
    with patch.object(_tg.requests, "get", return_value=m):
        assert _tg.get_updates(0) == [{"update_id": 1}]

def test_get_updates_http_error():
    _tg.init("t")
    m = MagicMock(); m.status_code = 500
    with patch.object(_tg.requests, "get", return_value=m):
        assert _tg.get_updates(0) == []

def test_get_updates_not_ok():
    _tg.init("t")
    m = MagicMock(); m.status_code = 200; m.json.return_value = {"ok": False}
    with patch.object(_tg.requests, "get", return_value=m):
        assert _tg.get_updates(0) == []

def test_get_updates_json_error():
    _tg.init("t")
    m = MagicMock(); m.status_code = 200
    m.json.side_effect = ValueError("bad"); m.text = "garbage"
    with patch.object(_tg.requests, "get", return_value=m):
        assert _tg.get_updates(0) == []

def test_get_updates_network_error():
    _tg.init("t")
    with patch.object(_tg.requests, "get", side_effect=_req.RequestException("x")):
        assert _tg.get_updates(0) == []

def test_send_message_success():
    _tg.init("t")
    with patch.object(_tg.requests, "post", return_value=_ok({"message_id": 5})):
        assert _tg.send_message(-1, 42, "hi") is True

def test_send_message_no_thread():
    _tg.init("t")
    with patch.object(_tg.requests, "post", return_value=_ok({"message_id": 5})) as mp:
        _tg.send_message(-1, None, "hi")
        assert "message_thread_id" not in mp.call_args[1]["json"]

def test_send_message_parse_mode():
    _tg.init("t")
    with patch.object(_tg.requests, "post", return_value=_ok({"message_id": 5})) as mp:
        _tg.send_message(-1, 42, "hi", parse_mode="HTML")
        assert mp.call_args[1]["json"]["parse_mode"] == "HTML"

def test_send_message_fail():
    _tg.init("t")
    with patch.object(_tg.requests, "post", return_value=_fail()):
        assert _tg.send_message(-1, 42, "hi") is False

def test_send_message_id_success():
    _tg.init("t")
    with patch.object(_tg.requests, "post", return_value=_ok({"message_id": 99})):
        assert _tg.send_message_id(-1, 42, "hi") == 99

def test_send_message_id_no_thread():
    _tg.init("t")
    with patch.object(_tg.requests, "post", return_value=_ok({"message_id": 99})) as mp:
        _tg.send_message_id(-1, None, "hi")
        assert "message_thread_id" not in mp.call_args[1]["json"]

def test_send_message_id_parse_mode():
    _tg.init("t")
    with patch.object(_tg.requests, "post", return_value=_ok({"message_id": 99})) as mp:
        _tg.send_message_id(-1, 42, "hi", parse_mode="HTML")
        assert mp.call_args[1]["json"]["parse_mode"] == "HTML"

def test_send_message_id_fail():
    _tg.init("t")
    with patch.object(_tg.requests, "post", return_value=_fail()):
        assert _tg.send_message_id(-1, 42, "hi") is None

def test_send_buttons_success():
    _tg.init("t")
    with patch.object(_tg.requests, "post", return_value=_ok({"message_id": 77})):
        assert _tg.send_message_with_buttons(-1, 42, "x", []) == 77

def test_send_buttons_fail():
    _tg.init("t")
    with patch.object(_tg.requests, "post", return_value=_fail()):
        assert _tg.send_message_with_buttons(-1, 42, "x", []) is None

def test_edit_message_success():
    _tg.init("t")
    with patch.object(_tg.requests, "post", return_value=_ok(True)):
        assert _tg.edit_message(-1, 5, "new") is True

def test_edit_message_parse_mode():
    _tg.init("t")
    with patch.object(_tg.requests, "post", return_value=_ok(True)) as mp:
        _tg.edit_message(-1, 5, "x", parse_mode="HTML")
        assert mp.call_args[1]["json"]["parse_mode"] == "HTML"
