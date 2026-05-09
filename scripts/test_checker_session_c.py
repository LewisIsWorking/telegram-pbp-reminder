"""Tests for checker.py — session (part c) group.

Extracted from test_checker.py during the test-split refactor (phase 2).
Module imports, helpers, and the _LOGS_DIR redirection setup live in
``_test_checker_helpers``.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_scene_shows_in_status():
    """Scene name appears in /status output."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["current_scenes"] = {"100": "The Haunted Chapel"}
    result = checker._build_status("100", "TestCampaign", state, {999})
    assert "The Haunted Chapel" in result

def test_scene_shows_in_campaign():
    """Scene name appears in /campaign output."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["current_scenes"] = {"100": "The Grand Library"}
    result = checker._build_campaign_report("100", config, state, {999})
    assert "The Grand Library" in result

def test_away_command():
    """/away marks player as away and skips warnings."""
    _reset()
    config = _make_config()
    state = _make_state()
    now = datetime.now(timezone.utc)
    state["players"] = {
        "100:42": {
            "user_id": "42", "first_name": "Alice", "last_name": "",
            "username": "alice", "campaign_name": "TestCampaign",
            "pbp_topic_id": "100", "last_post_time": now.isoformat(),
            "last_warned_week": 0,
        },
    }

    updates = [_make_msg(1, 100, "/away 3 days vacation", user_id=42, first_name="Alice")]
    checker.process_updates(updates, config, state)

    assert "100:42" in state.get("away", {}), "Away record should be created"
    record = state["away"]["100:42"]
    assert record["reason"] == "vacation"
    assert record["until"] is not None
    assert "✈️" in _sent_messages[-1]["text"]

def test_away_indefinite():
    """/away without duration is indefinite."""
    _reset()
    config = _make_config()
    state = _make_state()
    now = datetime.now(timezone.utc)
    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "",
        "username": "", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": now.isoformat(),
        "last_warned_week": 0,
    }

    updates = [_make_msg(1, 100, "/away busy with work", user_id=42, first_name="Alice")]
    checker.process_updates(updates, config, state)

    record = state["away"]["100:42"]
    assert record["until"] is None
    assert record["reason"] == "busy with work"

def test_back_command():
    """/back clears away status."""
    _reset()
    config = _make_config()
    state = _make_state()
    now = datetime.now(timezone.utc)
    state["away"] = {
        "100:42": {"until": None, "reason": "holiday", "set_at": now.isoformat()}
    }
    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "",
        "username": "", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": now.isoformat(),
        "last_warned_week": 0,
    }

    updates = [_make_msg(1, 100, "/back", user_id=42, first_name="Alice")]
    checker.process_updates(updates, config, state)

    assert "100:42" not in state.get("away", {}), "Away record should be cleared"
    assert "👋" in _sent_messages[-1]["text"]

def test_away_auto_clear_on_post():
    """Posting a non-command message auto-clears away status."""
    _reset()
    config = _make_config()
    state = _make_state()
    now = datetime.now(timezone.utc)
    state["away"] = {
        "100:42": {"until": None, "reason": "holiday", "set_at": now.isoformat()}
    }
    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "",
        "username": "", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": now.isoformat(),
        "last_warned_week": 0,
    }

    updates = [_make_msg(1, 100, "I check the chest for traps.", user_id=42, first_name="Alice")]
    checker.process_updates(updates, config, state)

    assert "100:42" not in state.get("away", {}), "Away should auto-clear on post"

def test_away_skips_warnings():
    """Away players should be skipped in inactivity warnings."""
    _reset()
    config = _make_config()
    state = _make_state()
    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=10)).isoformat()
    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "",
        "username": "", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": old,
        "last_warned_week": 0,
    }
    # Mark as away
    state["away"] = {
        "100:42": {"until": None, "reason": "holiday", "set_at": now.isoformat()}
    }

    _sent_messages.clear()
    checker.check_player_activity(config, state, now=now)

    # Should NOT have sent any warning
    warning_msgs = [m for m in _sent_messages if "Alice" in m["text"] and "not posted" in m["text"]]
    assert len(warning_msgs) == 0, f"Away player should not get warned, got: {_sent_messages}"

def test_away_skips_combat_ping():
    """Away players should be excluded from combat ping missing list."""
    _reset()
    config = _make_config()
    state = _make_state()
    now = datetime.now(timezone.utc)
    old = (now - timedelta(hours=5)).isoformat()

    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "",
        "username": "alice", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": old,
        "last_warned_week": 0,
    }
    state["combat"]["100"] = {
        "active": True, "round": 1, "current_phase": "players",
        "phase_started_at": old, "last_ping_at": None,
        "players_acted": [], "campaign_name": "TestCampaign",
    }
    # Mark as away
    state["away"] = {
        "100:42": {"until": None, "reason": "holiday", "set_at": now.isoformat()}
    }

    _sent_messages.clear()
    checker.check_combat_turns(config, state, now=now)

    # Should NOT ping Alice
    pings = [m for m in _sent_messages if "Alice" in m["text"]]
    assert len(pings) == 0, f"Away player should not be pinged, got: {_sent_messages}"
