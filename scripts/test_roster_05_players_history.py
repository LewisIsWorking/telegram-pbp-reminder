"""test_roster.py — bin 5.

  - players/history.py — _post_roster (part b)
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

def test_alerts_skips_permanent_players():
    """Auto-removal skips players with permanent=True."""
    from scheduled.alerts import check_player_activity
    from datetime import datetime, timezone, timedelta
    now = datetime(2026, 4, 20, 12, 0, tzinfo=timezone.utc)
    old_post = (now - timedelta(weeks=5)).isoformat()
    state = {
        "players": {"100:U1": {
            "user_id": "U1", "first_name": "Anthony", "username": "MrNegetZ",
            "pbp_topic_id": "100", "campaign_name": "DF",
            "last_post_time": old_post, "last_warned_week": 0,
            "permanent": True,
        }},
        "removed_players": {}, "last_alerts": {},
        "topics": {"100": {"last_message_time": old_post}},
        "paused_campaigns": {},
    }
    config = {"group_id": -1, "topic_pairs": [
        {"pbp_topic_ids": ["100"], "name": "DF", "code": "C01",
         "chat_topic_id": 999, "features": {}},
    ]}
    check_player_activity(config, state, now=now)
    assert "100:U1" in state["players"]  # NOT removed
    assert state["removed_players"] == {}
