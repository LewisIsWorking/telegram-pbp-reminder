"""Coverage tests extracted from test_branch_gaps.py — bin 1.

Sections in this file:
  - dispatch/cmd_gm.py: /setchar branches
  - dispatch/router.py: exception isolation
  - dispatch/tracking.py: comeback return branch
  - dispatch/comeback.py: _find_gm_mention fallback
  - dispatch/cmd_player.py: grand_total branch
  - commands/summary.py: hp_tracker branch

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


