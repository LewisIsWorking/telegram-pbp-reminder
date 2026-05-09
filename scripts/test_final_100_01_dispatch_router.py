"""Tests extracted from test_final_100.py — bin 1.

Sections in this file:
  - dispatch/router.py: _build_poll_id_map, _find_pair, _handle_poll_answer
"""
"""
Final push: tests for the large remaining uncovered blocks.
Focuses on router poll/callback/reaction handling, tracking GM-reply logging,
cmd_player /available, summary content, and other high-impact gaps.
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

def _pc(**kw):
    base = {"user_id": "U1", "user_name": "Alice", "gm_ids": set(),
            "pid": "100", "group_id": -1, "thread_id": 999,
            "state": {}, "config": {}, "campaign_name": "Kibwe",
            "now_iso": "2026-04-03T12:00:00+00:00",
            "msg_time_iso": "2026-04-03T12:00:00+00:00",
            "parsed": {"raw_text": ""}, "maps": MagicMock(), "reply_topic": 999}
    base.update(kw)
    base["cmd_word"] = base["text"].split()[0]
    return base

def _info_ctx(cmd, state=None):
    return {"cmd_word": cmd, "text": cmd,
            "user_id": "GM1", "user_name": "L", "gm_ids": {"GM1"},
            "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
            "state": state or {"vote": {}, "timer": {}, "clocks": {},
                               "player_boons": {}},
            "config": {"group_id": -1, "gm_user_ids": [], "topic_pairs": []},
            "campaign_name": "Kibwe", "now_iso": "2026-04-03T12:00:00+00:00",
            "msg_time_iso": "2026-04-03T12:00:00+00:00",
            "parsed": {}, "maps": MagicMock()}

# ─── dispatch/router.py: _build_poll_id_map, _find_pair, _handle_poll_answer ─

def test_build_poll_id_map():
    from dispatch.poll_router import build_poll_id_map as _build_poll_id_map
    state = {"session_poll": {
        "C01": {"poll_id": "p1"},
        "C02": {"poll_id": "p2"},
        "C03": {},  # no poll_id → skipped
    }}
    result = _build_poll_id_map(state)
    assert result == {"p1": "C01", "p2": "C02"}


def test_find_pair_found():
    from dispatch.poll_router import find_pair as _find_pair
    config = {"topic_pairs": [{"code": "C01", "pbp_topic_ids": [100]}]}
    assert _find_pair(config, "C01")["pbp_topic_ids"] == [100]


def test_find_pair_not_found():
    from dispatch.poll_router import find_pair as _find_pair
    assert _find_pair({"topic_pairs": []}, "C99") is None


def test_handle_poll_answer_known_poll():
    from dispatch.poll_router import handle_poll_answer as _handle_poll_answer
    config = {"topic_pairs": [
        {"code": "C01", "pbp_topic_ids": [100],
         "poll_options": ["Friday", "Saturday"],
         "poll_user_ids": [111], "poll_user_names": {}}
    ]}
    state = {"session_poll": {"C01": {"poll_id": "p1", "voted_uids": [], "votes": {}}}}
    poll_answer = {"poll_id": "p1", "option_ids": [0],
                   "user": {"id": 111, "first_name": "Alice"}}
    with patch("dispatch.poll_router.notify_vote"), \
         patch("dispatch.poll_router.capture_unknown_voter"):
        _handle_poll_answer(poll_answer, config, state)
    assert "111" in state["session_poll"]["C01"]["voted_uids"]


def test_handle_poll_answer_unknown_poll():
    from dispatch.poll_router import handle_poll_answer as _handle_poll_answer
    _handle_poll_answer({"poll_id": "unknown", "option_ids": [],
                         "user": {"id": 1, "first_name": "?"}},
                        {}, {"session_poll": {}})


def test_process_updates_poll_answer():
    from dispatch.router import process_updates
    maps = MagicMock()
    maps.all_pids.return_value = []
    maps.to_name = {}
    config = {"group_id": -1001, "gm_user_ids": [], "topic_pairs": [], "bot_topic_id": None}
    state = {"offset": 0, "players": {}, "topics": {},
             "session_poll": {"C01": {"poll_id": "p1", "voted_uids": [], "votes": {}}}}
    with patch("dispatch.router.build_topic_maps", return_value=maps), \
         patch("dispatch.poll_router.notify_vote"), \
         patch("dispatch.poll_router.capture_unknown_voter"):
        result = process_updates(
            [{"update_id": 1, "poll_answer": {
                "poll_id": "p1", "option_ids": [0],
                "user": {"id": 111, "first_name": "Alice"}}}],
            config, state)
    assert result == 2


def test_process_updates_boon_callback():
    from dispatch.router import process_updates
    maps = MagicMock()
    maps.all_pids.return_value = []
    maps.to_name = {}
    config = {"group_id": -1001, "gm_user_ids": [], "topic_pairs": [], "bot_topic_id": None}
    state = {"offset": 0, "players": {}, "topics": {}}
    with patch("dispatch.router.build_topic_maps", return_value=maps), \
         patch("dispatch.router.process_boon_callback"):
        result = process_updates(
            [{"update_id": 2, "callback_query": {
                "id": "cb1", "data": "boon:100:0",
                "from": {"id": 1, "first_name": "Alice"},
                "message": {"message_id": 42, "chat": {"id": -1001}}}}],
            config, state)
    assert result == 3


def test_process_updates_reaction():
    from dispatch.router import process_updates
    maps = MagicMock()
    maps.all_pids.return_value = []
    maps.to_name = {}
    config = {"group_id": -1001, "gm_user_ids": [], "topic_pairs": [], "bot_topic_id": None}
    state = {"offset": 0, "players": {}, "topics": {}}
    with patch("dispatch.router.build_topic_maps", return_value=maps), \
         patch("commands.reactions.process_reaction"):
        result = process_updates(
            [{"update_id": 3, "message_reaction": {
                "message_id": 10, "user": {"id": 1}, "chat": {"id": -1001}}}],
            config, state)
    assert result == 4


def test_process_updates_bot_topic_message():
    from dispatch.router import process_updates
    maps = MagicMock()
    maps.all_pids.return_value = []
    maps.to_name = {}
    config = {"group_id": -1001, "gm_user_ids": [], "topic_pairs": [], "bot_topic_id": 999}
    state = {"offset": 0, "players": {}, "topics": {}}
    with patch("dispatch.router.build_topic_maps", return_value=maps), \
         patch("dispatch.router.handle_bot_topic_cmd"):
        result = process_updates(
            [{"update_id": 4, "message": {
                "message_id": 50, "message_thread_id": 999,
                "chat": {"id": -1001},
                "from": {"id": 1, "first_name": "Lewis", "is_bot": False},
                "text": "/status kibwe"}}],
            config, state)
    assert result == 5


def test_process_updates_no_message():
    from dispatch.router import process_updates
    maps = MagicMock()
    maps.all_pids.return_value = []
    maps.to_name = {}
    config = {"group_id": -1001, "gm_user_ids": [], "topic_pairs": [], "bot_topic_id": None}
    state = {"offset": 0, "players": {}, "topics": {}}
    with patch("dispatch.router.build_topic_maps", return_value=maps):
        result = process_updates([{"update_id": 5}], config, state)
    assert result == 6

