"""Tests extracted from test_final_coverage.py — bin 1.

Sections in this file:
  - dispatch/cmd_search.py
  - Same name+category twice
  - dispatch/bot_topic.py
"""
"""
Tests targeting the remaining coverage gaps:
  dispatch/cmd_search.py, dispatch/bot_topic.py, scheduled/reports.py,
  scheduled/potw.py (winner section), boons/handler.py, scheduled/leaderboard.py,
  transcript/finalize.py, commands/player.py, helpers_pkg/time_utils.py,
  + many single-line gaps across dispatch/commands files.
"""
import sys, os, json, pytest, io, zipfile, tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.dirname(__file__))

def _tg_mock():
    m = MagicMock()
    m.send_message.return_value = True
    return m

def _maps():
    m = MagicMock()
    m.name_to_pid = {"kibwe": "100", "riddleport": "200"}
    m.to_name = {"100": "Kibwe", "200": "Riddleport"}
    m.to_chat = {"100": 21514, "200": 21515}
    return m

def _bt_msg(text, uid="U1", is_bot=False):
    return {"from": {"id": int(uid.lstrip("U") or 1),
                     "first_name": "Alice", "is_bot": is_bot},
            "text": text}

def _bt_config():
    return {
        "group_id": -1001, "bot_topic_id": 999, "gm_user_ids": [999],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
             "gm_user_ids": [999], "chat_topic_id": 21514}
        ]
    }

def _boons_state(pid="100", uid="U1"):
    return {
        "pending_potw_boons": {pid: {
            "winner_user_id": uid,
            "message_id": 42,
            "campaign_name": "Kibwe",
            "boons": ["Turtle", "Coin", "Map"],
            "base_message": "You won!",
        }},
        "player_boons": {},
        "players": {"100:U1": {"user_id": uid, "first_name": "Alice"}},
    }

def _lb_config():
    return {"group_id": -1001, "leaderboard_topic_id": 555,
            "gm_user_ids": [999], "bot_topic_id": 999,
            "topic_pairs": [{"pbp_topic_ids": [100], "code": "C00",
                              "name": "Kibwe", "gm_user_ids": [999]}]}

# ═══════════════════════════════════════════════════════════════════════════════
# dispatch/cmd_search.py

# ═══════════════════════════════════════════════════════════════════════════════

from dispatch.cmd_search import handle_search

def _tg_mock():
    m = MagicMock()
    m.send_message.return_value = True
    return m


def test_search_empty_query():
    tg = _tg_mock()
    handle_search("", -1, 999, tg)
    tg.send_message.assert_called_once()
    assert "Usage" in tg.send_message.call_args[0][2]


def test_search_network_error():
    tg = _tg_mock()
    import requests as _req
    with patch("dispatch.cmd_search.requests.post",
               side_effect=_req.RequestException("down")):
        handle_search("fireball", -1, 999, tg)
    assert "failed" in tg.send_message.call_args[0][2].lower()


def test_search_http_error():
    tg = _tg_mock()
    m = MagicMock(); m.status_code = 500
    with patch("dispatch.cmd_search.requests.post", return_value=m):
        handle_search("fireball", -1, 999, tg)
    assert "error" in tg.send_message.call_args[0][2].lower()


def test_search_no_hits():
    tg = _tg_mock()
    m = MagicMock(); m.status_code = 200
    m.json.return_value = {"hits": {"hits": [], "total": {"value": 0}}}
    with patch("dispatch.cmd_search.requests.post", return_value=m):
        handle_search("zzznoresults", -1, 999, tg)
    assert "No results" in tg.send_message.call_args[0][2]


def test_search_with_results():
    tg = _tg_mock()
    m = MagicMock(); m.status_code = 200
    m.json.return_value = {"hits": {"hits": [
        {"_source": {"name": "Fireball", "category": "spell",
                     "url": "/spells/fireball", "level": 3,
                     "rarity": "common", "summary": "A ball of fire.",
                     "actions": "2A", "tradition": "arcane"}}
    ], "total": {"value": 1}}}
    with patch("dispatch.cmd_search.requests.post", return_value=m):
        handle_search("fireball", -1, 999, tg)
    msg = tg.send_message.call_args[0][2]
    assert "Fireball" in msg
    assert "fireball" in msg.lower()


def test_search_rare_item():
    tg = _tg_mock()
    m = MagicMock(); m.status_code = 200
    m.json.return_value = {"hits": {"hits": [
        {"_source": {"name": "Rare Sword", "category": "weapon",
                     "url": "/weapons/rare-sword", "level": 10,
                     "rarity": "rare", "summary": "", "actions": ""}}
    ], "total": {"value": 1}}}
    with patch("dispatch.cmd_search.requests.post", return_value=m):
        handle_search("rare sword", -1, 999, tg)
    msg = tg.send_message.call_args[0][2]
    assert "rare" in msg.lower()


def test_search_deduplicates():
    tg = _tg_mock()
    m = MagicMock(); m.status_code = 200
    # Same name+category twice
    hit = {"_source": {"name": "Shield", "category": "equipment",
                       "url": "/items/shield", "level": 0,
                       "rarity": "common", "summary": "", "actions": ""}}
    m.json.return_value = {"hits": {"hits": [hit, hit], "total": {"value": 2}}}
    with patch("dispatch.cmd_search.requests.post", return_value=m):
        handle_search("shield", -1, 999, tg)
    msg = tg.send_message.call_args[0][2]
    assert msg.count("Shield") == 1



# ═══════════════════════════════════════════════════════════════════════════════
# dispatch/bot_topic.py
