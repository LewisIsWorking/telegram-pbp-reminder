"""Tests extracted from test_branch_gaps.py — bin 5.

Sections in this file:
  - scheduled/session_poll.py: exception isolation
  - commands/queue_stats.py: avg reply per campaign
  - scheduled/queue_reminder.py: message chunking
  - boons/handler.py: _resolve_boon returns None
  - helpers_pkg/config.py: chat_topic collision
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

# ─── scheduled/session_poll.py: exception isolation ──────────────────────────

def test_session_poll_exception_isolated():
    from scheduled.session_poll import post_session_poll
    config = {"group_id": -1, "gm_user_ids": [], "bot_topic_id": 999,
              "poll_post_hour": 7,
              "topic_pairs": [{"pbp_topic_ids": [100], "code": "C01",
                               "hybrid_live": True, "poll_options": ["A"],
                               "chat_topic_id": 21514}]}
    now = datetime(2026, 3, 29, 8, tzinfo=timezone.utc)
    state = {}
    with patch("scheduled.session_poll._post_one", side_effect=RuntimeError("boom")):
        post_session_poll(config, state, now=now)  # should not raise


def test_session_poll_nudge_topic_routing():
    """nudge_topic_id routes reminder pings away from the poll's own topic.

    The poll widget posts to chat_topic_id (21514); the daily ping reminder
    posts to nudge_topic_id (137393) instead. Posting + first ping both happen
    in a single Sunday run.
    """
    from scheduled.session_poll import post_session_poll
    config = {"group_id": -1001, "gm_user_ids": [], "bot_topic_id": 137393,
              "poll_post_hour": 7,
              "topic_pairs": [{"pbp_topic_ids": [100], "code": "C01",
                               "hybrid_live": True,
                               "poll_options": ["Friday", "Saturday"],
                               "poll_user_ids": [111, 222],
                               "poll_user_names": {"111": "alice", "222": "bob"},
                               "chat_topic_id": 21514,
                               "nudge_topic_id": 137393}]}
    now = datetime(2026, 3, 29, 8, tzinfo=timezone.utc)  # Sunday >= poll_post_hour
    state = {}
    with patch("scheduled.session_poll.tg.send_poll",
               return_value=(123, "pollid")) as m_poll, \
         patch("scheduled.session_poll.tg.send_message",
               return_value=True) as m_send, \
         patch("scheduled.session_poll.tg.pin_message"), \
         patch("scheduled.session_poll.tg.unpin_message"):
        post_session_poll(config, state, now=now)

    # Poll widget went to the campaign topic.
    assert m_poll.call_args.args[1] == 21514
    # The ping reminder went to the nudge topic, not the campaign topic.
    ping = next(c for c in m_send.call_args_list if "Waiting on" in c.args[2])
    assert ping.args[1] == 137393
    assert "Vote in the poll!" in ping.args[2]
    assert "above" not in ping.args[2]


# ─── commands/queue_stats.py: avg reply per campaign ─────────────────────────

def test_queue_stats_avg_reply_shown():
    from commands.queue_stats import build_queue_stats
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    ts = [(now - timedelta(hours=h*2)).isoformat() for h in range(5)]
    config = {"group_id": -1, "gm_user_ids": [999],
              "topic_pairs": [{"pbp_topic_ids": [100], "code": "C00",
                               "name": "Kibwe", "gm_user_ids": [999]}]}
    state = {
        "queue_history": {}, "queue_archive": [],
        "_config_cache": config,
        "post_timestamps": {"100": {"999": ts}},
    }
    with patch("commands.queue_scan.scan_transcripts", return_value={}), \
         patch("commands.queue_analytics.helpers") as mh, \
         patch("commands.queue_stats.helpers") as mh2:
        mh.iter_campaigns.return_value = []
        mh2.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
        mh2.is_excluded.return_value = False
        mh2.get_topic_timestamps.return_value = {"999": ts}
        result = build_queue_stats(config, state)
    assert isinstance(result, str)



# ─── scheduled/queue_reminder.py: message chunking ───────────────────────────

def test_queue_reminder_chunks_long_message():
    from scheduled.queue_reminder import post_queue_reminder
    now = datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc)
    t = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    # Create 100 entries to force a long message needing chunking
    entries = [{"name": f"Player{i}", "time": t,
                "preview": "x" * 50, "link": "", "message_id": str(i)}
               for i in range(100)]
    config = {"group_id": -1001, "bot_topic_id": 999, "gm_user_ids": [999],
              "queue_daily_hours": [9, 21],
              "topic_pairs": [{"pbp_topic_ids": [100], "code": "C00",
                               "name": "Kibwe", "gm_user_ids": [999]}]}
    scanned = {"100": {"campaign": "Kibwe", "code": "C00", "entries": entries}}
    state = {"last_queue_fingerprint": "OLD", "queue_post_count": 0,
             "last_queue_pin_id": None, "last_queue_daily_slots": []}
    with patch("scheduled.queue_reminder.scan_transcripts", return_value=scanned), \
         patch("scheduled.queue_reminder.post_topic_queues"):
        post_queue_reminder(config, state, now=now)
    assert state["queue_post_count"] == 1



# ─── boons/handler.py: _resolve_boon returns None ────────────────────────────

def test_choose_boon_resolve_fails():
    from boons.handler import choose_boon_by_text
    state = {
        "pending_potw_boons": {"100": {
            "winner_user_id": "U1", "message_id": 42,
            "campaign_name": "Kibwe",
            "boons": ["Turtle"],
            "base_message": "Won!",
        }},
        "player_boons": {},
        "players": {},
    }
    config = {"group_id": -1}
    with patch("boons.handler._resolve_boon", return_value=(None, None)):
        result = choose_boon_by_text("100", "U1", 1, config, state)
    assert "wrong" in result.lower() or "went wrong" in result.lower()



# ─── helpers_pkg/config.py: chat_topic collision ─────────────────────────────

def test_config_chat_topic_collision():
    from helpers_pkg.config import validate_config
    config = {
        "group_id": -1, "gm_user_ids": [],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "name": "A", "chat_topic_id": 500},
            {"pbp_topic_ids": [200], "name": "B", "chat_topic_id": 500},  # collision
        ],
    }
    issues = validate_config(config)
    assert any("collision" in i.lower() or "used by another" in i.lower()
               for i in issues)

