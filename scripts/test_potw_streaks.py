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


# ── announce_streaks ──────────────────────────────────────────────────────────

def _make_winner():
    return {"user_id": "U1", "first_name": "Alice", "username": "alice"}

def _make_config():
    return {"group_id": -1001, "bot_topic_id": 999}

def _make_state(history=None):
    return {"potw_history": history or []}


@patch("scheduled.potw_streaks.tg")
@patch("scheduled.potw_streaks.helpers")
def test_announce_streaks_no_streak(mock_helpers, mock_tg):
    mock_helpers.player_mention.return_value = "Alice"
    state = _make_state()
    announce_streaks(_make_config(), state, _make_winner(), "Kibwe", "100", -1001, 40585)
    mock_tg.send_message.assert_not_called()


@patch("scheduled.potw_streaks.tg")
@patch("scheduled.potw_streaks.helpers")
def test_announce_streaks_campaign_milestone(mock_helpers, mock_tg):
    mock_helpers.player_mention.return_value = "Alice"
    history = [
        {"campaign_pid": "100", "user_id": "U1", "year": 2026, "week": "W5"},
        {"campaign_pid": "100", "user_id": "U1", "year": 2026, "week": "W6"},
    ]
    state = _make_state(history)
    announce_streaks(_make_config(), state, _make_winner(), "Kibwe", "100", -1001, 40585)
    # Campaign streak=2 (milestone) AND community streak=2 (milestone) → 2 calls
    assert mock_tg.send_message.call_count == 2
    # First call is to campaign topic
    first_args = mock_tg.send_message.call_args_list[0][0]
    assert first_args[1] == 40585
    assert "2-week" in first_args[2]


@patch("scheduled.potw_streaks.tg")
@patch("scheduled.potw_streaks.helpers")
def test_announce_streaks_community_milestone(mock_helpers, mock_tg):
    mock_helpers.player_mention.return_value = "Alice"
    history = [
        {"campaign_pid": "100", "user_id": "U1", "year": 2026, "week": "W4"},
        {"campaign_pid": "200", "user_id": "U1", "year": 2026, "week": "W5"},
        {"campaign_pid": "100", "user_id": "U1", "year": 2026, "week": "W6"},
    ]
    state = _make_state(history)
    announce_streaks(_make_config(), state, _make_winner(), "Kibwe", "100", -1001, 40585)
    # Campaign streak=1 (no milestone), community streak=3 (milestone)
    assert mock_tg.send_message.call_count == 1
    args = mock_tg.send_message.call_args[0]
    assert args[1] == 999  # sent to bot topic


@patch("scheduled.potw_streaks.tg")
@patch("scheduled.potw_streaks.helpers")
def test_announce_streaks_no_bot_topic(mock_helpers, mock_tg):
    mock_helpers.player_mention.return_value = "Alice"
    history = [
        {"campaign_pid": "100", "user_id": "U1", "year": 2026, "week": "W4"},
        {"campaign_pid": "200", "user_id": "U1", "year": 2026, "week": "W5"},
        {"campaign_pid": "100", "user_id": "U1", "year": 2026, "week": "W6"},
    ]
    state = _make_state(history)
    config = {"group_id": -1001}  # no bot_topic_id
    announce_streaks(config, state, _make_winner(), "Kibwe", "100", -1001, 40585)
    # Community milestone exists but no bot topic — should not send
    mock_tg.send_message.assert_not_called()
