"""Tests extracted from test_push_to_100.py — bin 3.

Sections in this file:
  - cmd_info.py — missing commands
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

# ── cmd_info.py — missing commands ────────────────────────────────────────────

def _ic(cmd, state=None):
    return {"user_id": "GM1", "user_name": "Lewis", "gm_ids": {"GM1"},
            "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
            "state": state or {}, "campaign_name": "Kibwe",
            "config": {"group_id": -1, "gm_user_ids": [], "topic_pairs": []},
            "now_iso": "2026-04-03T12:00:00+00:00", "msg_time_iso": "2026-04-03T12:00:00+00:00",
            "parsed": {}, "maps": MagicMock(), "cmd_word": cmd, "text": cmd}


def test_cmd_info_overview():
    from dispatch.cmd_info import handle
    with patch("dispatch.cmd_info.tg.send_message"):
        assert handle(_ic("/overview", {"clocks": {}, "quests": {}, "npcs": {},
                                        "conditions": {}, "hp_tracker": {}})) is True


def test_cmd_info_combatlog():
    from dispatch.cmd_info import handle
    with patch("dispatch.cmd_info.tg.send_message"):
        assert handle(_ic("/combatlog", {"combat": {}})) is True


def test_cmd_info_party():
    from dispatch.cmd_info import handle
    with patch("dispatch.cmd_info.tg.send_message"):
        assert handle(_ic("/party", {"players": {}})) is True


def test_cmd_info_catchup():
    from dispatch.cmd_info import handle
    with patch("dispatch.cmd_info.tg.send_message"), \
         patch("dispatch.cmd_info.build_catchup", return_value="ok"):
        assert handle(_ic("/catchup", {"post_timestamps": {}, "away": {},
                                       "topics": {}, "acted_this_scene": {}})) is True


def test_cmd_info_quests():
    from dispatch.cmd_info import handle
    with patch("dispatch.cmd_info.tg.send_message"):
        assert handle(_ic("/quests", {"quests": {}})) is True


def test_cmd_info_pins():
    from dispatch.cmd_info import handle
    with patch("dispatch.cmd_info.tg.send_message"):
        assert handle(_ic("/pins", {"pins": {}})) is True


def test_cmd_info_loot():
    from dispatch.cmd_info import handle
    with patch("dispatch.cmd_info.tg.send_message"):
        assert handle(_ic("/lootlist", {"loot": {}})) is True

