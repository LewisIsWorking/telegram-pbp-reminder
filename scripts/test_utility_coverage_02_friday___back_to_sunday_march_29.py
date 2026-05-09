"""Tests extracted from test_utility_coverage.py — bin 2.

Sections in this file:
  - Friday → back to Sunday March 29
  - scheduled/state_backup.py
"""
"""
Coverage tests for:
  migrate_gist_to_files.py
  promote_poll_voters.py
  scheduled/session_poll_build.py
  scheduled/state_backup.py
  helpers_pkg/groups.py
"""
import sys, os, json, pytest, tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

def _g_config():
    return {
        "group_id": -1001,
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C00", "name": "R"},
            {"pbp_topic_ids": [101], "code": "C01", "name": "D",
             "group_id": -2002, "linked_polls": ["C11"]},
        ]
    }

def _now():
    return datetime(2026, 4, 3, 12, 0, tzinfo=timezone.utc)  # Friday

# ═══════════════════════════════════════════════════════════════════════════════

from scheduled.session_poll_build import (
    sunday_week_key, is_poll_day, poll_options_for,
    _next_weekday_date, build_history_str, build_ping_message,
    build_all_voted_message, votes_to_option_label, option_tally
)


def _now():
    return datetime(2026, 4, 3, 12, 0, tzinfo=timezone.utc)  # Friday


def test_sunday_week_key_friday():
    # Friday → back to Sunday March 29
    result = sunday_week_key(_now())
    assert result.startswith("sun")
    assert "2026-03-29" in result


def test_sunday_week_key_sunday():
    sunday = datetime(2026, 3, 29, 12, tzinfo=timezone.utc)
    result = sunday_week_key(sunday)
    assert "2026-03-29" in result


def test_is_poll_day_always_true():
    assert is_poll_day(_now(), {}) is True


def test_next_weekday_date_friday():
    # From Friday, next Friday = same day (0 days away)
    result = _next_weekday_date(_now(), 4)
    assert result == "2026-04-03"


def test_next_weekday_date_saturday():
    result = _next_weekday_date(_now(), 5)
    assert result == "2026-04-04"


def test_poll_options_for_static_with_dates():
    pair = {"poll_options": ["Friday", "Saturday", "Both", "Can't make it"]}
    opts = poll_options_for(pair, _now())
    assert opts[0] == "2026-04-03 Friday"
    assert opts[1] == "2026-04-04 Saturday"
    assert opts[2] == "Both"
    assert opts[3] == "Can't make it"


def test_poll_options_for_dynamic():
    opts = poll_options_for({}, _now())
    assert len(opts) == 3
    assert "Friday" in opts[0]
    assert "Saturday" in opts[1]
    assert "Can't make either" in opts[2]


def test_build_history_str_no_wins():
    assert build_history_str({}, ["A", "B"]) == ""


def test_build_history_str_with_wins():
    history = {"wins": {"0": 3, "1": 1}}
    result = build_history_str(history, ["Friday", "Saturday"])
    assert "Friday" in result
    assert "3/4" in result


def test_build_ping_message():
    pair = {"code": "C01"}
    result = build_ping_message(pair, ["@Alice", "@Bob"], 3, 5, 14,
                                "https://t.me/x")
    assert "C01" in result
    assert "3/5" in result
    assert "@Alice" in result
    assert "t.me" in result


def test_build_ping_message_no_link():
    pair = {"code": "C01"}
    result = build_ping_message(pair, ["@Alice"], 1, 5, 14, "")
    assert "🔗" not in result


def test_build_all_voted_message():
    result = build_all_voted_message("C01", 6, 14)
    assert "All 6" in result
    assert "C01" in result


def test_votes_to_option_label():
    pair = {"poll_options": ["Friday", "Saturday", "Both"]}
    result = votes_to_option_label([0, 2], pair, _now())
    assert "Friday" in result or "2026" in result


def test_votes_to_option_label_out_of_range():
    pair = {"poll_options": ["A"]}
    result = votes_to_option_label([99], pair, _now())
    assert result == "?"


def test_option_tally():
    votes = {"0": ["U1", "U2"], "2": ["U3"]}
    opts = ["Friday", "Saturday", "Both"]
    result = option_tally(votes, opts)
    assert any("Friday" in r for r in result)
    assert any("Both" in r for r in result)
    assert not any("Saturday" in r for r in result)



# ═══════════════════════════════════════════════════════════════════════════════
# scheduled/state_backup.py
