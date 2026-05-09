"""test_potw_streaks.py — bin 2.

  - compute_community_streak
  - streak_announcement
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

# ── compute_community_streak ──────────────────────────────────────────────────

def test_community_streak_empty():
    assert compute_community_streak([], "U1") == 0

def test_community_streak_no_match():
    history = [{"user_id": "U2", "year": 2026, "week": "W5"}]
    assert compute_community_streak(history, "U1") == 0

def test_community_streak_single():
    history = [{"user_id": "U1", "year": 2026, "week": "W5", "campaign_pid": "100"}]
    assert compute_community_streak(history, "U1") == 1

def test_community_streak_deduplicates_same_week():
    history = [
        {"user_id": "U1", "year": 2026, "week": "W5", "campaign_pid": "100"},
        {"user_id": "U1", "year": 2026, "week": "W5", "campaign_pid": "200"},
    ]
    # Same week in two campaigns = 1 win
    assert compute_community_streak(history, "U1") == 1

def test_community_streak_two_consecutive():
    history = [
        {"user_id": "U1", "year": 2026, "week": "W5", "campaign_pid": "100"},
        {"user_id": "U1", "year": 2026, "week": "W6", "campaign_pid": "200"},
    ]
    assert compute_community_streak(history, "U1") == 2

def test_community_streak_broken():
    history = [
        {"user_id": "U1", "year": 2026, "week": "W3", "campaign_pid": "100"},
        {"user_id": "U1", "year": 2026, "week": "W5", "campaign_pid": "100"},
    ]
    assert compute_community_streak(history, "U1") == 1



# ── streak_announcement ───────────────────────────────────────────────────────

def test_announcement_campaign_milestone():
    msg = streak_announcement(2, "Alice", "Kibwe", "campaign")
    assert msg is not None
    assert "Alice" in msg
    assert "2-week" in msg
    assert "Kibwe" in msg

def test_announcement_community_milestone():
    msg = streak_announcement(3, "Bob", "Kibwe", "community")
    assert msg is not None
    assert "Bob" in msg
    assert "3 consecutive" in msg

def test_announcement_non_milestone_campaign():
    assert streak_announcement(1, "Alice", "Kibwe", "campaign") is None
    assert streak_announcement(4, "Alice", "Kibwe", "campaign") is None
    assert streak_announcement(6, "Alice", "Kibwe", "campaign") is None

def test_announcement_non_milestone_community():
    assert streak_announcement(1, "Bob", "Kibwe", "community") is None
    assert streak_announcement(4, "Bob", "Kibwe", "community") is None

def test_all_campaign_milestones_produce_messages():
    for m in CAMPAIGN_MILESTONES:
        assert streak_announcement(m, "X", "Y", "campaign") is not None

def test_all_community_milestones_produce_messages():
    for m in COMMUNITY_MILESTONES:
        assert streak_announcement(m, "X", "Y", "community") is not None


