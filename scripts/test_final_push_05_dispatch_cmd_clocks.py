"""Coverage tests extracted from test_final_push.py — bin 5.

Sections in this file:
  - dispatch/cmd_clocks.py:123
  - dispatch/cmd_conditions_hp.py:184
  - dispatch/cmd_info.py:102-103 — /showvote
  - dispatch/cmd_votes_timers.py:108-111 — tied/no-votes
  - dispatch/cmd_trackers.py:115
  - dispatch/cmd_trackers_items.py:108
  - dispatch/cmd_gm.py:57 — /kick no target
  - dispatch/bot_topic.py:104 — no pid for global cmd
  - scheduled/session_poll.py:136 — empty roster
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


# ── dispatch/cmd_clocks.py:123 ───────────────────────────────────────────────
def test_cmd_clocks_real():
    from dispatch.cmd_clocks import handle
    ctx = {"cmd_word": "/tick", "text": "/tick Ghost",
           "user_id": "GM1", "user_name": "L", "gm_ids": {"GM1"},
           "pid": "100", "group_id": -1, "thread_id": 999,
           "state": {"clocks": {"100": {}}}, "config": {}, "campaign_name": "K",
           "now_iso": "2026-04-03T12:00:00+00:00",
           "msg_time_iso": "2026-04-03T12:00:00+00:00",
           "parsed": {"raw_text": "/tick Ghost"}, "maps": MagicMock(), "reply_topic": 999}
    assert handle(ctx) is True



# ── dispatch/cmd_conditions_hp.py:184 ────────────────────────────────────────
def test_cmd_hp_real():
    from dispatch.cmd_conditions_hp import handle
    ctx = {"cmd_word": "/hp", "text": "/hp badarg",
           "user_id": "GM1", "user_name": "L", "gm_ids": {"GM1"},
           "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
           "state": {"hp_tracker": {}}, "config": {}, "campaign_name": "K",
           "now_iso": "2026-04-03T12:00:00+00:00",
           "msg_time_iso": "2026-04-03T12:00:00+00:00",
           "parsed": {"raw_text": "/hp badarg"}, "maps": MagicMock()}
    assert handle(ctx) is True



# ── dispatch/cmd_info.py:102-103 — /showvote ─────────────────────────────────
def test_cmd_info_showvote_real():
    from dispatch.cmd_info import handle
    ctx = {"cmd_word": "/showvote", "text": "/showvote",
           "user_id": "GM1", "user_name": "L", "gm_ids": {"GM1"},
           "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
           "state": {"vote": {}}, "config": {}, "campaign_name": "K",
           "now_iso": "2026-04-03T12:00:00+00:00",
           "msg_time_iso": "2026-04-03T12:00:00+00:00",
           "parsed": {}, "maps": MagicMock()}
    with patch("dispatch.cmd_info.tg.send_message"):
        assert handle(ctx) is True



# ── dispatch/cmd_votes_timers.py:108-111 — tied/no-votes ────────────────────
def test_cmd_endvote_real():
    from dispatch.cmd_votes_timers import handle
    ctx = {"cmd_word": "/endvote", "text": "/endvote",
           "user_id": "GM1", "user_name": "L", "gm_ids": {"GM1"},
           "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
           "state": {"vote": {"100": {"question": "?",
                                       "options": ["A", "B"],
                                       "votes": {"U1": 0, "U2": 1}}}},
           "config": {}, "campaign_name": "K",
           "now_iso": "2026-04-03T12:00:00+00:00",
           "msg_time_iso": "2026-04-03T12:00:00+00:00",
           "parsed": {"raw_text": "/endvote"}, "maps": MagicMock()}
    assert handle(ctx) is True



# ── dispatch/cmd_trackers.py:115 ─────────────────────────────────────────────
def test_cmd_trackers_nf_real():
    from dispatch.cmd_trackers import handle
    ctx = {"cmd_word": "/done", "text": "/done 9",
           "user_id": "GM1", "user_name": "L", "gm_ids": {"GM1"},
           "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
           "state": {"quests": {"100": [{"text": "Q", "status": "active"}]}},
           "config": {}, "campaign_name": "K",
           "now_iso": "2026-04-03T12:00:00+00:00",
           "msg_time_iso": "2026-04-03T12:00:00+00:00",
           "parsed": {"raw_text": "/done 9"}, "maps": MagicMock()}
    assert handle(ctx) is True



# ── dispatch/cmd_trackers_items.py:108 ───────────────────────────────────────
def test_cmd_trackers_items_loot_real():
    from dispatch.cmd_trackers_items import handle
    ctx = {"cmd_word": "/delloot", "text": "/delloot 9",
           "user_id": "GM1", "user_name": "L", "gm_ids": {"GM1"},
           "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
           "state": {"loot": {"100": []}},
           "config": {}, "campaign_name": "K",
           "now_iso": "2026-04-03T12:00:00+00:00",
           "msg_time_iso": "2026-04-03T12:00:00+00:00",
           "parsed": {"raw_text": "/delloot 9"}, "maps": MagicMock()}
    assert handle(ctx) is True



# ── dispatch/cmd_gm.py:57 — /kick no target ─────────────────────────────────
def test_cmd_gm_kick_real():
    from dispatch.cmd_gm import handle
    ctx = {"cmd_word": "/kick", "text": "/kick",
           "user_id": "GM1", "user_name": "L", "gm_ids": {"GM1"},
           "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
           "state": {}, "config": {}, "campaign_name": "K",
           "now_iso": "2026-04-03T12:00:00+00:00",
           "msg_time_iso": "2026-04-03T12:00:00+00:00",
           "parsed": {"raw_text": "/kick"}, "maps": MagicMock()}
    assert handle(ctx) is True



# ── dispatch/bot_topic.py:104 — no pid for global cmd ───────────────────────
def test_bot_topic_no_pid_real():
    from dispatch.bot_topic import handle_bot_topic_cmd
    maps = MagicMock()
    maps.name_to_pid = {}
    maps.to_name = {}
    handle_bot_topic_cmd(
        {"from": {"id": 1, "first_name": "L", "is_bot": False}, "text": "/gm"},
        {"group_id": -1, "bot_topic_id": 999, "gm_user_ids": [], "topic_pairs": []},
        {}, maps, -1, 999, frozenset(["/gm"]), [],
    )



# ── scheduled/session_poll.py:136 — empty roster ────────────────────────────
def test_session_poll_empty_roster_real():
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
        "voted_uids": [], "last_ping_day": -1, "votes": {},
    }}}
    post_session_poll(config, state, now=now)


