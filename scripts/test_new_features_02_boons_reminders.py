"""test_new_features.py — bin 2.

  - boons.reminders+bot_topic+queue_reminder
"""
"""Tests for features added in v4.4-4.8."""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timezone, timedelta
from unittest.mock import patch


# --- Queue tests ---


def _run_all():
    tests = [(name, obj) for name, obj in globals().items()
             if name.startswith("test_") and callable(obj)]
    passed = failed = 0
    for name, func in sorted(tests):
        try:
            func()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  FAIL: {name}: {e}")
    print(f"\n{passed} passed, {failed} failed out of {passed + failed}")
    return failed

def test_boon_reminder_24h():
    """24h reminder fires, reminders_sent goes to 1."""
    from boons.reminders import check_boon_reminders
    now = datetime.now(timezone.utc)
    config = {"group_id": -100, "bot_topic_id": 300}
    state = {
        "pending_potw_boons": {"100": {
            "message_id": 555,
            "winner_user_id": "42",
            "boons": ["Boon A"],
            "base_message": "Winner!",
            "campaign_name": "TestCamp",
            "posted_at": (now - timedelta(hours=25)).isoformat(),
        }},
        "players": {"100:42": {
            "user_id": "42", "first_name": "Alice", "username": "alice",
            "campaign_name": "TestCamp", "pbp_topic_id": "100",
            "last_post_time": now.isoformat(), "last_warned_week": 0,
        }},
    }
    # Mock telegram
    import telegram as tg
    sent = []
    orig = tg.send_message
    tg.send_message = lambda *a, **k: sent.append(a) or True
    try:
        check_boon_reminders(config, state, now=now)
    finally:
        tg.send_message = orig
    assert state["pending_potw_boons"]["100"]["reminders_sent"] == 1
    assert len(sent) == 1
    assert "unclaimed" in sent[0][2].lower()

def test_boon_reminder_7d_autoselect():
    """7d auto-pick fires and removes from pending."""
    from boons.reminders import check_boon_reminders
    now = datetime.now(timezone.utc)
    config = {"group_id": -100, "bot_topic_id": 300}
    state = {
        "pending_potw_boons": {"100": {
            "message_id": 555,
            "winner_user_id": "42",
            "boons": ["Boon A", "Boon B"],
            "base_message": "Winner!",
            "campaign_name": "TestCamp",
            "posted_at": (now - timedelta(hours=170)).isoformat(),
            "reminders_sent": 3,
        }},
        "players": {},
        "player_boons": {},
    }
    import telegram as tg
    sent = []
    orig_send = tg.send_message
    orig_edit = tg.edit_message
    tg.send_message = lambda *a, **k: sent.append(("send", a)) or True
    tg.edit_message = lambda *a, **k: sent.append(("edit", a)) or True
    try:
        check_boon_reminders(config, state, now=now)
    finally:
        tg.send_message = orig_send
        tg.edit_message = orig_edit
    assert "100" not in state["pending_potw_boons"]

def test_resolve_campaign_exact():
    from dispatch.bot_topic import resolve_campaign

    class FakeMaps:
        name_to_pid = {"kibwe": "100", "doomsday funtime": "200", "doomsday": "200"}
        to_name = {"100": "Kibwe", "200": "Doomsday Funtime"}

    pid, name = resolve_campaign("kibwe", FakeMaps())
    assert pid == "100"
    assert name == "Kibwe"

def test_resolve_campaign_prefix():
    from dispatch.bot_topic import resolve_campaign

    class FakeMaps:
        name_to_pid = {"kibwe": "100", "doomsday funtime": "200", "doomsday": "200"}
        to_name = {"100": "Kibwe", "200": "Doomsday Funtime"}

    pid, name = resolve_campaign("doom", FakeMaps())
    assert pid == "200"

def test_resolve_campaign_not_found():
    from dispatch.bot_topic import resolve_campaign

    class FakeMaps:
        name_to_pid = {"kibwe": "100"}
        to_name = {"100": "Kibwe"}

    pid, name = resolve_campaign("nonexistent", FakeMaps())
    assert pid is None

def test_queue_reminder_skips_when_empty():
    from scheduled.queue_reminder import post_queue_reminder
    config = {"group_id": -100, "bot_topic_id": 300}
    state = {"gm_queue": {}}
    import telegram as tg
    sent = []
    orig = tg.send_message
    tg.send_message = lambda *a, **k: sent.append(a) or True
    with patch("scheduled.queue_reminder.post_topic_queues"):
        try:
            post_queue_reminder(config, state)
        finally:
            tg.send_message = orig
    assert len(sent) == 0
    assert "last_queue_fingerprint" in state
