"""test_roster.py — bin 1.

  - helpers
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


