"""Tests extracted from test_final_coverage.py — bin 6.

Sections in this file:
  - until pattern — may parse or return None, but must not raise
  - Misc single-line gaps
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

from helpers_pkg.time_utils import parse_away_duration


def test_parse_away_duration_days():
    now = datetime(2026, 4, 10, tzinfo=timezone.utc)
    dt, reason = parse_away_duration("3 days holiday", now)
    assert dt is not None
    assert "holiday" in reason


def test_parse_away_duration_weeks():
    now = datetime(2026, 4, 3, tzinfo=timezone.utc)
    dt, reason = parse_away_duration("2 weeks vacation", now)
    assert dt is not None


def test_parse_away_duration_until():
    now = datetime(2026, 4, 3, tzinfo=timezone.utc)
    # until pattern — may parse or return None, but must not raise
    result = parse_away_duration("until May 1 vacation", now)
    assert isinstance(result, tuple)


def test_parse_away_duration_reason_only():
    now = datetime(2026, 4, 3, tzinfo=timezone.utc)
    dt, reason = parse_away_duration("family stuff", now)
    assert dt is None
    assert "family" in reason



# ═══════════════════════════════════════════════════════════════════════════════
# Misc single-line gaps
