"""test_potw_streaks.py — bin 1.

  - _last_iso_week
  - _consecutive_weeks
  - compute_campaign_streak
"""
"""
Full coverage tests for scheduled/potw_streaks.py.

Covers: _last_iso_week, _consecutive_weeks, compute_campaign_streak,
compute_community_streak, streak_announcement, announce_streaks.
"""

import sys
import os
import pytest
from unittest.mock import patch, call

sys.path.insert(0, os.path.dirname(__file__))

from scheduled.potw_streaks import (
    compute_campaign_streak,
    compute_community_streak,
    streak_announcement,
    announce_streaks,
    _consecutive_weeks,
    _last_iso_week,
    CAMPAIGN_MILESTONES,
    COMMUNITY_MILESTONES,
)


# ── _last_iso_week ─────────────────────────────────────────────────────────────


def _r(year, week):
    return {"year": year, "week": f"W{week}"}

def _make_winner():
    return {"user_id": "U1", "first_name": "Alice", "username": "alice"}

def _make_config():
    return {"group_id": -1001, "bot_topic_id": 999}

def _make_state(history=None):
    return {"potw_history": history or []}

# ── _last_iso_week ─────────────────────────────────────────────────────────────

def test_last_iso_week_2020():
    # 2020 has 53 ISO weeks
    assert _last_iso_week(2020) == 53

def test_last_iso_week_2021():
    # 2021 has 52 ISO weeks
    assert _last_iso_week(2021) == 52

def test_last_iso_week_2026():
    assert _last_iso_week(2026) == 53



# ── _consecutive_weeks ────────────────────────────────────────────────────────

def _r(year, week):
    return {"year": year, "week": f"W{week}"}

def test_consecutive_same_year():
    assert _consecutive_weeks(_r(2026, 5), _r(2026, 6)) is True

def test_not_consecutive_same_year():
    assert _consecutive_weeks(_r(2026, 5), _r(2026, 7)) is False

def test_consecutive_year_boundary():
    # W52 of 2021 -> W1 of 2022
    assert _consecutive_weeks(_r(2021, 52), _r(2022, 1)) is True

def test_not_consecutive_year_boundary():
    assert _consecutive_weeks(_r(2021, 51), _r(2022, 1)) is False

def test_consecutive_year_boundary_53_weeks():
    # 2020 has 53 weeks; W53 -> W1 of 2021
    assert _consecutive_weeks(_r(2020, 53), _r(2021, 1)) is True

def test_consecutive_bad_data_returns_false():
    assert _consecutive_weeks({"year": None, "week": "W1"}, _r(2026, 2)) is False

def test_consecutive_missing_week_returns_false():
    assert _consecutive_weeks({"year": 2026}, {"year": 2026, "week": "W2"}) is False



# ── compute_campaign_streak ───────────────────────────────────────────────────

def test_campaign_streak_empty_history():
    assert compute_campaign_streak([], "100", "U1") == 0

def test_campaign_streak_no_match():
    history = [{"campaign_pid": "200", "user_id": "U1", "year": 2026, "week": "W5"}]
    assert compute_campaign_streak(history, "100", "U1") == 0

def test_campaign_streak_single_win():
    history = [{"campaign_pid": "100", "user_id": "U1", "year": 2026, "week": "W5"}]
    assert compute_campaign_streak(history, "100", "U1") == 1

def test_campaign_streak_two_consecutive():
    history = [
        {"campaign_pid": "100", "user_id": "U1", "year": 2026, "week": "W5"},
        {"campaign_pid": "100", "user_id": "U1", "year": 2026, "week": "W6"},
    ]
    assert compute_campaign_streak(history, "100", "U1") == 2

def test_campaign_streak_broken():
    history = [
        {"campaign_pid": "100", "user_id": "U1", "year": 2026, "week": "W4"},
        {"campaign_pid": "100", "user_id": "U1", "year": 2026, "week": "W6"},
    ]
    # Gap at W5 — streak is only 1 (just W6)
    assert compute_campaign_streak(history, "100", "U1") == 1

def test_campaign_streak_longer():
    history = [
        {"campaign_pid": "100", "user_id": "U1", "year": 2026, "week": "W1"},
        {"campaign_pid": "100", "user_id": "U1", "year": 2026, "week": "W2"},
        {"campaign_pid": "100", "user_id": "U1", "year": 2026, "week": "W3"},
        {"campaign_pid": "100", "user_id": "U1", "year": 2026, "week": "W4"},
        {"campaign_pid": "100", "user_id": "U1", "year": 2026, "week": "W5"},
    ]
    assert compute_campaign_streak(history, "100", "U1") == 5

def test_campaign_streak_ignores_other_campaigns():
    history = [
        {"campaign_pid": "100", "user_id": "U1", "year": 2026, "week": "W5"},
        {"campaign_pid": "200", "user_id": "U1", "year": 2026, "week": "W6"},
    ]
    assert compute_campaign_streak(history, "100", "U1") == 1


