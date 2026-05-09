"""test_potw_streaks.py — bin 3.

  - announce_streaks
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

