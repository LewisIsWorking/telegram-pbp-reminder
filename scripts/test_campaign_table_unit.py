"""
Unit tests for campaign_table.py helper functions.

Integration tests (full HTML output) live in test_campaign_table.py.
"""

import sys
import os
import pytest
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__)))

from scheduled.campaign_table import (
    _calc_age,
    _truncate,
    _count_week_posts,
)
from commands.queue_format import entry_age_icon

# ── Shared constants ───────────────────────────────────────────────────────────

NOW      = datetime(2026, 3, 27, 12, 0, 0, tzinfo=timezone.utc)
WEEK_AGO = NOW - timedelta(days=7)
RECENT_TS = (NOW - timedelta(hours=2)).isoformat()
STALE_TS  = (NOW - timedelta(days=8)).isoformat()  # outside 7-day window

# ── Health icon ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("hours_val, expected", [
    (0.5,   "🆕"),   # < 1h
    (12.0,  "🌳"),   # 12-24h
    (24.0,  "🟢"),   # day 1
    (60.0,  "🟩"),   # day 2-3
    (72.0,  "🟡"),   # day 3-4
    (120.0, "🟠"),   # day 5-6
    (168.0, "🔴"),   # day 7-8
    (240.0, "🟪"),   # day 10-11
    (408.0, "💀"),   # day 17+
    (600.0, "☠️"),   # day 25+
])
def test_health_icon(hours_val, expected):
    assert entry_age_icon(hours_val) == expected


# ── Age calculation ────────────────────────────────────────────────────────────

def test_calc_age_hours():
    last = (NOW - timedelta(hours=5)).isoformat()
    age, hours_val = _calc_age(last, NOW)
    assert age == "5h"
    assert hours_val == pytest.approx(5.0)


def test_calc_age_days():
    last = (NOW - timedelta(hours=50)).isoformat()
    age, hours_val = _calc_age(last, NOW)
    assert age == "2d"
    assert hours_val == pytest.approx(50.0)


def test_calc_age_missing():
    age, hours_val = _calc_age(None, NOW)
    assert age == "—"
    assert hours_val == pytest.approx(99.0 * 24)


def test_calc_age_boundary_exactly_24h():
    last = (NOW - timedelta(hours=24)).isoformat()
    age, hours_val = _calc_age(last, NOW)
    assert age == "1d"
    assert hours_val == pytest.approx(24.0)


# ── Week post count ────────────────────────────────────────────────────────────

def test_count_week_posts_recent_only():
    topic_ts = {
        "111": [RECENT_TS, STALE_TS],
        "222": [RECENT_TS],
    }
    assert _count_week_posts(topic_ts, WEEK_AGO) == 2


def test_count_week_posts_all_stale():
    topic_ts = {"111": [STALE_TS], "222": [STALE_TS]}
    assert _count_week_posts(topic_ts, WEEK_AGO) == 0


def test_count_week_posts_bad_ts():
    topic_ts = {"111": ["not-a-date", RECENT_TS]}
    assert _count_week_posts(topic_ts, WEEK_AGO) == 1


def test_count_week_posts_empty():
    assert _count_week_posts({}, WEEK_AGO) == 0


def test_count_week_posts_multiple_users():
    topic_ts = {
        "111": [RECENT_TS, RECENT_TS],
        "222": [RECENT_TS],
        "333": [STALE_TS],
    }
    assert _count_week_posts(topic_ts, WEEK_AGO) == 3


# ── Truncation ─────────────────────────────────────────────────────────────────

def test_truncate_short():
    assert _truncate("Short", 18) == "Short"


def test_truncate_exact():
    assert _truncate("A" * 18, 18) == "A" * 18


def test_truncate_long():
    result = _truncate("A" * 20, 18)
    assert len(result) == 18
    assert result.endswith("…")


def test_truncate_one_over():
    result = _truncate("A" * 19, 18)
    assert len(result) == 18
    assert result.endswith("…")


def test_truncate_empty():
    assert _truncate("", 18) == ""
