"""Tests extracted from test_branch_gaps.py — bin 1.

Sections in this file:
  - dispatch/cmd_gm.py: /setchar branches
  - dispatch/router.py: exception isolation
  - dispatch/tracking.py: comeback return branch
  - dispatch/comeback.py: _find_gm_mention fallback
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

# ─── dispatch/cmd_gm.py: /setchar branches ───────────────────────────────────

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


def test_setchar_no_args():
    from dispatch.cmd_gm import handle as gm_handle
    ctx = _gm_ctx("/setchar")
    ctx["state"] = {}
    result = gm_handle(ctx)
    assert result is True  # Usage message sent


def test_setchar_player_not_found():
    from dispatch.cmd_gm import handle as gm_handle
    ctx = _gm_ctx("/setchar @nobody Drax")
    ctx["state"] = {"players": {}}
    result = gm_handle(ctx)
    assert result is True


def test_setchar_player_found():
    from dispatch.cmd_gm import handle as gm_handle
    ctx = _gm_ctx("/setchar @alice Amara")
    ctx["state"] = {"players": {
        "100:U1": {"user_id": "U1", "username": "alice", "pbp_topic_id": "100"}
    }}
    result = gm_handle(ctx)
    assert result is True
    assert ctx["state"]["characters"]["100"]["U1"] == "Amara"



# ─── dispatch/router.py: exception isolation ─────────────────────────────────

def test_router_isolates_update_error():
    from dispatch.router import process_updates
    bad_update = {"update_id": 999, "message": None}  # will cause error in parsing
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": [], "bot_topic_id": None}
    state = {"offset": 0, "players": {}, "topics": {}}
    maps = MagicMock()
    maps.all_pids.return_value = []
    with patch("dispatch.router.build_topic_maps", return_value=maps), \
         patch("dispatch.router.parse_message", side_effect=Exception("boom")):
        result = process_updates([bad_update], config, state)
    assert result == 1000  # offset = update_id + 1



# ─── dispatch/tracking.py: comeback return branch ────────────────────────────

def test_tracking_comeback_sends_to_chat():
    from dispatch.comeback import check_comeback
    now = datetime.now(timezone.utc)
    old_player = {"user_id": "U1", "username": "alice",
                  "last_post_time": (now - timedelta(days=10)).isoformat()}
    parsed = {"user_id": "U1", "username": "alice", "first_name": "Alice",
              "user_name": "Alice", "campaign_name": "Kibwe",
              "msg_time_iso": "2026-04-03T12:00:00+00:00",
              "thread_id": "100", "pid": "100",
              "is_gm": False, "text": "Hello!"}
    config = {"group_id": -1001, "gm_user_ids": [999]}
    state = {}
    with patch("dispatch.comeback.helpers") as mh:
        mh.hours_since.return_value = 250.0
        mh.character_name.return_value = "Amara"
        mh.COMEBACK_THRESHOLD_HOURS = 168
        check_comeback(parsed, old_player, state, config, set())



# ─── dispatch/comeback.py: _find_gm_mention fallback ─────────────────────────

def test_find_gm_mention_fallback():
    from dispatch.comeback import _find_gm_mention
    state = {"players": {}}
    result = _find_gm_mention(state, {999})
    assert isinstance(result, str)

