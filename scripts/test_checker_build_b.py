"""Tests for checker.py — build (part b) group.

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


def test_build_mystats_no_posts():
    _reset()
    state = _make_state()
    result = checker._build_mystats("100", "42", "TestCampaign", state, {"999"})
    assert "No posts tracked" in result

def test_build_whosturn_no_combat():
    _reset()
    state = _make_state()
    result = checker._build_whosturn("100", "TestCampaign", state)
    assert "No active combat" in result

def test_build_whosturn_players_phase():
    _reset()
    now = datetime.now(timezone.utc)
    state = _make_state()

    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "",
        "username": "", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": now.isoformat(),
        "last_warned_week": 0,
    }
    state["players"]["100:43"] = {
        "user_id": "43", "first_name": "Bob", "last_name": "",
        "username": "", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": now.isoformat(),
        "last_warned_week": 0,
    }
    state["combat"]["100"] = {
        "active": True, "round": 2, "current_phase": "players",
        "players_acted": ["42"], "last_ping_at": None,
        "campaign_name": "TestCampaign",
        "phase_started_at": (now - timedelta(hours=1)).isoformat(),
    }

    result = checker._build_whosturn("100", "TestCampaign", state)
    assert "Round 2" in result
    assert "Alice" in result
    assert "Bob" in result
    assert "Acted" in result
    assert "Waiting" in result

def test_build_whosturn_enemies_phase():
    _reset()
    now = datetime.now(timezone.utc)
    state = _make_state()

    state["combat"]["100"] = {
        "active": True, "round": 1, "current_phase": "enemies",
        "players_acted": [], "last_ping_at": None,
        "campaign_name": "TestCampaign",
        "phase_started_at": (now - timedelta(hours=1)).isoformat(),
    }

    result = checker._build_whosturn("100", "TestCampaign", state)
    assert "Enemies" in result
    assert "GM" in result

def test_build_weekly_digest_basic():
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
    state["message_counts"]["100"] = {"42": 15, "999": 10}
    state["post_timestamps"]["100"] = {
        "42": [(now - timedelta(hours=h)).isoformat() for h in range(1, 16)],
        "999": [(now - timedelta(hours=h)).isoformat() for h in range(1, 11)],
    }

    result = checker._build_weekly_digest(config, state, now)
    assert "Weekly Digest" in result
    assert "TestCampaign" in result
    assert "MVP" in result
    assert "Alice" in result

def test_build_weekly_digest_health_icons():
    assert checker._health_icon(25) == "🟢"
    assert checker._health_icon(15) == "🟡"
    assert checker._health_icon(7) == "🟠"
    assert checker._health_icon(2) == "🔴"
    assert checker._health_icon(0) == "🔴"

def test_build_myhistory_basic():
    _reset()
    now = datetime.now(timezone.utc)
    state = _make_state()

    state["message_counts"]["100"] = {"42": 30}
    state["post_timestamps"]["100"] = {
        "42": [
            (now - timedelta(weeks=w, hours=h)).isoformat()
            for w in range(4)
            for h in [2, 24, 48]
        ],
    }

    result = checker._build_myhistory("100", "42", "TestCampaign", state, {"999"})
    assert "Posting history" in result
    assert "Player" in result
    assert "8 weeks" in result
    assert "Peak week" in result

def test_build_myhistory_no_posts():
    _reset()
    state = _make_state()
    result = checker._build_myhistory("100", "42", "TestCampaign", state, {"999"})
    assert "No posting history" in result
