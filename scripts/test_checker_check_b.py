"""Tests for checker.py — check (part b) group.

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


def test_check_combat_turns_pings_missing():
    _reset()
    now = datetime.now(timezone.utc)
    config = _make_config()
    state = _make_state()

    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "",
        "username": "alice", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": now.isoformat(),
        "last_warned_week": 0,
    }
    state["combat"]["100"] = {
        "active": True, "round": 1, "current_phase": "players",
        "players_acted": [], "last_ping_at": None,
        "campaign_name": "TestCampaign",
        "phase_started_at": (now - timedelta(hours=5)).isoformat(),
    }

    checker.check_combat_turns(config, state, now=now)
    ping_msgs = [m for m in _sent_messages if "waiting on" in m.get("text", "")]
    assert len(ping_msgs) == 1
    assert "alice" in ping_msgs[0]["text"].lower() or "Alice" in ping_msgs[0]["text"]

def test_check_combat_turns_skips_enemies_phase():
    _reset()
    now = datetime.now(timezone.utc)
    config = _make_config()
    state = _make_state()

    state["combat"]["100"] = {
        "active": True, "round": 1, "current_phase": "enemies",
        "players_acted": [], "last_ping_at": None,
        "campaign_name": "TestCampaign",
        "phase_started_at": (now - timedelta(hours=5)).isoformat(),
    }

    checker.check_combat_turns(config, state, now=now)
    assert len(_sent_messages) == 0

def test_check_combat_turns_no_reping_too_soon():
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
    state["combat"]["100"] = {
        "active": True, "round": 1, "current_phase": "players",
        "players_acted": [], "campaign_name": "TestCampaign",
        "phase_started_at": (now - timedelta(hours=5)).isoformat(),
        "last_ping_at": (now - timedelta(hours=1)).isoformat(),
    }

    checker.check_combat_turns(config, state, now=now)
    assert len(_sent_messages) == 0  # Too soon to reping

def test_check_anniversaries_fires_on_date():
    _reset()
    now = datetime.now(timezone.utc)
    # Construct a "created" date exactly 2 years ago today
    two_years_ago = now.replace(year=now.year - 2)
    created_str = two_years_ago.strftime("%Y-%m-%d")

    config = _make_config(pairs=[
        {"name": "OldCampaign", "chat_topic_id": 200, "pbp_topic_ids": [100], "created": created_str},
    ])
    state = _make_state()

    checker.check_anniversaries(config, state, now=now)
    anniv_msgs = [m for m in _sent_messages if "2 years" in m.get("text", "")]
    assert len(anniv_msgs) == 1
    assert "100:2" in state["last_anniversary"]

def test_check_anniversaries_no_duplicate():
    _reset()
    now = datetime.now(timezone.utc)
    two_years_ago = now.replace(year=now.year - 2)
    created_str = two_years_ago.strftime("%Y-%m-%d")

    config = _make_config(pairs=[
        {"name": "OldCampaign", "chat_topic_id": 200, "pbp_topic_ids": [100], "created": created_str},
    ])
    state = _make_state()
    state["last_anniversary"]["100:2"] = now.isoformat()  # Already posted

    checker.check_anniversaries(config, state, now=now)
    assert len(_sent_messages) == 0

def test_check_anniversaries_wrong_day():
    _reset()
    now = datetime.now(timezone.utc)
    # Use a date that's NOT today — use day=1 to avoid month-length overflow
    wrong_date = now.replace(year=now.year - 1, month=(now.month % 12) + 1, day=1)
    created_str = wrong_date.strftime("%Y-%m-%d")

    config = _make_config(pairs=[
        {"name": "Campaign", "chat_topic_id": 200, "pbp_topic_ids": [100], "created": created_str},
    ])
    state = _make_state()

    checker.check_anniversaries(config, state, now=now)
    assert len(_sent_messages) == 0

def test_check_recruitment_fires_when_short():
    _reset()
    now = datetime.now(timezone.utc)
    config = _make_config()
    state = _make_state()

    # Only 1 player, needs 6
    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "",
        "username": "", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": now.isoformat(),
        "last_warned_week": 0,
    }

    checker.check_recruitment_needs(config, state, now=now)
    recruit_msgs = [m for m in _sent_messages if "needs" in m.get("text", "") and "more player" in m.get("text", "")]
    assert len(recruit_msgs) == 1
    assert "5 more players" in recruit_msgs[0]["text"]

def test_check_recruitment_skips_full_roster():
    _reset()
    now = datetime.now(timezone.utc)
    config = _make_config()
    state = _make_state()

    # Add 6 players (full roster)
    for i in range(6):
        state["players"][f"100:{i}"] = {
            "user_id": str(i), "first_name": f"Player{i}", "last_name": "",
            "username": "", "campaign_name": "TestCampaign",
            "pbp_topic_id": "100", "last_post_time": now.isoformat(),
            "last_warned_week": 0,
        }

    checker.check_recruitment_needs(config, state, now=now)
    recruit_msgs = [m for m in _sent_messages if "needs" in m.get("text", "") and "more player" in m.get("text", "")]
    assert len(recruit_msgs) == 0
