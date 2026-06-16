"""Tests extracted from test_final_coverage.py — bin 5.

Sections in this file:
  - transcript/finalize.py — update_transcript_index
  - commands/player.py — build_mystats_all
  - commands/player.py — build_mystats_all
  - scheduled/reports.py — post_roster_summary with active player
  - scheduled/reports.py — post_roster_summary with active player
  - helpers_pkg/time_utils.py — parse_away_date
  - helpers_pkg/time_utils.py — parse_away_date
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
# transcript/finalize.py — update_transcript_index

# ═══════════════════════════════════════════════════════════════════════════════

from transcript.finalize import update_transcript_index


def test_update_transcript_index_no_dir(tmp_path):
    config = {"topic_pairs": [{"name": "Kibwe"}]}
    with patch("transcript.finalize._LOGS_DIR", tmp_path / "missing"):
        update_transcript_index(config)  # should not raise


def test_update_transcript_index_with_logs(tmp_path):
    config = {"topic_pairs": [{"name": "Kibwe"}]}
    logs = tmp_path / "Kibwe"
    logs.mkdir()
    (logs / "2026-03.md").write_text("**Alice** (2026-03-01):\nHi\n", encoding="utf-8")
    (logs / "2026-04.md").write_text("**Bob** (2026-04-01):\nHey\n", encoding="utf-8")
    with patch("transcript.finalize._LOGS_DIR", tmp_path):
        update_transcript_index(config)
    assert (tmp_path / "README.md").exists()
    content = (tmp_path / "README.md").read_text(encoding="utf-8")
    assert "Kibwe" in content


def test_update_transcript_index_empty_dir(tmp_path):
    config = {"topic_pairs": [{"name": "Kibwe"}]}
    (tmp_path / "Kibwe").mkdir()  # empty dir
    with patch("transcript.finalize._LOGS_DIR", tmp_path):
        update_transcript_index(config)



# ═══════════════════════════════════════════════════════════════════════════════
# commands/player.py — build_mystats_all

# ═══════════════════════════════════════════════════════════════════════════════

from commands.player import build_mystats_all


@patch("commands.player.helpers")
def test_mystats_all_no_posts(mock_helpers):
    mock_helpers.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
    mock_helpers.gm_ids_for_campaign.return_value = {"999"}
    mock_helpers.get_topic_timestamps.return_value = {}
    mock_helpers.get_label.return_value = "C00: Kibwe"
    result = build_mystats_all("U1", "Alice", {}, {"message_counts": {}})
    assert "No posts" in result


@patch("commands.player.helpers")
def test_mystats_all_with_posts(mock_helpers):
    now = datetime.now(timezone.utc)
    ts = [(now - timedelta(hours=h*3)).isoformat() for h in range(5)]
    mock_helpers.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
    mock_helpers.gm_ids_for_campaign.return_value = {"999"}
    mock_helpers.get_topic_timestamps.return_value = {"U1": ts}
    mock_helpers.get_label.return_value = "C00: Kibwe"
    mock_helpers.calc_streak.return_value = 3
    state = {"message_counts": {"100": {"U1": 42}}}
    with patch("commands.player.timestamps_in_window", return_value=ts[:3]), \
         patch("commands.player.deduplicate_posts", return_value=ts[:3]):
        result = build_mystats_all("U1", "Alice", {}, state)
    assert "Alice" in result
    assert "42" in result



# ═══════════════════════════════════════════════════════════════════════════════
# scheduled/reports.py — post_roster_summary with active player

# ═══════════════════════════════════════════════════════════════════════════════

from scheduled.reports import post_roster_summary


@patch("scheduled.reports.helpers")
def test_roster_posts_active_player(mock_helpers):
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    ts = [(now - timedelta(hours=h)).isoformat() for h in range(5)]
    mock_helpers.build_topic_maps.return_value = MagicMock(
        to_chat={"100": 21514}, to_name={"100": "Kibwe"}
    )
    mock_helpers.players_by_campaign.return_value = {"100": [
        {"user_id": "U1", "first_name": "Alice", "username": "alice"}
    ]}
    mock_helpers.feature_enabled.return_value = True
    mock_helpers.interval_elapsed.return_value = True
    mock_helpers.gm_ids_for_campaign.return_value = {"999"}
    mock_helpers.get_label.return_value = "C00: Kibwe"
    mock_helpers.get_topic_timestamps.return_value = {"U1": ts}
    mock_helpers.get_characters.return_value = {"U1": "Amara"}
    mock_helpers.player_full_name.return_value = "Alice"
    mock_helpers.REQUIRED_PLAYERS = 4
    config = {"group_id": -1001, "bot_topic_id": 999, "gm_user_ids": [999],
              "topic_pairs": [{"pbp_topic_ids": [100], "code": "C00",
                               "name": "Kibwe", "gm_user_ids": [999],
                               "chat_topic_id": 21514}]}
    state = {"last_roster": {}, "message_counts": {"100": {"U1": 50}},
             "player_registry": {}}
    with patch("commands.campaign.roster_user_stats", return_value={}), \
         patch("commands.campaign.roster_block", return_value="Alice block"):
        post_roster_summary(config, state, now=now)



# ═══════════════════════════════════════════════════════════════════════════════
# helpers_pkg/time_utils.py — parse_away_date
