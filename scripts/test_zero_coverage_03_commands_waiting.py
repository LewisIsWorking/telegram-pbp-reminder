"""Tests extracted from test_zero_coverage.py — bin 3.

Sections in this file:
  - commands/waiting.py
  - commands/waiting.py
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

from commands.queue_stats import (
    record_reply, get_today_clears, get_week_clears,
    avg_reply_hours, build_queue_stats
)


def test_record_reply_adds_to_history():
    state = {}
    now = datetime(2026, 3, 27, tzinfo=timezone.utc)
    record_reply("100", state, "preview", "Alice", now)
    assert len(state["queue_history"]["100"]) == 1
    assert len(state["queue_archive"]) == 1


def test_record_reply_caps_history():
    state = {"queue_history": {"100": ["x"] * 500}}
    record_reply("100", state, "", "", datetime.now(timezone.utc))
    assert len(state["queue_history"]["100"]) == 500


def test_record_reply_caps_archive():
    state = {"queue_archive": [{"pid": "x"}] * 200}
    record_reply("100", state, "", "", datetime.now(timezone.utc))
    assert len(state["queue_archive"]) == 200


def test_get_today_clears():
    now = datetime(2026, 3, 27, 12, tzinfo=timezone.utc)
    state = {"queue_history": {"100": [
        "2026-03-27T10:00:00", "2026-03-26T10:00:00"
    ]}}
    assert get_today_clears(state, now) == 1


def test_get_week_clears():
    now = datetime(2026, 3, 27, 12, tzinfo=timezone.utc)
    state = {"queue_history": {"100": [
        "2026-03-25T10:00:00",  # within 7 days
        "2026-03-15T10:00:00",  # outside
    ]}}
    assert get_week_clears(state, now) == 1


def test_avg_reply_hours_not_enough_data():
    state = {"post_timestamps": {}}
    assert avg_reply_hours("100", state) is None


@patch("commands.queue_stats.helpers")
def test_avg_reply_hours_calculates(mock_helpers):
    now = datetime(2026, 3, 27, 12, tzinfo=timezone.utc)
    ts = [(now - timedelta(hours=h)).isoformat() for h in [10, 6, 2]]
    mock_helpers.get_topic_timestamps.return_value = {"999": ts}
    config = {"topic_pairs": [
        {"pbp_topic_ids": [100], "gm_user_ids": [999]}
    ], "gm_user_ids": [999]}
    state = {"_config_cache": config}
    result = avg_reply_hours("100", state)
    assert result is not None
    assert result > 0


@patch("commands.queue_stats.helpers")
def test_avg_reply_hours_large_gaps_excluded(mock_helpers):
    now = datetime(2026, 3, 27, 12, tzinfo=timezone.utc)
    ts = [(now - timedelta(days=d)).isoformat() for d in [30, 20, 10]]
    mock_helpers.get_topic_timestamps.return_value = {"999": ts}
    config = {"topic_pairs": [
        {"pbp_topic_ids": [100], "gm_user_ids": [999]}
    ], "gm_user_ids": [999]}
    state = {"_config_cache": config}
    result = avg_reply_hours("100", state)
    assert result is None


@patch("commands.queue_scan.scan_transcripts", return_value={})
@patch("commands.queue_analytics.helpers")
@patch("commands.queue_stats.helpers")
def test_build_queue_stats_runs(mock_h, mock_qa_h, mock_scan):
    mock_h.iter_campaigns.return_value = []
    mock_qa_h.iter_campaigns.return_value = []
    state = {"queue_history": {}, "queue_archive": []}
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": []}
    result = build_queue_stats(config, state)
    assert "GM Queue Stats" in result



# ═══════════════════════════════════════════════════════════════════════════════
# commands/waiting.py
