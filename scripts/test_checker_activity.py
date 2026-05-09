"""Tests for checker.py — activity group.

Extracted from test_checker.py during the test-split refactor (phase 2.3).
Module imports, helpers, and the _LOGS_DIR redirection setup live in
``_test_checker_helpers``.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_streak_milestone_fires_at_7():
    _reset()
    now = datetime.now(timezone.utc)
    config = _make_config()
    state = _make_state()

    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "",
        "username": "", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": now.isoformat(),
        "last_warned_week": 0,
    }
    # 8 consecutive days of posts
    state["post_timestamps"]["100"] = {
        "42": [(now - timedelta(days=d, hours=3)).isoformat() for d in range(8)],
    }

    checker.check_streak_milestones(config, state, now=now)
    streak_msgs = [m for m in _sent_messages if "7-day" in m.get("text", "")]
    assert len(streak_msgs) == 1
    assert state["celebrated_streaks"]["100:42"] == 7

def test_streak_milestone_no_duplicate():
    _reset()
    now = datetime.now(timezone.utc)
    config = _make_config()
    state = _make_state()

    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "",
        "username": "", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": now.isoformat(),
        "last_warned_week": 0,
    }
    state["post_timestamps"]["100"] = {
        "42": [(now - timedelta(days=d, hours=3)).isoformat() for d in range(8)],
    }
    state["celebrated_streaks"] = {"100:42": 7}  # Already celebrated

    checker.check_streak_milestones(config, state, now=now)
    assert len(_sent_messages) == 0

def test_streak_milestone_escalates():
    _reset()
    now = datetime.now(timezone.utc)
    config = _make_config()
    state = _make_state()

    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "",
        "username": "", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": now.isoformat(),
        "last_warned_week": 0,
    }
    # 15 consecutive days
    state["post_timestamps"]["100"] = {
        "42": [(now - timedelta(days=d, hours=3)).isoformat() for d in range(15)],
    }
    state["celebrated_streaks"] = {"100:42": 7}

    checker.check_streak_milestones(config, state, now=now)
    streak_msgs = [m for m in _sent_messages if "14-day" in m.get("text", "")]
    assert len(streak_msgs) == 1
    assert state["celebrated_streaks"]["100:42"] == 14

def test_activity_tracking():
    """Messages record hour and day counters in state."""
    _reset()
    config = _make_config()
    state = _make_state()
    # Use a known time: Wednesday (weekday=2) at 14:30 UTC
    from datetime import datetime as dt
    wed_14 = int(dt(2026, 2, 25, 14, 30, tzinfo=timezone.utc).timestamp())

    updates = [{
        "update_id": 9200,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 42, "first_name": "Alice"},
            "date": wed_14,
            "text": "I search the room carefully.",
        },
    }]

    checker.process_updates(updates, config, state)
    hours = state.get("activity_hours", {}).get("100", {}).get("42", {})
    days = state.get("activity_days", {}).get("100", {}).get("42", {})
    assert hours.get("14", 0) == 1
    assert days.get("2", 0) == 1  # Wednesday = 2

def test_activity_command():
    """/activity shows pattern report when data exists."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["activity_hours"] = {"100": {
        "42": {"14": 10, "15": 5, "20": 3},
        "999": {"10": 8, "14": 4},
    }}
    state["activity_days"] = {"100": {
        "42": {"0": 5, "2": 8, "4": 5},
        "999": {"1": 4, "3": 8},
    }}

    result = checker._build_activity("100", "TestCampaign", state, {999})
    assert "Activity Patterns" in result
    assert "Busiest days" in result
    assert "Busiest times" in result
    assert "Peak hour" in result

def test_activity_empty():
    """/activity with no data shows helpful message."""
    _reset()
    result = checker._build_activity("100", "TestCampaign", {}, {999})
    assert "No activity data" in result

def test_activity_command_via_message():
    """/activity sent as a message produces a response."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["activity_hours"] = {"100": {"42": {"14": 5}}}
    state["activity_days"] = {"100": {"42": {"2": 5}}}
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 9201,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 42, "first_name": "Alice"},
            "date": now_ts,
            "text": "/activity",
        },
    }]

    checker.process_updates(updates, config, state)
    activity_msgs = [m for m in _sent_messages if "Activity" in m.get("text", "")]
    assert len(activity_msgs) >= 1
