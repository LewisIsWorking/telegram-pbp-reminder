"""Tests extracted from test_branch_gaps.py — bin 13.

Sections in this file:
  - queue_reminder silent section integration (part b)
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

# ─── queue_reminder silent section integration ────────────────────────────────

def test_queue_reminder_empty_scanned_no_silent_returns_early():
    """Empty scanned with no silent campaigns updates fingerprint and returns."""
    from scheduled.queue_reminder import post_queue_reminder
    now = datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc)
    config = {
        "group_id": -1001, "bot_topic_id": 999, "gm_user_ids": [999],
        "queue_daily_hours": [now.hour],
        "topic_pairs": [
            {"pbp_topic_ids": [200], "code": "C08", "name": "Recent"},
        ],
    }
    # Recent activity — not silent
    recent_iso = (now - timedelta(days=2)).isoformat()
    state = {
        "last_queue_fingerprint": "OLD",
        "queue_post_count": 0, "last_queue_pin_id": None,
        "last_queue_daily_slots": [],
        "topics": {"200": {"last_message_time": recent_iso}},
    }
    sent_texts = []
    with patch("scheduled.queue_reminder.scan_transcripts", return_value={}), \
         patch("scheduled.queue_reminder.post_topic_queues"), \
         patch("scheduled.queue_reminder.tg.send_message_id",
               side_effect=lambda g, t, m: sent_texts.append(m) or 42):
        post_queue_reminder(config, state, now=now)
    # Nothing sent — returned early via "not scanned and not silent_lines"
    assert not any("Silent" in t for t in sent_texts)
    assert state["last_queue_fingerprint"] == "empty"
