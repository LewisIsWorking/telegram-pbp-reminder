"""Tests for posting.pin_audit — the pin/unpin forensic trail.

Covers the append/bound/read behaviour of the log, the automatic
call-site resolution, and that the safe_delete pin/unpin paths write
the expected audit entries.
"""

from unittest.mock import MagicMock

import pytest

from posting import bot_sent_registry as reg
from posting import refusal_log as rl
from posting import pin_audit as pa
from posting.safe_delete import perform_guarded_unpin, perform_pin
from state_store import StateStore


@pytest.fixture(autouse=True)
def isolated_store(tmp_path, monkeypatch):
    test_store = StateStore(state_dir=tmp_path)
    monkeypatch.setattr(pa, "_store", test_store)
    monkeypatch.setattr(reg, "_store", test_store)
    monkeypatch.setattr(rl, "_store", test_store)
    pa.reset_for_test()
    reg.reset_for_test()
    rl.reset_for_test()
    yield
    pa.reset_for_test()
    reg.reset_for_test()
    rl.reset_for_test()


def test_record_action_appends_entry_with_fields():
    pa.record_action("pin", 111, 222, ok=True, timestamp="2026-07-07T00:00:00+00:00")
    entries = pa.recent()
    assert len(entries) == 1
    e = entries[0]
    assert e["action"] == "pin"
    assert e["chat_id"] == 111
    assert e["message_id"] == 222
    assert e["ok"] is True
    assert e["refused"] is False
    assert e["timestamp"] == "2026-07-07T00:00:00+00:00"
    assert "site" in e


def test_record_action_bounds_to_max_entries(monkeypatch):
    monkeypatch.setattr(pa, "_MAX_ENTRIES", 5)
    for i in range(12):
        pa.record_action("pin", 1, i, ok=True, site="x")
    entries = pa.recent(limit=100)
    assert len(entries) == 5
    # Oldest dropped: only the last five message_ids survive.
    assert [e["message_id"] for e in entries] == [7, 8, 9, 10, 11]


def test_recent_returns_tail_newest_last():
    for i in range(6):
        pa.record_action("unpin", 1, i, ok=True, site="x")
    tail = pa.recent(limit=3)
    assert [e["message_id"] for e in tail] == [3, 4, 5]


def test_caller_site_skips_wrapper_frames():
    # Called directly from this test file → site names this file, not a wrapper.
    pa.record_action("pin", 1, 2, ok=True)
    site = pa.recent()[0]["site"]
    assert site.startswith("test_pin_audit.py:")


def test_perform_pin_records_pin_and_returns_ok():
    post_fn = MagicMock(return_value={"message_id": 999})
    result = perform_pin(555, 999, post_fn)
    assert result is True
    post_fn.assert_called_once()
    assert post_fn.call_args[0][0] == "pinChatMessage"
    entries = pa.recent()
    assert len(entries) == 1
    assert entries[0]["action"] == "pin"
    assert entries[0]["message_id"] == 999
    assert entries[0]["ok"] is True


def test_perform_pin_records_failure():
    post_fn = MagicMock(return_value=None)
    assert perform_pin(555, 999, post_fn) is False
    assert pa.recent()[0]["ok"] is False


def test_unpin_refused_records_refused_audit_entry():
    # Unknown id → guard refuses; audit records action=unpin, refused=True.
    post_fn = MagicMock()
    assert perform_guarded_unpin(555, 424242, post_fn) is False
    post_fn.assert_not_called()
    e = pa.recent()[-1]
    assert e["action"] == "unpin"
    assert e["message_id"] == 424242
    assert e["refused"] is True
    assert e["ok"] is False


def test_unpin_performed_records_audit_entry():
    reg.record_sent(7777)
    post_fn = MagicMock(return_value={})
    assert perform_guarded_unpin(555, 7777, post_fn) is True
    e = pa.recent()[-1]
    assert e["action"] == "unpin"
    assert e["message_id"] == 7777
    assert e["refused"] is False
    assert e["ok"] is True
