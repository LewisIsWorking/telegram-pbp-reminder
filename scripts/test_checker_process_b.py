"""Tests for checker.py — process (part b) group.

Extracted from test_checker.py during the test-split refactor. Module
imports, helper functions (_make_config, _make_state, _make_msg, _utc,
_reset, _run_all), and the _LOGS_DIR redirection setup all live in the
shared ``_test_checker_helpers`` module so this file contains test
functions only.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_process_boon_callback_valid():
    _reset()
    state = _make_state()
    state["pending_potw_boons"]["100"] = {
        "message_id": 555,
        "winner_user_id": "42",
        "boons": ["Boon A", "Boon B", "Boon C"],
        "base_message": "Winner!",
        "posted_at": datetime.now(timezone.utc).isoformat(),
    }
    cb = {
        "id": "cb1", "data": "boon:100:1",
        "from": {"id": 42},
        "message": {"chat": {"id": -100}, "message_id": 555},
    }
    checker.process_boon_callback(cb, _make_config(), state)
    assert "100" not in state["pending_potw_boons"]  # Cleaned up
    edit_msgs = [m for m in _sent_messages if "message_id" in m]
    assert len(edit_msgs) == 1

def test_process_boon_callback_wrong_user():
    _reset()
    state = _make_state()
    state["pending_potw_boons"]["100"] = {
        "message_id": 555,
        "winner_user_id": "42",
        "boons": ["Boon A"],
        "base_message": "Winner!",
        "posted_at": datetime.now(timezone.utc).isoformat(),
    }
    cb = {
        "id": "cb1", "data": "boon:100:0",
        "from": {"id": 99},  # Wrong user
        "message": {"chat": {"id": -100}, "message_id": 555},
    }
    checker.process_boon_callback(cb, _make_config(), state)
    assert "100" in state["pending_potw_boons"]  # Not cleaned up

def test_process_updates_mystats_command():
    _reset()
    config = _make_config()
    state = _make_state()
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 7001,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 42, "first_name": "Test"},
            "date": now_ts,
            "text": "/mystats",
        },
    }]

    checker.process_updates(updates, config, state)
    stats_msgs = [m for m in _sent_messages if "No posts tracked" in m.get("text", "") or "TestCampaign" in m.get("text", "")]
    assert len(stats_msgs) >= 1

def test_process_updates_me_alias():
    _reset()
    config = _make_config()
    state = _make_state()
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 7002,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 42, "first_name": "Test"},
            "date": now_ts,
            "text": "/me",
        },
    }]

    checker.process_updates(updates, config, state)
    stats_msgs = [m for m in _sent_messages if "No posts tracked" in m.get("text", "") or "TestCampaign" in m.get("text", "")]
    assert len(stats_msgs) >= 1

def test_process_updates_whosturn_command():
    _reset()
    config = _make_config()
    state = _make_state()
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 7003,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 42, "first_name": "Test"},
            "date": now_ts,
            "text": "/whosturn",
        },
    }]

    checker.process_updates(updates, config, state)
    turn_msgs = [m for m in _sent_messages if "No active combat" in m.get("text", "") or "Round" in m.get("text", "")]
    assert len(turn_msgs) >= 1

def test_process_updates_myhistory_command():
    _reset()
    config = _make_config()
    state = _make_state()
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 8001,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 42, "first_name": "Test"},
            "date": now_ts,
            "text": "/myhistory",
        },
    }]

    checker.process_updates(updates, config, state)
    history_msgs = [m for m in _sent_messages if "No posting history" in m.get("text", "") or "Posting history" in m.get("text", "")]
    assert len(history_msgs) >= 1
