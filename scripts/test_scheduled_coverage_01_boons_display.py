"""Tests extracted from test_scheduled_coverage.py — bin 1.

Sections in this file:
  - boons/display.py
  - scheduled/week_welcome.py
  - scheduled/week_welcome.py
  - scheduled/queue_nudge.py
  - scheduled/queue_nudge.py
"""
"""
Coverage tests for:
  boons/display.py
  scheduled/week_welcome.py
  scheduled/queue_nudge.py
  scheduled/swimming_poll.py
  post_changelog.py
"""
import sys, os, pytest, importlib.util
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

def _ww_config():
    return {"group_id": -1001, "bot_topic_id": 999, "poll_post_hour": 7}

def _qn_config():
    return {
        "group_id": -1001, "bot_topic_id": 999,
        "gm_user_ids": [999],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
             "gm_user_ids": [999]}
        ]
    }

# ═══════════════════════════════════════════════════════════════════════════════
# boons/display.py

# ═══════════════════════════════════════════════════════════════════════════════

from boons.display import build_boons, build_boons_all


def test_build_boons_empty():
    assert "No boons" in build_boons("100", "U1", "Kibwe", {})


def test_build_boons_with_boons():
    state = {"player_boons": {"100": {"U1": [
        {"text": "A turtle", "date": "2026-03-01", "week": "W10", "campaign": "Kibwe"},
        {"text": "A coin",   "date": "2026-03-08", "week": "W11", "campaign": "Kibwe"},
    ]}}}
    result = build_boons("100", "U1", "Kibwe", state)
    assert "A turtle" in result
    assert "A coin" in result
    assert "W10" in result
    assert "Kibwe" in result


def test_build_boons_all_empty():
    assert "No boons" in build_boons_all("U1", {})


def test_build_boons_all_with_boons():
    state = {"player_boons": {
        "100": {"U1": [{"text": "Boon A", "date": "2026-03-01",
                        "week": "W10", "campaign": "Kibwe"}]},
        "200": {"U1": [{"text": "Boon B", "date": "2026-03-08",
                        "week": "W11", "campaign": "Riddleport"}]},
    }}
    result = build_boons_all("U1", state)
    assert "Boon A" in result
    assert "Boon B" in result
    assert "Kibwe" in result
    assert "Riddleport" in result


def test_build_boons_all_other_player_ignored():
    state = {"player_boons": {"100": {
        "U1": [{"text": "Mine", "date": "2026-03-01", "week": "W1", "campaign": "X"}],
        "U2": [{"text": "Theirs", "date": "2026-03-01", "week": "W1", "campaign": "X"}],
    }}}
    result = build_boons_all("U1", state)
    assert "Mine" in result
    assert "Theirs" not in result



# ═══════════════════════════════════════════════════════════════════════════════
# scheduled/week_welcome.py

# ═══════════════════════════════════════════════════════════════════════════════

from scheduled.week_welcome import post_week_welcome

_SUNDAY = datetime(2026, 3, 29, 8, 0, tzinfo=timezone.utc)  # Sunday after 7am
_FRIDAY = datetime(2026, 4, 3, 8, 0, tzinfo=timezone.utc)


def _ww_config():
    return {"group_id": -1001, "bot_topic_id": 999, "poll_post_hour": 7}


def test_week_welcome_skips_non_sunday():
    state = {}
    post_week_welcome(_ww_config(), state, now=_FRIDAY)
    assert "last_week_welcome" not in state


def test_week_welcome_skips_before_post_hour():
    early = datetime(2026, 3, 29, 5, 0, tzinfo=timezone.utc)
    state = {}
    post_week_welcome(_ww_config(), state, now=early)
    assert "last_week_welcome" not in state


def test_week_welcome_skips_if_already_posted():
    state = {"last_week_welcome": "sun2026-03-29"}
    post_week_welcome(_ww_config(), state, now=_SUNDAY)
    assert state["last_week_welcome"] == "sun2026-03-29"


def test_week_welcome_skips_no_bot_topic():
    config = {"group_id": -1001, "poll_post_hour": 7}
    state = {}
    post_week_welcome(config, state, now=_SUNDAY)
    assert "last_week_welcome" not in state


def test_week_welcome_posts_on_sunday():
    state = {}
    post_week_welcome(_ww_config(), state, now=_SUNDAY)
    assert state.get("last_week_welcome") == "sun2026-03-29"



# ═══════════════════════════════════════════════════════════════════════════════
# scheduled/queue_nudge.py
