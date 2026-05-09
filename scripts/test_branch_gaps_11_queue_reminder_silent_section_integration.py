"""Coverage tests extracted from test_branch_gaps.py — bin 11.

Sections in this file:
  - queue_reminder silent section integration

Targeted tests for specific uncovered branches in the production
modules listed above. Module imports are duplicated from the original
``test_branch_gaps.py`` header; per-section helper functions are
extracted alongside their sections.
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


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

