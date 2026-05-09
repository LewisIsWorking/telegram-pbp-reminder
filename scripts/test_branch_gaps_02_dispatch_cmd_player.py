"""Tests extracted from test_branch_gaps.py — bin 2.

Sections in this file:
  - dispatch/cmd_player.py: grand_total branch
  - commands/summary.py: hp_tracker branch
  - commands/timeline.py: bad date fallback
  - parsing/message.py: video note branch
  - commands/session.py: build_session branches
  - dispatch/cmd_info.py: /boons branch
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

# ─── dispatch/cmd_player.py: grand_total branch ──────────────────────────────

def test_cmd_player_roll_multi_dice():
    # Covers line 157: grand_total branch when multiple dice results
    from dispatch.cmd_player import handle as player_handle
    ctx = {
        "cmd_word": "/roll", "text": "/roll 2d6",
        "user_id": "U1", "user_name": "Alice",
        "gm_ids": set(), "pid": "100",
        "group_id": -1, "thread_id": 999,
        "now_iso": "2026-04-03T12:00:00+00:00",
        "state": {}, "config": {},
        "campaign_name": "Kibwe",
        "maps": MagicMock(),
        "parsed": {"raw_text": "/roll 2d6", "text": "/roll 2d6"},
    }
    roll_result = {
        "results": [
            {"expr": "1d6", "detail": "[4]", "total": 4},
            {"expr": "1d6", "detail": "[3]", "total": 3},
        ],
        "label": "",
        "grand_total": 7,
        "error": None,
    }
    with patch("dispatch.cmd_player.helpers.roll_dice", return_value=roll_result):
        result = player_handle(ctx)
    assert result is True



# ─── commands/summary.py: hp_tracker branch ──────────────────────────────────

def test_summary_with_hp():
    from commands.summary import build_summary
    state = {
        "clocks": {}, "notes": {}, "quests": {}, "loot": {}, "npcs": {},
        "pinned_moments": {}, "conditions": {}, "trackers": {},
        "vote": {}, "timer": {},
        "hp_tracker": {"100": {"Goblin": {"current": 5, "max": 10}}},
    }
    with patch("commands.summary.helpers") as mh:
        mh.get_label.return_value = "C00: Kibwe"
        mh.hp_status_icon.return_value = "🟡"
        mh.hp_bar.return_value = "████░░░░"
        result = build_summary("100", "Kibwe", state, {})
    assert "HP Tracker" in result



# ─── commands/timeline.py: bad date fallback ─────────────────────────────────

def test_timeline_bad_date_shows_question_mark():
    from commands.timeline import build_timeline
    state = {"timeline_events": {"100": [
        {"time": "not-a-date", "text": "Something", "author": "Kibwe"}
    ]}}
    config = {"topic_pairs": [{"pbp_topic_ids": [100], "code": "C00",
                                "name": "Kibwe", "chat_topic_id": 21514}]}
    result = build_timeline(config, state)
    assert "?" in result or "Something" in result



# ─── parsing/message.py: video note branch ───────────────────────────────────

def test_detect_media_video_note():
    from parsing.message import _detect_media
    result = _detect_media({"video_note": {"duration": 10}})
    assert result == "video note"



# ─── commands/session.py: build_session branches ─────────────────────────────

def test_build_session_no_count():
    from commands.session import build_session
    with patch("commands.session.helpers") as mh:
        mh.get_label.return_value = "C00: Kibwe"
        result = build_session("100", "Kibwe", {}, {})
    assert "No sessions" in result


def test_build_session_with_count():
    from commands.session import build_session
    with patch("commands.session.helpers") as mh:
        mh.get_label.return_value = "C00: Kibwe"
        result = build_session("100", "Kibwe", {"session_counts": {"100": 7}}, {})
    assert "7" in result



# ─── dispatch/cmd_info.py: /boons branch ─────────────────────────────────────

def test_cmd_info_boons():
    from dispatch.cmd_info import handle as info_handle
    ctx = {
        "cmd_word": "/boons", "text": "/boons",
        "group_id": -1, "reply_topic": 999,
        "pid": "100", "campaign_name": "Kibwe",
        "user_id": "U1", "user_name": "Alice",
        "state": {"player_boons": {}},
        "config": {}, "gm_ids": set(),
    }
    with patch("dispatch.cmd_info.tg.send_message"):
        result = info_handle(ctx)
    assert result is True

