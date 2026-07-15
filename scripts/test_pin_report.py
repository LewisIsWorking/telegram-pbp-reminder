"""Tests for scheduled.pin_report — daily pin digest + non-bot alert."""

from datetime import datetime, timezone
from unittest.mock import MagicMock

from scheduled import pin_report as pr


def _cfg():
    return {"group_id": -100, "bot_topic_id": 999, "diagnostic_hour": 8}


def _at(hour):
    return datetime(2026, 7, 15, hour, tzinfo=timezone.utc)


# ---- daily digest ----------------------------------------------------

def test_digest_skips_wrong_hour(monkeypatch):
    tg = MagicMock()
    monkeypatch.setattr(pr, "tg", tg)
    pr.run_daily_pin_digest(_cfg(), {}, now=_at(7))
    tg.send_message.assert_not_called()


def test_digest_skips_when_already_posted_today(monkeypatch):
    tg = MagicMock()
    monkeypatch.setattr(pr, "tg", tg)
    pr.run_daily_pin_digest(_cfg(), {"last_pin_digest": "2026-07-15"}, now=_at(8))
    tg.send_message.assert_not_called()


def test_digest_no_bot_topic_noop(monkeypatch):
    tg = MagicMock()
    monkeypatch.setattr(pr, "tg", tg)
    pr.run_daily_pin_digest({"group_id": -100}, {}, now=_at(8))
    tg.send_message.assert_not_called()


def test_digest_posts_counts_and_marks_day(monkeypatch):
    tg = MagicMock()
    tg.send_message.return_value = True
    monkeypatch.setattr(pr, "tg", tg)
    monkeypatch.setattr(pr.pin_audit, "entries_since", lambda ts: [
        {"action": "pin", "bot_owned": True},
        {"action": "unpin", "bot_owned": True},
        {"action": "delete", "bot_owned": True},
    ])
    st = {}
    pr.run_daily_pin_digest(_cfg(), st, now=_at(8))
    tg.send_message.assert_called_once()
    body = tg.send_message.call_args[0][2]
    assert "Pinned: 1" in body and "Unpinned: 1" in body and "Deleted: 1" in body
    assert "No non-bot" in body
    assert st["last_pin_digest"] == "2026-07-15"


def test_digest_flags_non_bot_actions(monkeypatch):
    tg = MagicMock()
    tg.send_message.return_value = True
    monkeypatch.setattr(pr, "tg", tg)
    monkeypatch.setattr(pr.pin_audit, "entries_since", lambda ts: [
        {"action": "unpin", "bot_owned": False},
    ])
    pr.run_daily_pin_digest(_cfg(), {}, now=_at(8))
    body = tg.send_message.call_args[0][2]
    assert "NON-bot" in body


def test_digest_not_marked_when_post_fails(monkeypatch):
    tg = MagicMock()
    tg.send_message.return_value = False
    monkeypatch.setattr(pr, "tg", tg)
    monkeypatch.setattr(pr.pin_audit, "entries_since", lambda ts: [])
    st = {}
    pr.run_daily_pin_digest(_cfg(), st, now=_at(8))
    assert "last_pin_digest" not in st


# ---- real-time non-bot alert ----------------------------------------

def test_alert_no_fresh_entries_noop(monkeypatch):
    tg = MagicMock()
    monkeypatch.setattr(pr, "tg", tg)
    monkeypatch.setattr(pr.pin_audit, "entries_since", lambda ts: [])
    st = {}
    pr.alert_non_bot_pin_actions(_cfg(), st, now=_at(4))
    tg.send_message.assert_not_called()
    assert "last_pin_alert_ts" not in st


def test_alert_advances_marker_when_all_bot_owned(monkeypatch):
    tg = MagicMock()
    monkeypatch.setattr(pr, "tg", tg)
    monkeypatch.setattr(pr.pin_audit, "entries_since", lambda ts: [
        {"action": "pin", "bot_owned": True, "timestamp": "2026-07-15T04:00:00"},
    ])
    st = {}
    pr.alert_non_bot_pin_actions(_cfg(), st)
    tg.send_message.assert_not_called()
    assert st["last_pin_alert_ts"] == "2026-07-15T04:00:00"


def test_alert_fires_on_non_bot_action(monkeypatch):
    tg = MagicMock()
    tg.send_message.return_value = True
    monkeypatch.setattr(pr, "tg", tg)
    monkeypatch.setattr(pr.pin_audit, "entries_since", lambda ts: [
        {"action": "unpin", "bot_owned": False, "message_id": 123,
         "chat_id": -100, "refused": False,
         "timestamp": "2026-07-15T04:00:00", "site": "x.py:1"},
    ])
    st = {}
    pr.alert_non_bot_pin_actions(_cfg(), st)
    tg.send_message.assert_called_once()
    body = tg.send_message.call_args[0][2]
    assert "PIN GUARD ALERT" in body and "123" in body
    assert st["last_pin_alert_ts"] == "2026-07-15T04:00:00"


def test_alert_marker_unmoved_on_post_failure(monkeypatch):
    tg = MagicMock()
    tg.send_message.return_value = False
    monkeypatch.setattr(pr, "tg", tg)
    monkeypatch.setattr(pr.pin_audit, "entries_since", lambda ts: [
        {"action": "delete", "bot_owned": False, "message_id": 9,
         "chat_id": -100, "refused": False,
         "timestamp": "2026-07-15T05:00:00", "site": "y.py:2"},
    ])
    st = {"last_pin_alert_ts": "old"}
    pr.alert_non_bot_pin_actions(_cfg(), st)
    assert st["last_pin_alert_ts"] == "old"
