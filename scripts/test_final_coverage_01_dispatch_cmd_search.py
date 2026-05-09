"""Coverage tests extracted from test_final_coverage.py — bin 1.

Sections in this file:
  - dispatch/cmd_search.py
  - Same name+category twice
  - dispatch/bot_topic.py
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


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
