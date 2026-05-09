"""Tests for checker.py — build (part a) group.

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


def test_build_status_basic():
    _reset()
    state = _make_state()
    now = datetime.now(timezone.utc)

    state["topics"]["100"] = {
        "last_message_time": (now - timedelta(hours=3)).isoformat(),
        "last_user": "Alice",
        "last_user_id": "42",
        "campaign_name": "TestCampaign",
    }
    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "",
        "username": "", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": (now - timedelta(hours=3)).isoformat(),
        "last_warned_week": 0,
    }
    state["post_timestamps"]["100"] = {
        "42": [(now - timedelta(hours=h)).isoformat() for h in [3, 24, 48]],
    }

    result = checker._build_status("100", "TestCampaign", state, {"999"})
    assert "Status for TestCampaign" in result
    assert "1/6" in result  # 1 player
    assert "3h ago" in result
    assert "player" in result

def test_build_status_at_risk():
    _reset()
    state = _make_state()
    now = datetime.now(timezone.utc)

    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Bob", "last_name": "",
        "username": "", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": (now - timedelta(days=10)).isoformat(),
        "last_warned_week": 0,
    }

    result = checker._build_status("100", "TestCampaign", state, {"999"})
    assert "At risk" in result
    assert "Bob" in result
    assert "10d" in result

def test_build_campaign_report_basic():
    _reset()
    now = datetime.now(timezone.utc)
    config = _make_config(pairs=[
        {"name": "TestCampaign", "chat_topic_id": 200, "pbp_topic_ids": [100], "created": "2025-01-15"},
    ])
    state = _make_state()

    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "B",
        "username": "alice", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": (now - timedelta(hours=5)).isoformat(),
        "last_warned_week": 0,
    }
    state["message_counts"]["100"] = {"42": 20, "999": 30}
    state["post_timestamps"]["100"] = {
        "42": [(now - timedelta(hours=h)).isoformat() for h in [5, 24, 48, 72, 120]],
        "999": [(now - timedelta(hours=h)).isoformat() for h in [1, 6, 12, 30, 60]],
    }

    result = checker._build_campaign_report("100", config, state, {"999"})
    assert "TestCampaign" in result
    assert "1/6" in result
    assert "Roster" in result
    assert "Alice B" in result
    assert "@alice" in result
    assert "GM" in result
    assert "Running since" in result

def test_build_campaign_report_at_risk():
    _reset()
    now = datetime.now(timezone.utc)
    config = _make_config()
    state = _make_state()

    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Bob", "last_name": "",
        "username": "", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": (now - timedelta(days=12)).isoformat(),
        "last_warned_week": 0,
    }
    state["message_counts"]["100"] = {"42": 5}
    state["post_timestamps"]["100"] = {
        "42": [(now - timedelta(days=d)).isoformat() for d in [12, 13, 14]],
    }

    result = checker._build_campaign_report("100", config, state, {"999"})
    assert "At Risk" in result
    assert "Bob" in result

def test_build_mystats_basic():
    _reset()
    now = datetime.now(timezone.utc)
    state = _make_state()

    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "B",
        "username": "alice", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": (now - timedelta(hours=2)).isoformat(),
        "last_warned_week": 0,
    }
    state["message_counts"]["100"] = {"42": 15}
    state["post_timestamps"]["100"] = {
        "42": [(now - timedelta(hours=h)).isoformat() for h in [2, 24, 48, 72, 96, 120]],
    }

    result = checker._build_mystats("100", "42", "TestCampaign", state, {"999"})
    assert "TestCampaign" in result
    assert "Player" in result
    assert "15 posts" in result
    assert "Avg gap" in result

def test_build_mystats_gm():
    _reset()
    now = datetime.now(timezone.utc)
    state = _make_state()
    state["message_counts"]["100"] = {"999": 30}
    state["post_timestamps"]["100"] = {
        "999": [(now - timedelta(hours=h)).isoformat() for h in [1, 12, 24]],
    }

    result = checker._build_mystats("100", "999", "TestCampaign", state, {"999"})
    assert "GM" in result
