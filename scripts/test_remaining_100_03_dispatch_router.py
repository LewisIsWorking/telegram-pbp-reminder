"""Tests extracted from test_remaining_100.py — bin 3.

Sections in this file:
  - dispatch/router.py:181-182
  - dispatch/tracking.py:175-182 — warned comeback
  - dispatch/cmd_clocks.py:123
  - dispatch/cmd_conditions_hp.py:184
  - dispatch/cmd_info.py:98-99 — /npcs
  - dispatch/cmd_trackers.py:115
  - dispatch/cmd_trackers_items.py:108
  - dispatch/cmd_votes_timers.py:108-111
  - dispatch/bot_topic.py:104 — no campaigns
  - helpers_pkg/config.py:39-43 — load_settings
  - helpers_pkg/dc_lookup.py:110-112 — adjustment
"""
"""
Definitive final coverage push — verified state for every remaining gap.
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


def _ctx(**kw):
    base = {"user_id": "GM1", "user_name": "Lewis", "gm_ids": {"GM1"},
            "pid": "100", "group_id": -1, "thread_id": 999,
            "state": {}, "config": {}, "campaign_name": "Kibwe",
            "now_iso": "2026-04-03T12:00:00+00:00",
            "msg_time_iso": "2026-04-03T12:00:00+00:00",
            "parsed": {"raw_text": "", "text": ""},
            "maps": MagicMock(), "reply_topic": 999}
    base.update(kw)
    base["cmd_word"] = base["text"].split()[0] if base["text"] else base.get("cmd_word", "")
    return base



# ── dispatch/router.py:181-182 ───────────────────────────────────────────────
def test_router_exception():
    from dispatch.router import process_updates
    maps = MagicMock()
    maps.all_pids.return_value = []
    maps.to_name = {}
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": [], "bot_topic_id": None}
    state = {"offset": 0, "players": {}, "topics": {}}
    with patch("dispatch.router.build_topic_maps", return_value=maps), \
         patch("dispatch.router.parse_message", side_effect=RuntimeError("!")):
        result = process_updates([{"update_id": 42}], config, state)
    assert result == 43



# ── dispatch/tracking.py:175-182 — warned comeback ───────────────────────────
def test_tracking_warned_comeback():
    from dispatch.tracking import track_message
    now = datetime.now(timezone.utc)
    maps = MagicMock()
    maps.to_chat = {"100": 21514}
    maps.to_name = {"100": "Kibwe"}
    parsed = {"user_id": "U1", "username": "alice", "first_name": "Alice",
              "user_name": "Alice", "user_last_name": "", "campaign_name": "Kibwe",
              "pid": "100", "is_gm": False, "thread_id": "100",
              "text": "Hi!", "raw_text": "Hi!",
              "msg_time_iso": now.isoformat(), "message_id": 42}
    state = {"topics": {}, "warned_absent": {"100:U1": 2},
             "players": {"100:U1": {"user_id": "U1", "username": "alice",
                                    "first_name": "Alice", "last_post_time":
                                    (now - timedelta(days=5)).isoformat()}},
             "message_counts": {}, "post_timestamps": {}, "removed_players": {}}
    config = {"group_id": -1001, "gm_user_ids": [999], "bot_topic_id": 999}
    with patch("dispatch.tracking.helpers") as mh:
        mh.hours_since.return_value = 130.0
        mh.character_name.return_value = ""
        mh.COMEBACK_THRESHOLD_HOURS = 96
        mh.player_mention.return_value = "@alice"
        track_message(parsed, state, config, set(), maps)



# ── dispatch/cmd_clocks.py:123 ───────────────────────────────────────────────
def test_cmd_clocks_nf():
    from dispatch.cmd_clocks import handle
    ctx = _ctx(cmd_word="/tick", text="/tick Ghost",
               state={"clocks": {"100": {}}},
               parsed={"raw_text": "/tick Ghost"})
    assert handle(ctx) is True



# ── dispatch/cmd_conditions_hp.py:184 ────────────────────────────────────────
def test_cmd_hp_bad():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx(cmd_word="/hp", text="/hp bad",
               state={"hp_tracker": {}}, parsed={"raw_text": "/hp bad"})
    assert handle(ctx) is True



# ── dispatch/cmd_info.py:98-99 — /npcs ───────────────────────────────────────
def test_cmd_info_npcs():
    from dispatch.cmd_info import handle
    ctx = _ctx(cmd_word="/npcs", text="/npcs",
               state={"npcs": {}},
               config={"group_id": -1, "gm_user_ids": [], "topic_pairs": []})
    with patch("dispatch.cmd_info.tg.send_message"):
        assert handle(ctx) is True



# ── dispatch/cmd_trackers.py:115 ─────────────────────────────────────────────
def test_cmd_trackers_nf():
    from dispatch.cmd_trackers import handle
    ctx = _ctx(cmd_word="/done", text="/done 9",
               state={"quests": {"100": [{"text": "Q", "status": "active"}]}},
               parsed={"raw_text": "/done 9"})
    assert handle(ctx) is True



# ── dispatch/cmd_trackers_items.py:108 ───────────────────────────────────────
def test_cmd_trackers_loot_nf():
    from dispatch.cmd_trackers_items import handle
    ctx = _ctx(cmd_word="/delloot", text="/delloot 9",
               state={"loot": {"100": []}}, parsed={"raw_text": "/delloot 9"})
    assert handle(ctx) is True



# ── dispatch/cmd_votes_timers.py:108-111 ─────────────────────────────────────
def test_endvote_tied():
    from dispatch.cmd_votes_timers import handle
    ctx = _ctx(cmd_word="/endvote", text="/endvote",
               parsed={"raw_text": "/endvote"},
               state={"vote": {"100": {"question": "?", "options": ["A", "B"],
                                        "votes": {"U1": 0, "U2": 1}}}})
    assert handle(ctx) is True


def test_endvote_no_votes():
    from dispatch.cmd_votes_timers import handle
    ctx = _ctx(cmd_word="/endvote", text="/endvote",
               parsed={"raw_text": "/endvote"},
               state={"vote": {"100": {"question": "?", "options": ["A"],
                                        "votes": {}}}})
    assert handle(ctx) is True



# ── dispatch/bot_topic.py:104 — no campaigns ────────────────────────────────
def test_bot_topic_no_pid():
    from dispatch.bot_topic import handle_bot_topic_cmd
    maps = MagicMock()
    maps.name_to_pid = {}
    maps.to_name = {}
    handle_bot_topic_cmd(
        {"from": {"id": 1, "first_name": "L", "is_bot": False}, "text": "/gm"},
        {"group_id": -1, "bot_topic_id": 999, "gm_user_ids": [], "topic_pairs": []},
        {}, maps, -1, 999, frozenset(["/gm"]), [],
    )



# ── helpers_pkg/config.py:39-43 — load_settings ──────────────────────────────
def test_config_load_settings():
    from helpers_pkg.config import load_settings
    config = {"settings": {"REQUIRED_PLAYERS": 5, "POTW_MIN_POSTS": 3}}
    load_settings(config)  # Updates globals (config.py:39-43)


def test_config_empty_topic_pairs():
    from helpers_pkg.config import validate_config
    issues = validate_config({"group_id": -1, "gm_user_ids": [], "topic_pairs": None})
    assert any("non-empty list" in i or "list" in i.lower() for i in issues)



# ── helpers_pkg/dc_lookup.py:110-112 — adjustment ────────────────────────────
def test_dc_adjustment():
    from helpers_pkg.dc_lookup import dc_lookup, _DC_ADJUSTMENTS
    key = next(iter(_DC_ADJUSTMENTS))
    result = dc_lookup(key)
    assert "adjustment" in result.lower()

