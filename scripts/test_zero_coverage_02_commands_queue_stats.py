"""Tests extracted from test_zero_coverage.py — bin 2.

Sections in this file:
  - Entry with no time still produces output (uses epoch as fallback)
  - commands/queue_stats.py
"""
"""
Coverage tests for previously-0% files:
  commands/health.py
  commands/waiting.py
  commands/queue_analytics.py
  commands/queue_stats.py
  set_commands.py
  scheduled/diagnostic_analysis.py
"""
import sys, os, pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

def _now():
    return datetime.now(timezone.utc)

def _recent():
    return (_now() - timedelta(hours=2)).isoformat()

def _stale():
    return (_now() - timedelta(days=8)).isoformat()

def _days_ago(n):
    return (_now() - timedelta(days=n, hours=1)).isoformat()

def _h_config():
    return {
        "group_id": -1001, "gm_user_ids": [999], "bot_topic_id": 1,
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C00", "name": "Riddleport",
             "gm_user_ids": [999]},
            {"pbp_topic_ids": [101], "code": "C01", "name": "Dungeon",
             "gm_user_ids": [999]},
        ]
    }

def _h_state(last_100=None, last_101=None, ts=None):
    return {
        "topics": {
            "100": {"last_message_time": last_100} if last_100 else {},
            "101": {"last_message_time": last_101} if last_101 else {},
        },
        "post_timestamps": ts or {"100": {"1": [_recent()]*12}, "101": {}},
        "players": {
            "100:1": {"pbp_topic_id": "100", "user_id": "1"},
        },
        "session_counts": {},
    }

def _pm_config():
    return {
        "group_id": -1001, "gm_user_ids": [999],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C00", "name": "R",
             "gm_user_ids": [999]}
        ]
    }

# ═══════════════════════════════════════════════════════════════════════════════

from commands.queue_analytics import peak_hours, age_heatmap, player_momentum


def test_peak_hours_no_data():
    assert peak_hours({}) == "No data yet"


def test_peak_hours_with_data():
    state = {"activity_hours": {"100": {"U1": {"9": 10, "10": 5, "14": 8}}}}
    result = peak_hours(state)
    assert "09:00" in result


def test_age_heatmap_empty():
    assert age_heatmap({}) == ""


def test_age_heatmap_with_entries():
    two_days_ago = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    scanned = {"100": {
        "campaign": "Kibwe", "code": "C06",
        "entries": [{"time": two_days_ago}]
    }}
    result = age_heatmap(scanned)
    assert "C06" in result


def test_age_heatmap_skips_missing_time():
    # Entry with no time still produces output (uses epoch as fallback)
    scanned = {"100": {"campaign": "X", "code": "C00", "entries": [{"time": ""}]}}
    result = age_heatmap(scanned)
    # Should not raise; result may or may not contain C00 depending on strptime
    assert isinstance(result, str)


def _pm_config():
    return {
        "group_id": -1001, "gm_user_ids": [999],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C00", "name": "R",
             "gm_user_ids": [999]}
        ]
    }


@patch("commands.queue_analytics.helpers")
def test_player_momentum_no_data(mock_helpers):
    mock_helpers.iter_campaigns.return_value = [("100", "C00", "R", {})]
    mock_helpers.is_excluded.return_value = False
    mock_helpers.gm_ids_for_campaign.return_value = {999}
    mock_helpers.get_topic_timestamps.return_value = {}
    result = player_momentum({}, _pm_config())
    assert result == []


@patch("commands.queue_analytics.helpers")
def test_player_momentum_excluded(mock_helpers):
    mock_helpers.iter_campaigns.return_value = [("100", "C00", "R", {})]
    mock_helpers.is_excluded.return_value = True
    result = player_momentum({}, _pm_config())
    assert result == []


@patch("commands.queue_analytics.helpers")
def test_player_momentum_with_responses(mock_helpers):
    now = datetime.now(timezone.utc)
    gm_ts = (now - timedelta(hours=5)).isoformat()
    player_ts = (now - timedelta(hours=3)).isoformat()
    mock_helpers.iter_campaigns.return_value = [("100", "C00", "R", {})]
    mock_helpers.is_excluded.return_value = False
    mock_helpers.gm_ids_for_campaign.return_value = {"999"}
    mock_helpers.get_topic_timestamps.return_value = {
        "999": [gm_ts], "U1": [player_ts]
    }
    mock_helpers.get_player.return_value = {"first_name": "Alice"}
    result = player_momentum({}, _pm_config())
    assert len(result) == 1
    assert "Alice" in result[0]


@patch("commands.queue_analytics.helpers")
def test_player_momentum_large_gap_ignored(mock_helpers):
    now = datetime.now(timezone.utc)
    gm_ts = (now - timedelta(days=10)).isoformat()
    player_ts = (now - timedelta(hours=1)).isoformat()
    mock_helpers.iter_campaigns.return_value = [("100", "C00", "R", {})]
    mock_helpers.is_excluded.return_value = False
    mock_helpers.gm_ids_for_campaign.return_value = {"999"}
    mock_helpers.get_topic_timestamps.return_value = {
        "999": [gm_ts], "U1": [player_ts]
    }
    result = player_momentum({}, _pm_config())
    assert result == []



# ═══════════════════════════════════════════════════════════════════════════════
# commands/queue_stats.py
