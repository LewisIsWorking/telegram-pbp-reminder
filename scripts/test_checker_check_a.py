"""Tests for checker.py — check (part a) group.

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


def test_check_and_alert_fires_after_threshold():
    _reset()
    config = _make_config()
    state = _make_state()
    five_hours_ago = (datetime.now(timezone.utc) - timedelta(hours=5)).isoformat()

    state["topics"]["100"] = {
        "last_message_time": five_hours_ago,
        "last_user": "Alice",
        "last_user_id": "42",
        "campaign_name": "TestCampaign",
    }

    checker.check_and_alert(config, state)
    assert len(_sent_messages) == 1
    assert "No new posts" in _sent_messages[0]["text"]
    assert "TestCampaign" in _sent_messages[0]["text"]

def test_check_and_alert_skips_recent():
    _reset()
    config = _make_config()
    state = _make_state()
    one_hour_ago = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

    state["topics"]["100"] = {
        "last_message_time": one_hour_ago,
        "last_user": "Bob",
        "last_user_id": "42",
        "campaign_name": "TestCampaign",
    }

    checker.check_and_alert(config, state)
    assert len(_sent_messages) == 0

def test_check_and_alert_respects_feature_toggle():
    _reset()
    config = _make_config(pairs=[
        {"name": "Quiet", "chat_topic_id": 200, "pbp_topic_ids": [100], "disabled_features": ["alerts"]},
    ])
    state = _make_state()
    old = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()

    state["topics"]["100"] = {
        "last_message_time": old,
        "last_user": "Alice",
        "last_user_id": "42",
        "campaign_name": "Quiet",
    }

    checker.check_and_alert(config, state)
    assert len(_sent_messages) == 0  # Feature disabled, no alert

def test_check_player_activity_warns_at_1_week():
    _reset()
    config = _make_config()
    state = _make_state()
    now = datetime.now(timezone.utc)

    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "",
        "username": "alice", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": (now - timedelta(days=8)).isoformat(),
        "last_warned_week": 0,
    }

    checker.check_player_activity(config, state)
    warn_msgs = [m for m in _sent_messages if "hasn't posted" in m.get("text", "")]
    assert len(warn_msgs) == 1
    assert state["players"]["100:42"]["last_warned_week"] == 1

def test_check_player_activity_removes_at_4_weeks():
    _reset()
    config = _make_config()
    state = _make_state()
    now = datetime.now(timezone.utc)

    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Bob", "last_name": "",
        "username": "", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": (now - timedelta(days=30)).isoformat(),
        "last_warned_week": 3,
    }

    checker.check_player_activity(config, state)
    assert "100:42" not in state["players"]
    assert "100:42" in state["removed_players"]

def test_check_player_activity_permanent_not_removed():
    """Permanent players are never removed even at 4+ weeks."""
    _reset()
    config = _make_config()
    state = _make_state()
    now = datetime.now(timezone.utc)

    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Bob", "last_name": "",
        "username": "bobuser", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": (now - timedelta(days=30)).isoformat(),
        "last_warned_week": 3, "permanent": True,
    }

    checker.check_player_activity(config, state)
    assert "100:42" in state["players"], "Permanent player must not be removed"
    assert "100:42" not in state["removed_players"]

def test_check_player_activity_permanent_skips_week3_warning():
    """Permanent players skip the week-3 warning (mentions auto-removal)."""
    _reset()
    config = _make_config()
    state = _make_state()
    now = datetime.now(timezone.utc)

    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Bob", "last_name": "",
        "username": "bobuser", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": (now - timedelta(days=22)).isoformat(),
        "last_warned_week": 2, "permanent": True,
    }

    checker.check_player_activity(config, state)
    # last_warned_week should still be 2 (week-3 skipped)
    assert state["players"]["100:42"]["last_warned_week"] == 2

def test_check_player_activity_permanent_gets_week1_warning():
    """Permanent players still get week-1 inactivity pings."""
    _reset()
    config = _make_config()
    state = _make_state()
    now = datetime.now(timezone.utc)

    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Bob", "last_name": "",
        "username": "bobuser", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": (now - timedelta(days=8)).isoformat(),
        "last_warned_week": 0, "permanent": True,
    }

    checker.check_player_activity(config, state)
    assert state["players"]["100:42"]["last_warned_week"] == 1

def test_check_player_activity_respects_toggle():
    _reset()
    config = _make_config(pairs=[
        {"name": "NoWarn", "chat_topic_id": 200, "pbp_topic_ids": [100], "disabled_features": ["warnings"]},
    ])
    state = _make_state()
    now = datetime.now(timezone.utc)

    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "",
        "username": "", "campaign_name": "NoWarn",
        "pbp_topic_id": "100", "last_post_time": (now - timedelta(days=15)).isoformat(),
        "last_warned_week": 0,
    }

    checker.check_player_activity(config, state)
    assert len(_sent_messages) == 0  # No warning sent
