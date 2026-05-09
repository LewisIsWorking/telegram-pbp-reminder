"""Tests extracted from test_branch_gaps.py — bin 16.

Sections in this file:
  - scheduled/roster_nudge.py
"""
"""
Targeted tests for every remaining coverage gap.
Organised by file, hitting each uncovered branch.
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

def _gm_ctx(text, pid="100", uid="GM1"):
    return {
        "cmd_word": text.split()[0], "text": text,
        "user_id": uid, "gm_ids": {"GM1"},
        "pid": pid, "group_id": -1, "thread_id": 999,
        "state": {}, "config": {},
        "campaign_name": "Kibwe",
        "now_iso": "2026-04-03T12:00:00+00:00",
        "msg_time_iso": "2026-04-03T12:00:00+00:00",
        "user_name": "Lewis",
        "maps": MagicMock(), "parsed": {"raw_text": "/done 99", "text": "/done 99"},
    }

def _capture_config(placeholders=None):
    return {"group_id": -1, "bot_topic_id": 999, "topic_pairs": [
        {"code": "C01", "pbp_topic_ids": [100],
         "poll_user_ids": placeholders or [111, 222],
         "poll_user_names": {str(u): f"user{u}" for u in (placeholders or [111, 222])}}
    ]}

def _hp_config():
    return {
        "group_id": -1001, "bot_topic_id": 999,
        "leaderboard_topic_id": 888,
        "topic_pairs": [
            {"pbp_topic_ids": [100], "name": "Magni Watch"},
            {"pbp_topic_ids": [200], "name": "Kibwe"},
        ],
    }

def _hp_state(uid="U1"):
    return {
        "players": {
            f"100:{uid}": {"user_id": uid, "pbp_topic_id": 100, "first_name": "Chase"},
            f"200:{uid}": {"user_id": uid, "pbp_topic_id": 200, "first_name": "Chase"},
        }
    }

def _gm_config():
    return {"topic_pairs": [
        {"code": "C00", "name": "Riddleport",
         "pbp_topic_ids": [66154, 133428],
         "chat_topic_id": 91008},
    ]}

def _mention_config():
    return {"topic_pairs": [
        {"code": "C01", "pbp_topic_ids": [100],
         "poll_user_names": {"8787": "Sestina_The_Banner_Witch"}},
    ]}

# ─── scheduled/roster_nudge.py ────────────────────────────────────────────────

def test_roster_nudge_posts_when_interval_elapsed():
    """Posts when below target and 3+ days since last nudge."""
    from scheduled.roster_nudge import post_roster_nudge
    from datetime import datetime, timezone, timedelta
    now = datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)
    old = (now - timedelta(days=4)).isoformat()
    config = {"group_id": -1, "bot_topic_id": 999, "topic_pairs": [
        {"pbp_topic_ids": [100], "code": "C04", "name": "Magni Watch", "roster_target": 6},
    ]}
    state = {"last_roster_nudge": old, "last_roster_snapshot": "C04:1/6", "players": {
        "100:U1": {"user_id": "U1", "first_name": "Alice",
                   "pbp_topic_id": 100, "permanent": True,
                   "last_post_time": now.isoformat()},
    }}
    sent = []
    with patch("scheduled.roster_nudge.tg.send_message",
               side_effect=lambda g, t, m: sent.append(m)):
        post_roster_nudge(config, state, now=now)
    assert sent
    assert state["last_roster_nudge"] == now.isoformat()


def test_roster_nudge_posts_when_roster_changes():
    """Posts immediately when roster snapshot changes even within 3-day interval."""
    from scheduled.roster_nudge import post_roster_nudge
    from datetime import datetime, timezone, timedelta
    now = datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)
    recent = (now - timedelta(days=1)).isoformat()
    config = {"group_id": -1, "bot_topic_id": 999, "topic_pairs": [
        {"pbp_topic_ids": [100], "code": "C04", "name": "Test", "roster_target": 6},
    ]}
    state = {"last_roster_nudge": recent, "last_roster_snapshot": "C04:2/6", "players": {
        "100:U1": {"user_id": "U1", "first_name": "Alice", "pbp_topic_id": 100,
                   "permanent": True, "last_post_time": now.isoformat()},
    }}
    sent = []
    with patch("scheduled.roster_nudge.tg.send_message",
               side_effect=lambda g, t, m: sent.append(m)):
        post_roster_nudge(config, state, now=now)
    assert sent  # snapshot changed from 2 to 1


def test_roster_nudge_skips_when_all_satisfied():
    """Skips when all campaigns are at or above target."""
    from scheduled.roster_nudge import post_roster_nudge
    from datetime import datetime, timezone
    now = datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)
    config = {"group_id": -1, "bot_topic_id": 999, "topic_pairs": [
        {"pbp_topic_ids": [100], "code": "C04", "name": "Test", "roster_target": 1},
    ]}
    state = {"players": {
        "100:U1": {"user_id": "U1", "first_name": "Alice", "pbp_topic_id": 100,
                   "permanent": True, "last_post_time": now.isoformat()},
    }}
    sent = []
    with patch("scheduled.roster_nudge.tg.send_message",
               side_effect=lambda g, t, m: sent.append(m)):
        post_roster_nudge(config, state, now=now)
    assert not sent


def test_roster_nudge_skips_within_interval_no_change():
    """Skips if <3 days elapsed AND roster unchanged."""
    from scheduled.roster_nudge import post_roster_nudge
    from datetime import datetime, timezone, timedelta
    now = datetime(2026, 4, 21, 12, 0, tzinfo=timezone.utc)
    recent = (now - timedelta(days=1)).isoformat()
    config = {"group_id": -1, "bot_topic_id": 999, "topic_pairs": [
        {"pbp_topic_ids": [100], "code": "C04", "name": "Test", "roster_target": 6},
    ]}
    state = {"last_roster_nudge": recent, "last_roster_snapshot": "C04:0/6", "players": {}}
    sent = []
    with patch("scheduled.roster_nudge.tg.send_message",
               side_effect=lambda g, t, m: sent.append(m)):
        post_roster_nudge(config, state, now=now)
    assert not sent
