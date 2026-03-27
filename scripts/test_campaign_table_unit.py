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
    _health_icon,
    _truncate,
    _count_week_posts,
)

# ── Shared constants ───────────────────────────────────────────────────────────

NOW      = datetime(2026, 3, 27, 12, 0, 0, tzinfo=timezone.utc)
WEEK_AGO = NOW - timedelta(days=7)
RECENT_TS = (NOW - timedelta(hours=2)).isoformat()
STALE_TS  = (NOW - timedelta(days=8)).isoformat()  # outside 7-day window

# ── Health icon ────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("days_val, expected", [
    (0.5,  "🟢"),
    (1.0,  "🟡"),
    (2.5,  "🟡"),
    (3.0,  "🟠"),
    (4.9,  "🟠"),
    (5.0,  "🔴"),
    (10.0, "🔴"),
])
def test_health_icon(days_val, expected):
    assert _health_icon(days_val) == expected


# ── Age calculation ────────────────────────────────────────────────────────────

def test_calc_age_hours():
    last = (NOW - timedelta(hours=5)).isoformat()
    age, days_val = _calc_age(last, NOW)
    assert age == "5h"
    assert days_val < 1


def test_calc_age_days():
    last = (NOW - timedelta(hours=50)).isoformat()
    age, days_val = _calc_age(last, NOW)
    assert age == "2d"
    assert days_val == pytest.approx(50 / 24)


def test_calc_age_missing():
    age, days_val = _calc_age(None, NOW)
    assert age == "—"
    assert days_val == 99.0


def test_calc_age_boundary_exactly_24h():
    last = (NOW - timedelta(hours=24)).isoformat()
    age, days_val = _calc_age(last, NOW)
    assert age == "1d"
    assert days_val == pytest.approx(1.0)


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
