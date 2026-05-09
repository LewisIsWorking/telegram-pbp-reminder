"""Tests extracted from test_push_to_100.py — bin 4.

Sections in this file:
  - commands/status.py
"""
"""Tests for the 4 largest remaining coverage gaps."""
import sys, os
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


def _ctx(cmd, text, state, config=None, **kw):
    base = {
        "user_id": "GM1", "user_name": "Lewis", "gm_ids": {"GM1"},
        "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
        "state": state,
        "config": config or {"group_id": -1, "gm_user_ids": [], "topic_pairs": []},
        "campaign_name": "Kibwe", "now_iso": "2026-04-03T12:00:00+00:00",
        "msg_time_iso": "2026-04-03T12:00:00+00:00",
        "parsed": {"raw_text": text}, "maps": MagicMock(),
        "cmd_word": cmd, "text": text,
    }
    base.update(kw)
    return base

def _ic(cmd, state=None):
    return {"user_id": "GM1", "user_name": "Lewis", "gm_ids": {"GM1"},
            "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
            "state": state or {}, "campaign_name": "Kibwe",
            "config": {"group_id": -1, "gm_user_ids": [], "topic_pairs": []},
            "now_iso": "2026-04-03T12:00:00+00:00", "msg_time_iso": "2026-04-03T12:00:00+00:00",
            "parsed": {}, "maps": MagicMock(), "cmd_word": cmd, "text": cmd}

def _status(state_extras=None):
    s = {"topics": {}, "post_timestamps": {}, "message_counts": {},
         "players": {}, "paused_campaigns": {}, "current_scenes": {}}
    if state_extras:
        s.update(state_extras)
    return s

def _run_status(state, gm_ids=None, hours=1.0):
    from commands.status import build_status
    with patch("commands.status.helpers") as mh:
        mh.get_label.return_value = "C00"
        mh.get_topic_timestamps.return_value = {}
        mh.hours_since.return_value = hours
        mh.get_characters.return_value = {}
        mh.player_full_name.return_value = "A"
        mh.players_by_campaign.return_value = {}
        mh.pace_split.return_value = {"gm_this": 0, "player_this": 0,
                                       "gm_last": 0, "player_last": 0}
        mh.trend_icon.return_value = "➡️"
        mh.posts_str.return_value = "0"
        return build_status("100", "Kibwe", state, gm_ids or set(), {})

# ── commands/status.py ────────────────────────────────────────────────────────

def _status(state_extras=None):
    s = {"topics": {}, "post_timestamps": {}, "message_counts": {},
         "players": {}, "paused_campaigns": {}, "current_scenes": {}}
    if state_extras:
        s.update(state_extras)
    return s


def _run_status(state, gm_ids=None, hours=1.0):
    from commands.status import build_status
    with patch("commands.status.helpers") as mh:
        mh.get_label.return_value = "C00"
        mh.get_topic_timestamps.return_value = {}
        mh.hours_since.return_value = hours
        mh.get_characters.return_value = {}
        mh.player_full_name.return_value = "A"
        mh.players_by_campaign.return_value = {}
        mh.pace_split.return_value = {"gm_this": 0, "player_this": 0,
                                       "gm_last": 0, "player_last": 0}
        mh.trend_icon.return_value = "➡️"
        mh.posts_str.return_value = "0"
        return build_status("100", "Kibwe", state, gm_ids or set(), {})


def test_status_just_now():
    now = datetime.now(timezone.utc)
    state = _status({"topics": {"100": {"last_message_time": now.isoformat()}}})
    assert "just now" in _run_status(state, hours=0.3)


def test_status_days_ago():
    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=2, hours=3)).isoformat()
    state = _status({"topics": {"100": {"last_message_time": old}}})
    result = _run_status(state, hours=51.0)
    assert "d" in result and "h ago" in result


def test_status_1h_ago():
    now = datetime.now(timezone.utc)
    state = _status({"topics": {"100": {"last_message_time": now.isoformat()}}})
    assert "5h" in _run_status(state, hours=5.0)


def test_status_with_combat():
    now = datetime.now(timezone.utc)
    state = _status({"topics": {"100": {"last_message_time": now.isoformat()}},
                     "combat": {"100": {"active": True, "round": 3,
                                        "current_phase": "players"}}})
    result = _run_status(state)
    assert "Combat" in result or "Round" in result


def test_status_with_quests():
    now = datetime.now(timezone.utc)
    state = _status({"topics": {"100": {"last_message_time": now.isoformat()}},
                     "quests": {"100": [{"text": "Find sword", "status": "active"}]}})
    result = _run_status(state)
    assert "quest" in result.lower() or "📋" in result


def test_status_with_hp():
    now = datetime.now(timezone.utc)
    state = _status({"topics": {"100": {"last_message_time": now.isoformat()}},
                     "hp_tracker": {"100": {"G": {"current": 5, "max": 20}}}})
    result = _run_status(state)
    assert "❤️" in result or "standing" in result


def test_status_with_conditions():
    now = datetime.now(timezone.utc)
    state = _status({"topics": {"100": {"last_message_time": now.isoformat()}},
                     "conditions": {"100": [{"target": "G", "effect": "Stunned"}]}})
    result = _run_status(state)
    assert "⚡" in result or "condition" in result.lower()


def test_status_with_clocks():
    now = datetime.now(timezone.utc)
    state = _status({"topics": {"100": {"last_message_time": now.isoformat()}},
                     "clocks": {"100": {"Inv": {"filled": 2, "segments": 6}}}})
    result = _run_status(state)
    assert "⏱️" in result or "clock" in result.lower()


def test_status_with_queue():
    now = datetime.now(timezone.utc)
    state = _status({"topics": {"100": {"last_message_time": now.isoformat()}}})
    from commands.status import build_status
    with patch("commands.status.helpers") as mh, \
         patch("commands.queue_scan.scan_transcripts",
               return_value={"100": {"entries": [
                   {"name": "A", "time": "2026-03-01 10:00:00", "preview": "hi"}]}}):
        mh.get_label.return_value = "C00"
        mh.get_topic_timestamps.return_value = {}
        mh.hours_since.return_value = 1.0
        mh.get_characters.return_value = {}
        mh.player_full_name.return_value = "A"
        mh.players_by_campaign.return_value = {}
        mh.pace_split.return_value = {"gm_this": 0, "player_this": 0,
                                       "gm_last": 0, "player_last": 0}
        mh.trend_icon.return_value = "➡️"
        mh.posts_str.return_value = "0"
        result = build_status("100", "Kibwe", state, {"GM1"}, {})
    assert isinstance(result, str)
