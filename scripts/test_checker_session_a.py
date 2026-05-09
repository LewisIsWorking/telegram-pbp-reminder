"""Tests for checker.py — session (part a) group.

Extracted from test_checker.py during the test-split refactor (phase 2).
Module imports, helpers, and the _LOGS_DIR redirection setup live in
``_test_checker_helpers``.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_pause_command():
    _reset()
    config = _make_config()
    state = _make_state()
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 9001,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 999, "first_name": "GM"},
            "date": now_ts,
            "text": "/pause Holiday break",
        },
    }]

    checker.process_updates(updates, config, state)
    assert "100" in state.get("paused_campaigns", {})
    assert state["paused_campaigns"]["100"]["reason"] == "Holiday break"
    pause_msgs = [m for m in _sent_messages if "paused" in m.get("text", "").lower()]
    assert len(pause_msgs) == 1

def test_pause_non_gm_ignored():
    _reset()
    config = _make_config()
    state = _make_state()
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 9002,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 42, "first_name": "Player"},
            "date": now_ts,
            "text": "/pause trying to pause",
        },
    }]

    checker.process_updates(updates, config, state)
    assert "100" not in state.get("paused_campaigns", {})

def test_resume_command():
    _reset()
    config = _make_config()
    state = _make_state()
    state["paused_campaigns"] = {"100": {"paused_at": "now", "reason": "test"}}
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 9003,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 999, "first_name": "GM"},
            "date": now_ts,
            "text": "/resume",
        },
    }]

    checker.process_updates(updates, config, state)
    assert "100" not in state.get("paused_campaigns", {})
    resume_msgs = [m for m in _sent_messages if "resumed" in m.get("text", "").lower()]
    assert len(resume_msgs) == 1

def test_pause_stops_alerts():
    _reset()
    now = datetime.now(timezone.utc)
    config = _make_config()
    state = _make_state()

    state["topics"]["100"] = {
        "last_message_time": (now - timedelta(hours=10)).isoformat(),
        "last_user": "Alice",
        "last_user_id": "42",
        "campaign_name": "TestCampaign",
    }
    state["paused_campaigns"] = {"100": {"paused_at": now.isoformat(), "reason": "break"}}

    checker.check_and_alert(config, state, now=now)
    alert_msgs = [m for m in _sent_messages if "No new posts" in m.get("text", "")]
    assert len(alert_msgs) == 0

def test_pause_stops_player_warnings():
    _reset()
    now = datetime.now(timezone.utc)
    config = _make_config()
    state = _make_state()

    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "",
        "username": "", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": (now - timedelta(days=10)).isoformat(),
        "last_warned_week": 0,
    }
    state["paused_campaigns"] = {"100": {"paused_at": now.isoformat(), "reason": "break"}}

    checker.check_player_activity(config, state, now=now)
    assert len(_sent_messages) == 0

def test_pause_shows_in_status():
    _reset()
    now = datetime.now(timezone.utc)
    state = _make_state()
    state["paused_campaigns"] = {"100": {"paused_at": now.isoformat(), "reason": "Holiday"}}

    result = checker._build_status("100", "TestCampaign", state, {"999"})
    assert "PAUSED" in result
    assert "Holiday" in result

def test_pause_shows_in_campaign():
    _reset()
    now = datetime.now(timezone.utc)
    config = _make_config()
    state = _make_state()
    state["paused_campaigns"] = {"100": {"paused_at": now.isoformat(), "reason": "Between arcs"}}

    result = checker._build_campaign_report("100", config, state, {"999"})
    assert "PAUSED" in result
    assert "Between arcs" in result

def test_catchup_no_history():
    _reset()
    state = _make_state()
    result = checker._build_catchup("100", "42", "TestCampaign", state, {"999"})
    assert "no posting history" in result.lower()

def test_catchup_caught_up():
    _reset()
    now = datetime.now(timezone.utc)
    state = _make_state()
    # Player posted just now
    state["post_timestamps"]["100"] = {
        "42": [now.isoformat()],
    }
    result = checker._build_catchup("100", "42", "TestCampaign", state, {"999"})
    assert "caught up" in result.lower()

def test_catchup_nobody_posted():
    _reset()
    now = datetime.now(timezone.utc)
    state = _make_state()
    # Player posted 5 hours ago, nobody else has posted since
    state["post_timestamps"]["100"] = {
        "42": [(now - timedelta(hours=5)).isoformat()],
    }
    result = checker._build_catchup("100", "42", "TestCampaign", state, {"999"})
    assert "nobody" in result.lower()
    assert "floor is yours" in result.lower()
