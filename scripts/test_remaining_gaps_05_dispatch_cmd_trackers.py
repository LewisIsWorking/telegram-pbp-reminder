"""Coverage tests extracted from test_remaining_gaps.py — bin 5.

Sections in this file:
  - dispatch/cmd_trackers.py:115-118 — quest not found
  - dispatch/cmd_trackers_items.py:139-140 — npc not found
  - dispatch/cmd_votes_timers.py:119 — /timer no args
  - dispatch/comeback.py:36-52 — sends comeback alert
  - dispatch/poll_notify.py:62 — 3-way tie
  - dispatch/router.py:181-182 — exception isolation
  - dispatch/tracking.py:175-182 — warned player comeback
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


# ─── dispatch/cmd_trackers.py:115-118 — quest not found ─────────────────────

def test_cmd_trackers_quest_not_found_msg():
    from dispatch.cmd_trackers import handle as trackers_handle
    ctx = _ctx(cmd_word="/done", text="/done 99",
               state={"quests": {"100": []}},
               parsed={"raw_text": "/done 99"})
    result = trackers_handle(ctx)
    assert result is True


def test_cmd_trackers_quest_non_numeric():
    from dispatch.cmd_trackers import handle as trackers_handle
    ctx = _ctx(cmd_word="/delquest", text="/delquest notanumber",
               state={"quests": {"100": []}},
               parsed={"raw_text": "/delquest notanumber"})
    result = trackers_handle(ctx)
    assert result is True



# ─── dispatch/cmd_trackers_items.py:139-140 — npc not found ──────────────────

def test_cmd_trackers_npc_not_found():
    from dispatch.cmd_trackers_items import handle as ti_handle
    ctx = _ctx(cmd_word="/delnpc", text="/delnpc 99",
               state={"npcs": {"100": []}},
               parsed={"raw_text": "/delnpc 99"})
    result = ti_handle(ctx)
    assert result is True


def test_cmd_trackers_npc_non_numeric():
    from dispatch.cmd_trackers_items import handle as ti_handle
    ctx = _ctx(cmd_word="/delnpc", text="/delnpc notanumber",
               state={"npcs": {"100": []}},
               parsed={"raw_text": "/delnpc notanumber"})
    result = ti_handle(ctx)
    assert result is True



# ─── dispatch/cmd_votes_timers.py:119 — /timer no args ───────────────────────

def test_cmd_timer_no_args():
    from dispatch.cmd_votes_timers import handle as vt_handle
    ctx = _ctx(cmd_word="/timer", text="/timer",
               parsed={"raw_text": "/timer"})
    result = vt_handle(ctx)
    assert result is True



# ─── dispatch/comeback.py:36-52 — sends comeback alert ──────────────────────

def test_comeback_sends_alert():
    from dispatch.comeback import check_comeback
    now = datetime.now(timezone.utc)
    old_player = {"user_id": "U1", "username": "alice",
                  "last_post_time": (now - timedelta(days=10)).isoformat()}
    parsed = {
        "user_id": "U1", "username": "alice", "first_name": "Alice",
        "user_name": "Alice", "campaign_name": "Kibwe",
        "msg_time_iso": now.isoformat(),
        "thread_id": "100", "pid": "100", "is_gm": False, "text": "Hello!",
    }
    config = {"group_id": -1001, "gm_user_ids": [999], "bot_topic_id": 999}
    state = {}
    with patch("dispatch.comeback.helpers") as mh:
        mh.hours_since.return_value = 250.0
        mh.character_name.return_value = ""
        mh.COMEBACK_THRESHOLD_HOURS = 168
        check_comeback(parsed, old_player, state, config, set())



# ─── dispatch/poll_notify.py:62 — 3-way tie ──────────────────────────────────

def test_poll_notify_three_way_tie():
    from dispatch.poll_tally import _lead_summary
    votes = {"0": ["U1"], "1": ["U2"], "2": ["U3"]}
    options = ["Friday", "Saturday", "Sunday"]
    result = _lead_summary(votes, options)
    assert "tie" in result.lower()



# ─── dispatch/router.py:181-182 — exception isolation ────────────────────────

def test_router_exception_isolation():
    from dispatch.router import process_updates
    update = {"update_id": 100}
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": [], "bot_topic_id": None}
    state = {"offset": 0, "players": {}, "topics": {}}
    maps = MagicMock(); maps.all_pids.return_value = []; maps.to_name = {}
    with patch("dispatch.router.build_topic_maps", return_value=maps), \
         patch("dispatch.router.parse_message", side_effect=RuntimeError("boom")):
        result = process_updates([update], config, state)
    assert result == 101



# ─── dispatch/tracking.py:175-182 — warned player comeback ──────────────────

def test_tracking_warned_player_returns():
    from dispatch.tracking import track_message
    now = datetime.now(timezone.utc)
    maps = MagicMock()
    maps.to_chat = {"100": 21514}
    maps.to_name = {"100": "Kibwe"}
    parsed = {
        "user_id": "U1", "username": "alice", "first_name": "Alice",
        "user_name": "Alice", "campaign_name": "Kibwe",
        "pid": "100", "is_gm": False, "thread_id": "100",
        "text": "Hello!", "raw_text": "Hello!",
        "last_name": "", "user_last_name": "",
        "msg_time_iso": now.isoformat(),
        "message_id": 42,
    }
    config = {"group_id": -1001, "gm_user_ids": [999], "bot_topic_id": 999}
    state = {
        "topics": {},
        "warned_absent": {"100:U1": 2},  # warn level >= 2 (integer)
        "players": {"100:U1": {"user_id": "U1", "username": "alice",
                               "first_name": "Alice", "last_post_time":
                               (now - timedelta(days=5)).isoformat()}},
        "message_counts": {}, "post_timestamps": {}, "removed_players": {},
    }
    with patch("dispatch.tracking.helpers") as mh:
        mh.hours_since.return_value = 120.0
        mh.character_name.return_value = "Amara"
        mh.player_mention.return_value = "@alice"
        mh.COMEBACK_THRESHOLD_HOURS = 96
        track_message(parsed, state, config, set(), maps)


