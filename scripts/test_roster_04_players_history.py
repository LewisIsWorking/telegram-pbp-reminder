"""test_roster.py — bin 4.

  - players/history.py — _post_roster (part a)
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

def test_roster_includes_permanent_players_regardless_of_activity():
    """Permanent players always appear in roster even if inactive >30 days."""
    from commands.roster import build_roster_overview
    config = _config([("C01", "Doomsday Funtime")])
    state = {"players": {
        "100:U1": {"user_id": "U1", "first_name": "Anthony",
                   "pbp_topic_id": 100, "permanent": True,
                   "last_post_time": "2020-01-01T00:00:00+00:00"},
    }}
    result = build_roster_overview(config, state)
    assert "1/6" in result  # permanent player counted despite ancient last post
