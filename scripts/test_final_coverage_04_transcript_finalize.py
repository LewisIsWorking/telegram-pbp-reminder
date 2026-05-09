"""Coverage tests extracted from test_final_coverage.py — bin 4.

Sections in this file:
  - transcript/finalize.py — update_transcript_index
  - transcript/finalize.py — update_transcript_index
  - commands/player.py — build_mystats_all
  - commands/player.py — build_mystats_all
  - scheduled/reports.py — post_roster_summary with active player
  - scheduled/reports.py — post_roster_summary with active player
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


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
    (logs / "2026-03.md").write_text("**Alice** (2026-03-01):\nHi\n")
    (logs / "2026-04.md").write_text("**Bob** (2026-04-01):\nHey\n")
    with patch("transcript.finalize._LOGS_DIR", tmp_path):
        update_transcript_index(config)
    assert (tmp_path / "README.md").exists()
    content = (tmp_path / "README.md").read_text()
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
