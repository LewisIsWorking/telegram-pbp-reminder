"""Tests extracted from test_aaa_isolated.py — bin 3.

Sections in this file:
  - players/management.py:73 — no match continue
  - combat/commands.py:98 — long log truncated
  - combat/tracker.py:115 — GM round command
  - dispatch/bot_topic.py:104 — no pid for global cmd
  - dispatch/cmd_trackers.py:115 — quest not found
  - scheduled/session_poll.py:136 — empty roster return
  - checker.py:132 — process_updates called in main loop
  - dispatch/cmd_clocks.py:98-103 — /untick with amount
  - helpers_pkg/dc_lookup.py:110-112 — adjustment key lookup
"""
"""
MUST RUN FIRST (alphabetical ordering): these tests cover lines that
only hit in isolation before other tests cache module paths.

Naming: test_aaa_ ensures pytest runs this file before test_b*, test_c*, etc.
"""
import sys, os, json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))



# ── players/management.py:73 — no match continue ─────────────────────────────
def test_players_no_match_continue():
    from players.management import handle_kick
    state = {"players": {
        "100:U2": {"user_id": "U2", "first_name": "Bob",
                   "username": "bob", "last_name": ""}
    }}
    handle_kick("100", "Kibwe", "@nobody", state, -1, 999)



# ── combat/commands.py:98 — long log truncated ───────────────────────────────
def test_combat_long_log_early():
    from combat.commands import handle_enemies_command
    state = {"combat": {"100": {
        "active": True, "enemies": [],
        "log": [f"e{i}" for i in range(10)],
    }}}
    handle_enemies_command("", "100", "Kibwe", "2026-04-03T12:00:00", -1, 999, state)



# ── combat/tracker.py:115 — GM round command ─────────────────────────────────
def test_combat_tracker_gm_early():
    from combat.tracker import handle_combat_message
    state = {"combat": {"100": {
        "active": True, "log": [], "round": 1,
        "current_phase": "player", "actions_this_round": {},
        "participants": ["U1"],
    }}}
    handle_combat_message("/next", "/next", "GM1", "Lewis",
                          {"GM1"}, "100", "Kibwe",
                          "2026-04-03T12:00:00", -1, 999, state)



# ── dispatch/bot_topic.py:104 — no pid for global cmd ────────────────────────
def test_bot_topic_no_pid_early():
    from dispatch.bot_topic import handle_bot_topic_cmd
    maps = MagicMock()
    maps.name_to_pid = {}
    maps.to_name = {}
    handle_bot_topic_cmd(
        {"from": {"id": 1, "first_name": "L", "is_bot": False}, "text": "/gm"},
        {"group_id": -1, "bot_topic_id": 999, "gm_user_ids": [], "topic_pairs": []},
        {}, maps, -1, 999, frozenset(["/gm"]), [],
    )



# ── dispatch/cmd_trackers.py:115 — quest not found ───────────────────────────
def test_cmd_trackers_quest_nf_early():
    from dispatch.cmd_trackers import handle
    ctx = {"user_id": "GM1", "user_name": "Lewis", "gm_ids": {"GM1"},
           "pid": "100", "group_id": -1, "thread_id": 999,
           "state": {"quests": {"100": [{"text": "Q", "status": "active"}]}},
           "config": {}, "campaign_name": "Kibwe",
           "now_iso": "2026-04-03T12:00:00+00:00",
           "msg_time_iso": "2026-04-03T12:00:00+00:00",
           "parsed": {"raw_text": "/done 9"},
           "maps": MagicMock(), "reply_topic": 999,
           "cmd_word": "/done", "text": "/done 9"}
    assert handle(ctx) is True



# ── scheduled/session_poll.py:136 — empty roster return ──────────────────────
def test_session_poll_empty_roster_early():
    from scheduled.session_poll import post_session_poll
    now = datetime(2026, 3, 30, 10, tzinfo=timezone.utc)
    config = {"group_id": -1001, "bot_topic_id": 999, "poll_post_hour": 7,
              "gm_user_ids": [999], "topic_pairs": [
                  {"pbp_topic_ids": [100], "code": "C01", "hybrid_live": True,
                   "chat_topic_id": 21514, "poll_options": ["A"],
                   "poll_user_ids": [], "poll_user_names": {},
                   "allows_multiple_answers": False}]}
    state = {"session_poll": {"C01": {
        "week_iso": "sun2026-03-29", "poll_id": "p1", "poll_message_id": 99,
        "voted_uids": [], "last_ping_day": -1, "votes": {}}}}
    post_session_poll(config, state, now=now)



# ── checker.py:132 — process_updates called in main loop ────────────────────
def test_checker_loop_call():
    from dispatch.router import process_updates
    maps = MagicMock()
    maps.all_pids.return_value = []
    maps.to_name = {}
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": [], "bot_topic_id": None}
    state = {"offset": 0, "players": {}, "topics": {}}
    with patch("dispatch.router.build_topic_maps", return_value=maps):
        result = process_updates([], config, state)
    assert result == 0



# ── dispatch/cmd_clocks.py:98-103 — /untick with amount ──────────────────────
def test_untick_with_amount():
    from dispatch.cmd_clocks import handle
    from unittest.mock import MagicMock
    ctx = {
        "user_id": "GM1", "user_name": "L", "gm_ids": {"GM1"},
        "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
        "state": {"clocks": {"100": {"Investigation": {"filled": 3, "segments": 6,
                                                        "label": "Inv"}}}},
        "config": {}, "campaign_name": "K",
        "now_iso": "2026-04-03T12:00:00+00:00",
        "msg_time_iso": "2026-04-03T12:00:00+00:00",
        "parsed": {"raw_text": "/untick Investigation 2"},
        "maps": MagicMock(), "cmd_word": "/untick", "text": "/untick Investigation 2",
    }
    with patch("dispatch.cmd_clocks.helpers") as mh:
        mh.clock_display.return_value = "░░░░░░"
        assert handle(ctx) is True


def test_untick_amount_not_int():
    from dispatch.cmd_clocks import handle
    from unittest.mock import MagicMock
    ctx = {
        "user_id": "GM1", "user_name": "L", "gm_ids": {"GM1"},
        "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
        "state": {"clocks": {"100": {"Investigation": {"filled": 3, "segments": 6,
                                                        "label": "Inv"}}}},
        "config": {}, "campaign_name": "K",
        "now_iso": "2026-04-03T12:00:00+00:00",
        "msg_time_iso": "2026-04-03T12:00:00+00:00",
        "parsed": {"raw_text": "/untick Investigation lots"},
        "maps": MagicMock(), "cmd_word": "/untick", "text": "/untick Investigation lots",
    }
    with patch("dispatch.cmd_clocks.helpers") as mh:
        mh.clock_display.return_value = "░░░░░░"
        assert handle(ctx) is True



# ── helpers_pkg/dc_lookup.py:110-112 — adjustment key lookup ─────────────────
def test_dc_adjustment_key():
    from helpers_pkg.dc_lookup import dc_lookup, _DC_ADJUSTMENTS
    key = next(iter(_DC_ADJUSTMENTS))
    result = dc_lookup(key)
    assert "adjustment" in result.lower()

