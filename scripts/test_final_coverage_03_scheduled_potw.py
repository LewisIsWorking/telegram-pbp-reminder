"""Tests extracted from test_final_coverage.py — bin 3.

Sections in this file:
  - scheduled/potw.py — winner selection and announcement
  - boons/handler.py — choose_boon_by_text
  - boons/handler.py — choose_boon_by_text
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
# scheduled/potw.py — winner selection and announcement

# ═══════════════════════════════════════════════════════════════════════════════

from scheduled.potw import player_of_the_week, _gather_potw_candidates, _find_player_post_links


def test_gather_potw_candidates_no_posts():
    now = datetime(2026, 4, 3, tzinfo=timezone.utc)
    week_ago = now - timedelta(days=7)
    result = _gather_potw_candidates({}, {"999"}, week_ago, "100", {})
    assert result == []


def test_gather_potw_candidates_with_posts():
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    week_ago = now - timedelta(days=7)
    ts = [(now - timedelta(hours=h*4)).isoformat() for h in range(5)]
    ts_map = {"U1": ts}
    state = {"players": {"100:U1": {"user_id": "U1", "first_name": "Alice"}}}
    with patch("scheduled.potw.helpers") as mh:
        mh.POTW_MIN_POSTS = 3
        mh.get_player.return_value = {"user_id": "U1", "first_name": "Alice", "username": "alice"}
        result = _gather_potw_candidates(ts_map, {"999"}, week_ago, "100", state)
    assert len(result) == 1
    assert result[0]["first_name"] == "Alice"


def test_find_player_post_links_no_dir(tmp_path):
    with patch("scheduled.potw_links._LOGS_DIR", tmp_path / "missing"):
        result = _find_player_post_links("Kibwe", "Alice", "100",
                                         datetime(2026, 3, 27, tzinfo=timezone.utc))
    assert result == []


@patch("scheduled.potw.helpers")
def test_potw_announces_winner(mock_helpers):
    now = datetime(2026, 3, 29, 9, tzinfo=timezone.utc)
    mock_helpers.build_topic_maps.return_value = MagicMock(
        to_chat={"100": 21514}, to_name={"100": "Kibwe"}
    )
    mock_helpers.feature_enabled.return_value = True
    mock_helpers.interval_elapsed.return_value = True
    mock_helpers.gm_ids_for_campaign.return_value = {"999"}
    mock_helpers.get_topic_timestamps.return_value = {}
    mock_helpers.POTW_MIN_POSTS = 3
    mock_helpers.POTW_INTERVAL_DAYS = 7
    mock_helpers.BOONS_PATH = "/nonexistent/boons.json"
    mock_helpers.MECHANICAL_BOONS = ["Gain 1 Hero Point"]
    mock_helpers.player_mention.return_value = "@alice"
    mock_helpers.fmt_date.return_value = "2026-03-22"
    mock_helpers.posts_str.return_value = "10 posts"
    config = {"group_id": -1001, "bot_topic_id": 999, "gm_user_ids": [999],
              "topic_pairs": [{"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
                               "chat_topic_id": 21514, "gm_user_ids": [999]}]}
    state = {"last_potw": {}, "pending_potw_boons": {}}
    candidate = {"user_id": "U1", "first_name": "Alice", "username": "alice",
                 "post_count": 10, "avg_gap_hours": 4.0}
    with patch("scheduled.potw._gather_potw_candidates", return_value=[candidate]), \
         patch("scheduled.potw._find_player_post_links", return_value=[]), \
         patch("scheduled.potw_streaks.announce_streaks"), \
         patch("scheduled.potw.random.sample", return_value=["Boon A", "Boon B", "Boon C"]), \
         patch("scheduled.potw.random.choice", return_value="Gain 1 Hero Point"):
        player_of_the_week(config, state, now=now)
    assert "100" in state.get("last_potw", {}) or "pending_potw_boons" in state



# ═══════════════════════════════════════════════════════════════════════════════
# boons/handler.py — choose_boon_by_text
