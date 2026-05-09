"""Tests extracted from test_commands_coverage.py — bin 5.

Sections in this file:
  - scheduled/reports.py  — test post_roster_summary guard conditions
"""
"""
Coverage tests for:
  commands/queue_io.py
  commands/player_registry.py
  scheduled/poll_result.py
  scheduled/diagnostic.py
  scheduled/reports.py  (partial — tg-calling functions mocked)
"""
import sys, os, json, pytest, tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

@pytest.fixture
def tmp_queues(tmp_path, monkeypatch):
    """Redirect queue_io file operations to a temp directory."""
    monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path)
    return tmp_path

def _pr_config():
    return {
        "group_id": -1001,
        "topic_pairs": [{
            "pbp_topic_ids": [100], "code": "C01",
            "name": "DF", "hybrid_live": True,
            "chat_topic_id": 21514,
            "poll_options": ["Friday", "Saturday", "Either", "Both", "Can't make it"],
            "allows_multiple_answers": False,
        }]
    }

def _rpt_config():
    return {
        "group_id": -1001,
        "bot_topic_id": 999,
        "gm_user_ids": [999],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C00", "name": "R",
             "gm_user_ids": [999], "chat_topic_id": 21514}
        ]
    }

# ═══════════════════════════════════════════════════════════════════════════════
# scheduled/reports.py  — test post_roster_summary guard conditions
# ═══════════════════════════════════════════════════════════════════════════════

from scheduled.reports import post_roster_summary


def _rpt_config():
    return {
        "group_id": -1001,
        "bot_topic_id": 999,
        "gm_user_ids": [999],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C00", "name": "R",
             "gm_user_ids": [999], "chat_topic_id": 21514}
        ]
    }


@patch("scheduled.reports.helpers")
def test_roster_summary_skips_no_feature(mock_helpers):
    mock_helpers.build_topic_maps.return_value = MagicMock(
        to_chat={"100": 21514}, to_name={"100": "R"}
    )
    mock_helpers.players_by_campaign.return_value = {}
    mock_helpers.feature_enabled.return_value = False
    mock_helpers.interval_elapsed.return_value = True
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    state = {"last_roster": {}}
    post_roster_summary(_rpt_config(), state, now=now)


@patch("scheduled.reports.helpers")
def test_roster_summary_skips_interval_not_elapsed(mock_helpers):
    mock_helpers.build_topic_maps.return_value = MagicMock(
        to_chat={"100": 21514}, to_name={"100": "R"}
    )
    mock_helpers.players_by_campaign.return_value = {}
    mock_helpers.feature_enabled.return_value = True
    mock_helpers.interval_elapsed.return_value = False
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    state = {"last_roster": {"100": "2026-04-03"}}
    post_roster_summary(_rpt_config(), state, now=now)


@patch("scheduled.reports.helpers")
def test_roster_summary_skips_no_players(mock_helpers):
    mock_helpers.build_topic_maps.return_value = MagicMock(
        to_chat={"100": 21514}, to_name={"100": "R"}
    )
    mock_helpers.players_by_campaign.return_value = {"100": []}
    mock_helpers.feature_enabled.return_value = True
    mock_helpers.interval_elapsed.return_value = True
    mock_helpers.gm_ids_for_campaign.return_value = {999}
    mock_helpers.get_label.return_value = "C00: R"
    mock_helpers.get_characters.return_value = {}
    mock_helpers.get_topic_timestamps.return_value = {}
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    state = {"last_roster": {}, "message_counts": {}}
    post_roster_summary(_rpt_config(), state, now=now)
