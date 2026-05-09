"""Tests for checker.py — process (part a) group.

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


def test_process_updates_tracks_messages():
    _reset()
    config = _make_config()
    state = _make_state()
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 1001,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 42, "first_name": "TestPlayer", "last_name": "X", "username": "tp"},
            "date": now_ts,
            "text": "I attack the goblin",
        },
    }]

    new_offset = checker.process_updates(updates, config, state)
    assert new_offset == 1002
    assert "100" in state["topics"]
    assert state["topics"]["100"]["last_user"] == "TestPlayer"
    assert "100:42" in state["players"]
    assert state["players"]["100:42"]["first_name"] == "TestPlayer"
    assert state["message_counts"]["100"]["42"] == 1
    assert len(state["post_timestamps"]["100"]["42"]) == 1

def test_process_updates_ignores_other_groups():
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [{
        "update_id": 2001,
        "message": {
            "chat": {"id": -999},  # Wrong group
            "message_thread_id": 100,
            "from": {"id": 42, "first_name": "Test"},
            "text": "hello",
        },
    }]

    new_offset = checker.process_updates(updates, config, state)
    assert new_offset == 2002
    assert "100" not in state["topics"]

def test_process_updates_skips_gm_player_tracking():
    _reset()
    config = _make_config(gm_ids=[42])
    state = _make_state()
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 3001,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 42, "first_name": "GM"},
            "date": now_ts,
            "text": "The goblin attacks!",
        },
    }]

    checker.process_updates(updates, config, state)
    assert "100:42" not in state["players"]  # GM not tracked as player
    assert state["message_counts"]["100"]["42"] == 1  # But counts are tracked

def test_process_updates_help_command():
    _reset()
    config = _make_config()
    state = _make_state()
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 4001,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 42, "first_name": "Test"},
            "date": now_ts,
            "text": "/help",
        },
    }]

    checker.process_updates(updates, config, state)
    help_msgs = [m for m in _sent_messages if "PBP Reminder Bot" in m.get("text", "")]
    assert len(help_msgs) == 1

def test_process_updates_status_command():
    _reset()
    config = _make_config()
    state = _make_state()
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 5001,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 42, "first_name": "Test"},
            "date": now_ts,
            "text": "/status",
        },
    }]

    checker.process_updates(updates, config, state)
    status_msgs = [m for m in _sent_messages if "Status for" in m.get("text", "")]
    assert len(status_msgs) == 1

def test_process_updates_campaign_command():
    _reset()
    config = _make_config()
    state = _make_state()
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 6001,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 42, "first_name": "Test"},
            "date": now_ts,
            "text": "/campaign",
        },
    }]

    checker.process_updates(updates, config, state)
    campaign_msgs = [m for m in _sent_messages if "TestCampaign" in m.get("text", "")]
    assert len(campaign_msgs) >= 1
