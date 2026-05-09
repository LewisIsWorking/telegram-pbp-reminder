"""Tests extracted from test_zero_coverage.py — bin 4.

Sections in this file:
  - set_commands.py
  - set_commands.py
  - scheduled/diagnostic_analysis.py
  - scheduled/diagnostic_analysis.py
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

from commands.waiting import build_waiting, build_waiting_all, _age_str


def test_age_str_hours():
    assert _age_str(5) == "5h"

def test_age_str_days():
    assert _age_str(25) == "1d 1h"


@patch("commands.waiting.scan_transcripts")
def test_build_waiting_no_data(mock_scan):
    mock_scan.return_value = {}
    result = build_waiting("U1", "Alice", "100", "Kibwe", {}, {})
    assert "all caught up" in result


@patch("commands.queue_stats.avg_reply_hours", return_value=None)
@patch("commands.waiting.scan_transcripts")
def test_build_waiting_no_match(mock_scan, mock_avg):
    mock_scan.return_value = {
        "100": {"entries": [{"name": "Bob", "time": "2026-03-01 10:00:00",
                              "preview": "hello", "link": ""}]}
    }
    state = {"players": {}}
    result = build_waiting("U1", "Alice", "100", "Kibwe", {}, state)
    assert "No pending" in result


@patch("commands.queue_stats.avg_reply_hours", return_value=48.0)
@patch("commands.waiting.scan_transcripts")
def test_build_waiting_with_match(mock_scan, mock_avg):
    mock_scan.return_value = {
        "100": {"entries": [
            {"name": "Alice", "time": "2026-03-27 10:00:00",
             "preview": "word " * 10, "link": "https://t.me/x"}
        ]}
    }
    state = {"players": {"100:U1": {"first_name": "Alice"}}, "_config_cache": {}}
    result = build_waiting("U1", "Alice", "100", "Kibwe", {}, state)
    assert "Waiting on GM" in result
    assert "t.me" in result


@patch("commands.queue_stats.avg_reply_hours", return_value=12.0)
@patch("commands.waiting.scan_transcripts")
def test_build_waiting_avg_hours(mock_scan, mock_avg):
    mock_scan.return_value = {
        "100": {"entries": [
            {"name": "Alice", "time": "2026-03-27 10:00:00",
             "preview": "hi", "link": ""}
        ]}
    }
    state = {"players": {"100:U1": {"first_name": "Alice"}}, "_config_cache": {}}
    result = build_waiting("U1", "Alice", "100", "Kibwe", {}, state)
    assert "12h" in result


@patch("commands.waiting.scan_transcripts")
def test_build_waiting_all_none(mock_scan):
    mock_scan.return_value = {}
    result = build_waiting_all("U1", "Alice", {"topic_pairs": []}, {})
    assert "all caught up" in result


@patch("commands.waiting.scan_transcripts")
def test_build_waiting_all_with_match(mock_scan):
    mock_scan.return_value = {
        "100": {
            "code": "C00", "campaign": "Riddleport",
            "entries": [
                {"name": "Alice", "time": "2026-03-27 10:00:00",
                 "preview": "word " * 6, "link": ""}
            ]
        }
    }
    config = {"topic_pairs": [{"pbp_topic_ids": [100]}]}
    state = {"players": {"100:U1": {"first_name": "Alice"}}}
    result = build_waiting_all("U1", "Alice", config, state)
    assert "Riddleport" in result



# ═══════════════════════════════════════════════════════════════════════════════
# set_commands.py

# ═══════════════════════════════════════════════════════════════════════════════

from set_commands import _fmt, set_commands, EVERYONE_COMMANDS, GM_COMMANDS


def test_fmt():
    result = _fmt([("help", "Help text")])
    assert result == [{"command": "help", "description": "Help text"}]


def test_everyone_commands_non_empty():
    assert len(EVERYONE_COMMANDS) > 0


def test_gm_commands_non_empty():
    assert len(GM_COMMANDS) > 0


def test_set_commands_success():
    ok = MagicMock()
    ok.json.return_value = {"ok": True}
    with patch("set_commands.requests.post", return_value=ok):
        set_commands("faketoken")


def test_set_commands_failure():
    fail = MagicMock()
    fail.json.return_value = {"ok": False, "description": "err"}
    with patch("set_commands.requests.post", return_value=fail):
        set_commands("faketoken")  # should not raise



# ═══════════════════════════════════════════════════════════════════════════════
# scheduled/diagnostic_analysis.py
