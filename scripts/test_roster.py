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
    from commands.roster import build_roster_overview
    config = _config([("C04", "Test")])
    state = {"players": {
        f"100:U{i}": _player(100, f"U{i}", f"P{i}") for i in range(6)
    }}
    result = build_roster_overview(config, state)
    assert "✅" in result
    assert "6/6" in result


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


# ── players/history.py ────────────────────────────────────────────────────────

def test_history_on_join_appends_event():
    from players.history import on_join
    state = {}
    on_join("100", "U1", "Alice", "alice", state)
    assert len(state["player_history"]) == 1
    assert state["player_history"][0]["event"] == "join"
    assert state["player_history"][0]["name"] == "Alice"


def test_history_on_leave_appends_event():
    from players.history import on_leave
    state = {}
    on_leave("100", "U1", "Alice", "alice", state)
    assert state["player_history"][0]["event"] == "leave"


def test_history_on_rejoin_appends_join_and_prints():
    from players.history import on_rejoin
    state = {}
    on_rejoin("100", "U1", "Alice", "alice", state)
    assert state["player_history"][0]["event"] == "join"


def test_history_multiple_events_accumulate():
    from players.history import on_join, on_leave, on_rejoin
    state = {}
    on_join("100", "U1", "Alice", "alice", state)
    on_leave("100", "U1", "Alice", "alice", state)
    on_rejoin("100", "U1", "Alice", "alice", state)
    assert len(state["player_history"]) == 3
    events = [e["event"] for e in state["player_history"]]
    assert events == ["join", "leave", "join"]

# ── players/history.py — _post_roster ────────────────────────────────────────

def _hist_config():
    return {
        "group_id": -1001,
        "topic_pairs": [
            {"code": "C04", "name": "Magni Watch",
             "pbp_topic_ids": [100], "chat_topic_id": 999},
        ],
    }


def test_on_join_posts_roster_to_chat_topic():
    """on_join posts updated roster to campaign chat topic when config given."""
    from players.history import on_join
    sent = []
    state = {"players": {}, "player_history": []}
    with patch("players.history.tg.send_message",
               side_effect=lambda g, t, m: sent.append((g, t, m))):
        on_join("100", "U1", "Alice", "alice", state, _hist_config())
    assert sent, "Expected roster post to chat topic"
    gid, tid, msg = sent[0]
    assert tid == 999
    assert "Magni Watch" in msg


def test_on_leave_posts_roster_to_chat_topic():
    """on_leave posts updated roster to campaign chat topic when config given."""
    from players.history import on_leave
    sent = []
    state = {"players": {}, "player_history": []}
    with patch("players.history.tg.send_message",
               side_effect=lambda g, t, m: sent.append((g, t, m))):
        on_leave("100", "U1", "Alice", "alice", state, _hist_config())
    assert sent
    assert sent[0][1] == 999


def test_on_rejoin_posts_roster_to_chat_topic():
    """on_rejoin posts updated roster to campaign chat topic when config given."""
    from players.history import on_rejoin
    sent = []
    state = {"players": {}, "player_history": []}
    with patch("players.history.tg.send_message",
               side_effect=lambda g, t, m: sent.append((g, t, m))):
        on_rejoin("100", "U1", "Alice", "alice", state, _hist_config())
    assert sent
    assert sent[0][1] == 999


def test_no_roster_post_without_config():
    """on_join without config arg does not attempt to post roster."""
    from players.history import on_join
    sent = []
    state = {"players": {}, "player_history": []}
    with patch("players.history.tg.send_message",
               side_effect=lambda g, t, m: sent.append((g, t, m))):
        on_join("100", "U1", "Alice", "alice", state)
    assert not sent


def test_no_roster_post_when_no_chat_topic():
    """_post_roster silently skips campaigns with no chat_topic_id."""
    from players.history import on_join
    config = {"group_id": -1001, "topic_pairs": [
        {"code": "C04", "name": "Test", "pbp_topic_ids": [100]},
    ]}
    sent = []
    state = {"players": {}, "player_history": []}
    with patch("players.history.tg.send_message",
               side_effect=lambda g, t, m: sent.append((g, t, m))):
        on_join("100", "U1", "Alice", "alice", state, config)
    assert not sent

def test_post_roster_unknown_pid_no_crash():
    """_post_roster with a pid not in config exits silently."""
    from players.history import on_join
    state = {"players": {}, "player_history": []}
    config = {"group_id": -1, "topic_pairs": [
        {"code": "C04", "name": "Test", "pbp_topic_ids": [100], "chat_topic_id": 999}
    ]}
    sent = []
    with patch("players.history.tg.send_message",
               side_effect=lambda g, t, m: sent.append(m)):
        on_join("999", "U1", "Alice", "alice", state, config)
    assert not sent  # unknown pid — no pair found, no post


def test_roster_campaign_history_shows_leave():
    """Drill-down shows leave events with correct icon."""
    from commands.roster import build_roster_campaign
    config = _config()
    pair = config["topic_pairs"][0]
    state = {
        "players": {},
        "player_history": [
            {"event": "leave", "pid": "100", "user_id": "U1",
             "name": "Alice", "username": "alice",
             "at": "2026-04-20T09:00:00+00:00"},
        ],
    }
    result = build_roster_campaign(pair, config, state)
    assert "left" in result
    assert "➖" in result


def test_roster_active_player_missing_last_post():
    """Players with missing/invalid last_post_time are excluded from active count."""
    from commands.roster import build_roster_overview
    config = _config([("C04", "Test")])
    state = {"players": {
        "100:U1": {"user_id": "U1", "first_name": "Alice",
                   "pbp_topic_id": 100, "last_post_time": "invalid"},
        "100:U2": {"user_id": "U2", "first_name": "Bob",
                   "pbp_topic_id": 100},  # missing key
    }}
    result = build_roster_overview(config, state)
    assert "0/6" in result
