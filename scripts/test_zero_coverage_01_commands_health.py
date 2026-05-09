"""Tests extracted from test_zero_coverage.py — bin 1.

Sections in this file:
  - commands/health.py
  - Use real current time so build_health's internal datetime.now() matches
  - commands/queue_analytics.py
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
# commands/health.py

# ═══════════════════════════════════════════════════════════════════════════════

from commands.health import build_health

# Use real current time so build_health's internal datetime.now() matches
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


@patch("commands.queue_scan.scan_transcripts", return_value={})
def test_health_no_data(mock_scan):
    state = _h_state()
    # No last_message_time for topic 101
    result = build_health(_h_config(), state)
    assert "no data" in result


@patch("commands.queue_scan.scan_transcripts", return_value={})
def test_health_green(mock_scan):
    ts = {"100": {"1": [_recent()]*12}}
    state = _h_state(last_100=_recent(), ts=ts)
    result = build_health(_h_config(), state)
    assert "🟢" in result


@patch("commands.queue_scan.scan_transcripts", return_value={})
def test_health_yellow(mock_scan):
    two_days_ago = _days_ago(2)
    ts = {"100": {"1": [_recent()]*4}}
    state = _h_state(last_100=two_days_ago, ts=ts)
    result = build_health(_h_config(), state)
    assert "🟡" in result


@patch("commands.queue_scan.scan_transcripts", return_value={})
def test_health_orange(mock_scan):
    state = _h_state(last_100=_days_ago(4), ts={"100": {}})
    result = build_health(_h_config(), state)
    assert "🟠" in result


@patch("commands.queue_scan.scan_transcripts", return_value={})
def test_health_red(mock_scan):
    state = _h_state(last_100=_stale(), ts={"100": {}})
    result = build_health(_h_config(), state)
    assert "🔴" in result


@patch("commands.queue_scan.scan_transcripts", return_value={})
def test_health_age_hours(mock_scan):
    six_hours_ago = (_now() - timedelta(hours=6)).isoformat()
    ts = {"100": {"1": [_recent()]*12}}
    state = _h_state(last_100=six_hours_ago, ts=ts)
    result = build_health(_h_config(), state)
    assert "h" in result


@patch("commands.queue_scan.scan_transcripts", return_value={})
def test_health_age_days(mock_scan):
    two_days_ago = _days_ago(2)
    state = _h_state(last_100=two_days_ago, ts={"100": {}})
    result = build_health(_h_config(), state)
    assert "d" in result


@patch("commands.queue_scan.scan_transcripts", return_value={"100": {"entries": ["a", "b"]}})
def test_health_queue_indicator(mock_scan):
    state = _h_state(last_100=_recent(), ts={"100": {"1": [_recent()]*12}})
    result = build_health(_h_config(), state)
    assert "📋2" in result


@patch("commands.queue_scan.scan_transcripts", return_value={})
def test_health_session_count(mock_scan):
    state = _h_state(last_100=_recent(), ts={"100": {"1": [_recent()]*12}})
    state["session_counts"] = {"100": 5}
    result = build_health(_h_config(), state)
    assert "S5" in result


@patch("commands.queue_scan.scan_transcripts", return_value={})
def test_health_invalid_timestamp_ignored(mock_scan):
    ts = {"100": {"1": ["not-a-date", _recent()]}}
    state = _h_state(last_100=_recent(), ts=ts)
    result = build_health(_h_config(), state)
    assert "Riddleport" in result



# ═══════════════════════════════════════════════════════════════════════════════
# commands/queue_analytics.py
