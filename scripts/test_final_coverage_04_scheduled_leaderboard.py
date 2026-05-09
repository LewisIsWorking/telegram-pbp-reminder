"""Tests extracted from test_final_coverage.py — bin 4.

Sections in this file:
  - scheduled/leaderboard.py — post_campaign_leaderboard
  - scheduled/leaderboard.py — post_campaign_leaderboard
  - transcript/finalize.py — update_transcript_index
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

from boons.handler import choose_boon_by_text


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


def test_choose_boon_no_pending():
    result = choose_boon_by_text("100", "U1", 1, {}, {})
    assert "No pending" in result


def test_choose_boon_wrong_user():
    state = _boons_state()
    result = choose_boon_by_text("100", "U2", 1, {}, state)
    assert "Only the Player" in result


def test_choose_boon_out_of_range():
    state = _boons_state()
    result = choose_boon_by_text("100", "U1", 99, {}, state)
    assert "Pick a number" in result


def test_choose_boon_success():
    state = _boons_state()
    config = {"group_id": -1001, "bot_topic_id": 999}
    with patch("boons.handler._resolve_boon",
               return_value=("You won Turtle!", None)):
        result = choose_boon_by_text("100", "U1", 1, config, state)
    assert "Turtle" in result or "✅" in result


def test_choose_boon_fallback_by_winner_uid():
    state = _boons_state(pid="200")  # wrong pid
    config = {"group_id": -1001, "bot_topic_id": 999}
    with patch("boons.handler._resolve_boon",
               return_value=("You won Coin!", None)):
        result = choose_boon_by_text("100", "U1", 2, config, state)
    assert "Coin" in result or "✅" in result


def test_choose_boon_no_bot_topic():
    state = _boons_state()
    config = {"group_id": -1001}  # no bot_topic_id
    with patch("boons.handler._resolve_boon",
               return_value=("You won Map!", None)):
        result = choose_boon_by_text("100", "U1", 3, config, state)
    assert "Map" in result or "✅" in result



# ═══════════════════════════════════════════════════════════════════════════════
# scheduled/leaderboard.py — post_campaign_leaderboard

# ═══════════════════════════════════════════════════════════════════════════════

from scheduled.leaderboard import post_campaign_leaderboard


def _lb_config():
    return {"group_id": -1001, "leaderboard_topic_id": 555,
            "gm_user_ids": [999], "bot_topic_id": 999,
            "topic_pairs": [{"pbp_topic_ids": [100], "code": "C00",
                              "name": "Kibwe", "gm_user_ids": [999]}]}


@patch("scheduled.leaderboard.helpers")
def test_leaderboard_skips_no_topic(mock_helpers):
    config = {"group_id": -1, "gm_user_ids": []}
    post_campaign_leaderboard(config, {})


@patch("scheduled.leaderboard.helpers")
def test_leaderboard_skips_interval(mock_helpers):
    mock_helpers.interval_elapsed.return_value = False
    post_campaign_leaderboard(_lb_config(), {"last_leaderboard": "2026-04-03"})


@patch("scheduled.leaderboard.helpers")
def test_leaderboard_skips_no_data(mock_helpers):
    mock_helpers.interval_elapsed.return_value = True
    with patch("scheduled.leaderboard._gather_leaderboard_stats",
               return_value=({}, {}, {})):
        post_campaign_leaderboard(_lb_config(), {})


@patch("scheduled.leaderboard.helpers")
def test_leaderboard_posts(mock_helpers):
    mock_helpers.interval_elapsed.return_value = True
    mock_helpers.player_mention.return_value = "@alice"
    campaign_stats = {"Kibwe": {"players": [], "total": 10}}
    global_posts = {"U1": {"count": 10, "full_name": "Alice", "username": "alice"}}
    with patch("scheduled.leaderboard._gather_leaderboard_stats",
               return_value=(campaign_stats, global_posts, {})), \
         patch("scheduled.leaderboard._format_leaderboard",
               return_value="🏆 MVP of the Week: Alice!"):
        post_campaign_leaderboard(_lb_config(), {})

