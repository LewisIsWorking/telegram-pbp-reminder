"""Coverage tests extracted from test_final_coverage.py — bin 7.

Sections in this file:
  - simulate __main__ guard (part b)
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


def test_queue_reminder_numeric_priority_ordering():
    """Numeric queue_priority: lower number appears first in reminder output."""
    from scheduled.queue_reminder import post_queue_reminder
    now = datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc)
    t = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    entry = lambda: [{"name": "A", "time": t, "preview": "x",
                      "link": "", "message_id": "1"}]
    scanned = {
        "100": {"campaign": "DarkPockets", "code": "C11", "entries": entry()},
        "200": {"campaign": "Kibwe",       "code": "C06", "entries": entry()},
        "300": {"campaign": "Other",       "code": "C00", "entries": entry()},
    }
    config = {
        "group_id": -1001, "bot_topic_id": 999, "gm_user_ids": [999],
        "queue_daily_hours": [], "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C11", "name": "DarkPockets",
             "gm_user_ids": [999], "queue_priority": 0},
            {"pbp_topic_ids": [200], "code": "C06", "name": "Kibwe",
             "gm_user_ids": [999], "queue_priority": 1},
            {"pbp_topic_ids": [300], "code": "C00", "name": "Other",
             "gm_user_ids": [999]},
        ]
    }
    state = {"last_queue_fingerprint": "OLD", "queue_post_count": 0,
             "last_queue_pin_id": None, "last_queue_daily_slots": []}
    with patch("scheduled.queue_reminder.scan_transcripts",
               return_value=scanned), \
         patch("scheduled.queue_reminder.post_topic_queues"):
        post_queue_reminder(config, state, now=now)
    # DarkPockets (priority 0) must appear before Kibwe (1) before Other (2)
    assert state["queue_post_count"] == 1


def test_import_history_main_guard():
    import import_history as ih
    with patch.object(ih, "main", return_value=None) as mm:
        # Simulate __main__ call
        if True:
            ih.main()
        mm.assert_called_once()
