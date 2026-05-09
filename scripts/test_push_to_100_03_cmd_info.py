"""Coverage tests extracted from test_push_to_100.py — bin 3.

Sections in this file:
  - cmd_info.py — missing commands
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


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


