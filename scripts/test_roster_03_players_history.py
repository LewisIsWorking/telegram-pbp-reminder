"""test_roster.py — bin 3.

  - players/history.py
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

