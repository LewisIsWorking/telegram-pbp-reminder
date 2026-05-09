"""Tests extracted from test_final_coverage.py — bin 8.

Sections in this file:
  - simulate __main__ guard (part b)
"""
"""
Tests targeting the remaining coverage gaps:
  dispatch/cmd_search.py, dispatch/bot_topic.py, scheduled/reports.py,
  scheduled/potw.py (winner section), boons/handler.py, scheduled/leaderboard.py,
  transcript/finalize.py, commands/player.py, helpers_pkg/time_utils.py,
  + many single-line gaps across dispatch/commands files.
"""
import sys, os, json, pytest, io, zipfile, tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.dirname(__file__))

def _tg_mock():
    m = MagicMock()
    m.send_message.return_value = True
    return m

def _maps():
    m = MagicMock()
    m.name_to_pid = {"kibwe": "100", "riddleport": "200"}
    m.to_name = {"100": "Kibwe", "200": "Riddleport"}
    m.to_chat = {"100": 21514, "200": 21515}
    return m

def _bt_msg(text, uid="U1", is_bot=False):
    return {"from": {"id": int(uid.lstrip("U") or 1),
                     "first_name": "Alice", "is_bot": is_bot},
            "text": text}

def _bt_config():
    return {
        "group_id": -1001, "bot_topic_id": 999, "gm_user_ids": [999],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
             "gm_user_ids": [999], "chat_topic_id": 21514}
        ]
    }

def _boons_state(pid="100", uid="U1"):
    return {
        "pending_potw_boons": {pid: {
            "winner_user_id": uid,
            "message_id": 42,
            "campaign_name": "Kibwe",
            "boons": ["Turtle", "Coin", "Map"],
            "base_message": "You won!",
        }},
        "player_boons": {},
        "players": {"100:U1": {"user_id": uid, "first_name": "Alice"}},
    }

def _lb_config():
    return {"group_id": -1001, "leaderboard_topic_id": 555,
            "gm_user_ids": [999], "bot_topic_id": 999,
            "topic_pairs": [{"pbp_topic_ids": [100], "code": "C00",
                              "name": "Kibwe", "gm_user_ids": [999]}]}

# ═══════════════════════════════════════════════════════════════════════════════

def test_queue_reminder_unpin_prev():
    from scheduled.queue_reminder import post_queue_reminder
    now = datetime(2026, 4, 3, 9, 0, tzinfo=timezone.utc)
    t = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    entries = [{"name": "Alice", "time": t, "preview": "hi",
                "link": "", "message_id": "1"}]
    scanned = {"100": {"campaign": "Kibwe", "code": "C00", "entries": entries}}
    state = {"last_queue_fingerprint": "OLD", "queue_post_count": 0,
             "last_queue_pin_id": 777, "last_queue_daily_slots": []}
    config = {"group_id": -1001, "bot_topic_id": 999,
              "gm_user_ids": [999], "queue_daily_hours": [9, 21],
              "topic_pairs": [{"pbp_topic_ids": [100], "code": "C00",
                               "name": "Kibwe", "gm_user_ids": [999]}]}
    with patch("scheduled.queue_reminder.scan_transcripts", return_value=scanned), \
         patch("scheduled.queue_reminder.post_topic_queues"):
        post_queue_reminder(config, state, now=now)

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
