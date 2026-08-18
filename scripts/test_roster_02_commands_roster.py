"""test_roster.py — bin 2.

  - commands/roster.py
"""
"""Tests for commands/roster.py and players/history.py."""

import json
import sys
import os
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))


# ── helpers ───────────────────────────────────────────────────────────────────


def _config(codes=None):
    codes = codes or [("C04", "Magni Watch"), ("C09", "Metal City")]
    return {"group_id": -1, "topic_pairs": [
        {"code": c, "name": n, "pbp_topic_ids": [i * 100]}
        for i, (c, n) in enumerate(codes, 1)
    ]}

def _player(pid, uid, name, username="", days_ago=1):
    last = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()
    return {
        "user_id": uid, "first_name": name, "username": username,
        "pbp_topic_id": pid, "last_post_time": last, "last_warned_week": 0,
        "campaign_name": "Test",
    }

def _hist_config():
    return {
        "group_id": -1001,
        "topic_pairs": [
            {"code": "C04", "name": "Magni Watch",
             "pbp_topic_ids": [100], "chat_topic_id": 999},
        ],
    }

# ── commands/roster.py ────────────────────────────────────────────────────────

def test_roster_overview_orders_by_count():
    from commands.roster import build_roster_overview
    config = _config()
    state = {
        "players": {
            "100:U1": _player(100, "U1", "Alice"),
            "100:U2": _player(100, "U2", "Bob"),
            "200:U3": _player(200, "U3", "Carol"),
        }
    }
    result = build_roster_overview(config, state)
    assert result.index("Metal City") < result.index("Magni Watch")


def test_roster_overview_shows_deficit():
    from commands.roster import build_roster_overview
    config = _config([("C04", "Magni Watch")])
    state = {"players": {"100:U1": _player(100, "U1", "Alice")}}
    result = build_roster_overview(config, state)
    assert "1/6" in result
    assert "⚠️" in result


def test_roster_overview_satisfied_at_target():
    """✅ means "meets the target the ladder is currently asking for".

    Updated 2026-08-18 for the recruiting ladder. Six players used to be
    the target outright; now, once every campaign has cleared 6, the bar
    moves to 8 (Lewis: *"in the scenario where there are 6 players in ALL
    campaigns, can we try to get campaigns to 8"*). So a campaign showing
    six is under target by design, and the top rung is where ✅ lives.
    """
    from commands.roster import build_roster_overview
    config = _config([("C04", "Test")])
    state = {"players": {
        f"100:U{i}": _player(100, f"U{i}", f"P{i}") for i in range(8)
    }}
    result = build_roster_overview(config, state)
    assert "✅" in result
    assert "8/8" in result


def test_roster_overview_six_is_under_target_once_the_ladder_steps():
    """The counterpart, and the behaviour Lewis actually asked for: a
    campaign that reaches 6 does not stay satisfied, it gets a new bar."""
    from commands.roster import build_roster_overview
    config = _config([("C04", "Test")])
    state = {"players": {
        f"100:U{i}": _player(100, f"U{i}", f"P{i}") for i in range(6)
    }}
    result = build_roster_overview(config, state)
    assert "6/8" in result
    assert "⚠️" in result


def test_roster_overview_excludes_inactive():
    from commands.roster import build_roster_overview
    config = _config([("C04", "Test")])
    state = {"players": {
        "100:U1": _player(100, "U1", "Active", days_ago=5),
        "100:U2": _player(100, "U2", "Inactive", days_ago=45),
    }}
    result = build_roster_overview(config, state)
    assert "1/6" in result


def test_roster_campaign_drill_down():
    from commands.roster import build_roster_campaign
    config = _config()
    pair = config["topic_pairs"][0]
    state = {
        "players": {"100:U1": _player(100, "U1", "Alice", "alice")},
        "player_history": [
            {"event": "join", "pid": "100", "user_id": "U1",
             "name": "Alice", "username": "alice",
             "at": "2026-01-15T10:00:00+00:00"},
        ],
    }
    result = build_roster_campaign(pair, config, state)
    assert "Alice" in result
    assert "@alice" in result
    assert "joined" in result
    assert "2026-01-15" in result


def test_roster_campaign_no_history():
    from commands.roster import build_roster_campaign
    config = _config()
    pair = config["topic_pairs"][0]
    state = {"players": {}, "player_history": []}
    result = build_roster_campaign(pair, config, state)
    assert "no history recorded yet" in result


def test_roster_find_pair_with_c_prefix():
    from commands.roster import build_roster
    config = _config([("C04", "Magni Watch")])
    state = {"players": {}, "player_history": []}
    result = build_roster("C04", config, state)
    assert "Magni Watch" in result


def test_roster_find_pair_without_c_prefix():
    from commands.roster import build_roster
    config = _config([("C04", "Magni Watch")])
    state = {"players": {}, "player_history": []}
    result = build_roster("04", config, state)
    assert "Magni Watch" in result


def test_roster_find_pair_unknown():
    from commands.roster import build_roster
    config = _config([("C04", "Magni Watch")])
    state = {"players": {}, "player_history": []}
    result = build_roster("C99", config, state)
    assert "not found" in result


def test_roster_no_arg_returns_overview():
    from commands.roster import build_roster
    config = _config()
    state = {"players": {}, "player_history": []}
    result = build_roster("", config, state)
    assert "Campaign Roster" in result


