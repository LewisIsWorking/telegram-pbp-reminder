"""Tests extracted from test_scheduled_coverage.py — bin 3.

Sections in this file:
  - All swimmers voted
  - post_changelog.py
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

from scheduled.swimming_poll import post_swimming_poll, post_swimming_ping

_SWIM_SUNDAY = datetime(2026, 3, 29, 8, 0, tzinfo=timezone.utc)
_SWIM_MONDAY = datetime(2026, 3, 30, 8, 0, tzinfo=timezone.utc)


def test_swimming_poll_skips_non_sunday():
    state = {}
    post_swimming_poll({}, state, now=_SWIM_MONDAY)
    assert "swimming_poll" not in state


def test_swimming_poll_skips_before_hour():
    early = datetime(2026, 3, 29, 4, 0, tzinfo=timezone.utc)
    state = {}
    post_swimming_poll({"poll_post_hour": 7}, state, now=early)
    assert "swimming_poll" not in state


def test_swimming_poll_skips_already_posted():
    state = {"swimming_poll": {"week_iso": "sun2026-03-29"}}
    post_swimming_poll({"poll_post_hour": 7}, state, now=_SWIM_SUNDAY)
    assert state["swimming_poll"]["week_iso"] == "sun2026-03-29"


def test_swimming_poll_posts_on_sunday():
    state = {}
    post_swimming_poll({"poll_post_hour": 7}, state, now=_SWIM_SUNDAY)
    sp = state.get("swimming_poll", {})
    assert sp.get("week_iso") == "sun2026-03-29"
    assert sp.get("poll_message_id") == 99998  # conftest mock


def test_swimming_poll_send_failure_no_state_update():
    state = {}
    with patch("scheduled.swimming_poll.tg.send_poll", return_value=None):
        post_swimming_poll({"poll_post_hour": 7}, state, now=_SWIM_SUNDAY)
    assert "swimming_poll" not in state or not state.get("swimming_poll", {}).get("week_iso")


def test_swimming_ping_skips_wrong_week():
    state = {"swimming_poll": {"week_iso": "sun2026-03-22"}}  # last week
    post_swimming_ping({}, state, now=_SWIM_MONDAY)
    assert state["swimming_poll"].get("last_ping_day", -1) == -1


def test_swimming_ping_skips_already_pinged():
    today = _SWIM_MONDAY.toordinal()
    state = {"swimming_poll": {
        "week_iso": "sun2026-03-29",
        "last_ping_day": today,
        "voted_uids": [],
    }}
    post_swimming_ping({}, state, now=_SWIM_MONDAY)


def test_swimming_ping_all_voted_no_ping():
    # All swimmers voted
    from scheduled.swimming_poll import _SWIMMERS
    all_uids = [str(uid) for uid, _ in _SWIMMERS]
    state = {"swimming_poll": {
        "week_iso": "sun2026-03-29",
        "last_ping_day": -1,
        "voted_uids": all_uids,
        "poll_message_id": 999,
    }}
    post_swimming_ping({}, state, now=_SWIM_MONDAY)
    # Should not update last_ping_day since nobody to ping
    assert state["swimming_poll"]["last_ping_day"] == -1


def test_swimming_ping_sends_for_unvoted():
    state = {"swimming_poll": {
        "week_iso": "sun2026-03-29",
        "last_ping_day": -1,
        "voted_uids": [],
        "poll_message_id": 1234,
    }}
    post_swimming_ping({}, state, now=_SWIM_MONDAY)
    assert state["swimming_poll"]["last_ping_day"] == _SWIM_MONDAY.toordinal()



# ═══════════════════════════════════════════════════════════════════════════════
# post_changelog.py
