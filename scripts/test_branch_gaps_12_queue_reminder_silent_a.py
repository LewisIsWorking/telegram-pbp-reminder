"""Tests extracted from test_branch_gaps.py — bin 12.

Sections in this file:
  - queue_reminder silent section integration (part a)
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

def test_queue_reminder_appends_silent_section():
    """Silent campaigns are appended at the bottom of the GM queue message."""
    from scheduled.queue_reminder import post_queue_reminder
    now = datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc)
    t = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    old_iso = (now - timedelta(days=12)).isoformat()
    config = {
        "group_id": -1001, "bot_topic_id": 999, "gm_user_ids": [999],
        "queue_daily_hours": [9, 21],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C01", "name": "Active", "gm_user_ids": [999]},
            {"pbp_topic_ids": [200], "code": "C08", "name": "Silent", "emoji": "\U0001f984"},
        ],
    }
    scanned = {"100": {"campaign": "Active", "code": "C01",
                       "entries": [{"name": "P", "time": t, "preview": "hi",
                                    "link": "", "message_id": "1"}]}}
    state = {
        "last_queue_fingerprint": "OLD", "queue_post_count": 0,
        "last_queue_pin_id": None, "last_queue_daily_slots": [],
        "topics": {"200": {"last_message_time": old_iso}},
    }
    sent_texts = []
    def _capture(gid, tid, text):
        sent_texts.append(text)
        return 42
    with patch("scheduled.queue_reminder.scan_transcripts", return_value=scanned), \
         patch("scheduled.queue_reminder.post_topic_queues"), \
         patch("scheduled.queue_reminder.tg.send_message_id", side_effect=_capture), \
         patch("scheduled.queue_reminder.tg.pin_message"), \
         patch("scheduled.queue_reminder.tg.unpin_message"):
        post_queue_reminder(config, state, now=now)
    combined = "\n".join(sent_texts)
    assert "Silent campaigns" in combined
    assert "C08: Silent" in combined
    assert "no posts for 12d" in combined

def test_queue_reminder_appends_caught_up_section():
    """Caught-up campaigns (0 unreplied, recent post) appear in their own section."""
    from scheduled.queue_reminder import post_queue_reminder
    now = datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc)
    t = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    recent_iso = (now - timedelta(hours=5)).isoformat()
    config = {
        "group_id": -1001, "bot_topic_id": 999, "gm_user_ids": [999],
        "queue_daily_hours": [9, 21],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C01", "name": "Active", "gm_user_ids": [999]},
            {"pbp_topic_ids": [300], "code": "C00", "name": "Riddleport", "emoji": "\U0001f3b2"},
        ],
    }
    scanned = {"100": {"campaign": "Active", "code": "C01",
                       "entries": [{"name": "P", "time": t, "preview": "hi",
                                    "link": "", "message_id": "1"}]}}
    state = {
        "last_queue_fingerprint": "OLD", "queue_post_count": 0,
        "last_queue_pin_id": None, "last_queue_daily_slots": [],
        "topics": {"300": {"last_message_time": recent_iso}},
    }
    sent_texts = []
    def _capture(gid, tid, text):
        sent_texts.append(text)
        return 42
    with patch("scheduled.queue_reminder.scan_transcripts", return_value=scanned), \
         patch("scheduled.queue_reminder.post_topic_queues"), \
         patch("scheduled.queue_reminder.tg.send_message_id", side_effect=_capture), \
         patch("scheduled.queue_reminder.tg.pin_message"), \
         patch("scheduled.queue_reminder.tg.unpin_message"):
        post_queue_reminder(config, state, now=now)
    combined = "\n".join(sent_texts)
    assert "Caught up" in combined
    assert "C00: Riddleport" in combined
    assert "last post 5h ago" in combined


def test_queue_reminder_posts_when_only_silent():
    """When total=0 but there are silent campaigns, the queue still posts."""
    from scheduled.queue_reminder import post_queue_reminder
    now = datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc)
    old_iso = (now - timedelta(days=14)).isoformat()
    config = {
        "group_id": -1001, "bot_topic_id": 999, "gm_user_ids": [999],
        "queue_daily_hours": [now.hour],
        "topic_pairs": [
            {"pbp_topic_ids": [200], "code": "C08", "name": "Silent", "emoji": "\U0001f984"},
        ],
    }
    state = {
        "last_queue_fingerprint": "OLD", "queue_post_count": 0,
        "last_queue_pin_id": None, "last_queue_daily_slots": [],
        "topics": {"200": {"last_message_time": old_iso}},
    }
    sent_texts = []
    def _capture(gid, tid, text):
        sent_texts.append(text)
        return 42
    with patch("scheduled.queue_reminder.scan_transcripts", return_value={}), \
         patch("scheduled.queue_reminder.post_topic_queues"), \
         patch("scheduled.queue_reminder.tg.send_message_id", side_effect=_capture), \
         patch("scheduled.queue_reminder.tg.pin_message"), \
         patch("scheduled.queue_reminder.tg.unpin_message"):
        post_queue_reminder(config, state, now=now)
    combined = "\n".join(sent_texts)
    assert "Silent campaigns" in combined
    assert "C08: Silent" in combined

def test_queue_reminder_silent_included_in_fingerprint():
    """Silent campaigns affect the fingerprint so re-post triggers on silence onset."""
    from scheduled.queue_reminder import post_queue_reminder
    now = datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc)
    old_iso = (now - timedelta(days=11)).isoformat()
    config = {
        "group_id": -1001, "bot_topic_id": 999, "gm_user_ids": [999],
        "queue_daily_hours": [now.hour],
        "topic_pairs": [
            {"pbp_topic_ids": [200], "code": "C08", "name": "Silent"},
        ],
    }
    # Fingerprint starts as "empty" but silent campaign makes it diverge → posts
    state = {
        "last_queue_fingerprint": "empty",
        "queue_post_count": 0, "last_queue_pin_id": None,
        "last_queue_daily_slots": [],
        "topics": {"200": {"last_message_time": old_iso}},
    }
    with patch("scheduled.queue_reminder.scan_transcripts", return_value={}), \
         patch("scheduled.queue_reminder.post_topic_queues"), \
         patch("scheduled.queue_reminder.tg.send_message_id", return_value=42), \
         patch("scheduled.queue_reminder.tg.pin_message"), \
         patch("scheduled.queue_reminder.tg.unpin_message"):
        post_queue_reminder(config, state, now=now)
    assert "silent:" in state.get("last_queue_fingerprint", "")
