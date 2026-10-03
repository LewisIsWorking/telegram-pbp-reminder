"""Tests for the permanent-player split in recruitment alerts.

Added 2026-05-12 after Lewis flagged that the recruitment alert
(``check_recruitment_needs`` in ``scheduled/maintenance.py``)
was treating perm players as if they filled target slots. Same
three-role model as L23: perm players are full members but don't
fill the X/Y target slots. Recruitment is now gated on non-perm
count vs target.
"""

import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(__file__))

from _test_checker_helpers import (
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state,
)


def _add_player(state, uid, name, permanent=False):
    now = datetime.now(timezone.utc)
    state["players"][f"100:{uid}"] = {
        "user_id": uid, "first_name": name, "last_name": "",
        "username": name.lower(), "campaign_name": "TestCampaign",
        "pbp_topic_id": "100",
        "last_post_time": now.isoformat(),
        "last_warned_week": 0,
        "permanent": permanent,
    }


def _recruit_msgs():
    return [m for m in _sent_messages
            if "This table has room" in m.get("text", "")]


import pytest
import scheduled.recruit_focus as recruit_focus


@pytest.fixture(autouse=True)
def _no_focus_advert(monkeypatch):
    """These tests cover the per-campaign notice, so the single test campaign
    must not be the one the daily recruit-focus advert already covers (that
    case stands down, and has its own test below)."""
    monkeypatch.setattr(recruit_focus, "pick_recruit_pair", lambda config, state: None)


def test_recruitment_alert_shows_perm_suffix_when_perm_present():
    """5 non-perm + 1 perm renders the X/Y +Z perm format and asks
    for 1 more non-perm player."""
    _reset()
    config = _make_config()
    state = _make_state()
    for i in range(5):
        _add_player(state, str(i), f"Active{i}", permanent=False)
    _add_player(state, "7777", "Permy", permanent=True)
    checker.check_recruitment_needs(config, state, now=datetime.now(timezone.utc))
    msgs = _recruit_msgs()
    assert len(msgs) == 1, f"Expected one alert, got {len(msgs)}"
    text = msgs[0]["text"]
    assert "1 seat open (5/6 players +1 perm)." in text, text
    assert "@permy" in text, text


def test_recruitment_alert_omits_suffix_when_no_perms():
    """4 non-perm + 0 perm renders cleanly as ``4/6`` with no perm clutter."""
    _reset()
    config = _make_config()
    state = _make_state()
    for i in range(4):
        _add_player(state, str(i), f"Active{i}", permanent=False)
    checker.check_recruitment_needs(config, state, now=datetime.now(timezone.utc))
    msgs = _recruit_msgs()
    assert len(msgs) == 1
    text = msgs[0]["text"]
    assert "2 seats open (4/6 players)." in text, text
    assert "perm" not in text


def test_recruitment_alert_skipped_when_non_perm_at_target():
    """6 non-perm + 1 perm \u2192 non-perm meets target, no alert fires."""
    _reset()
    config = _make_config()
    state = _make_state()
    for i in range(6):
        _add_player(state, str(i), f"Active{i}", permanent=False)
    _add_player(state, "7777", "Permy", permanent=True)
    checker.check_recruitment_needs(config, state, now=datetime.now(timezone.utc))
    assert _recruit_msgs() == []


def test_recruitment_alert_fires_when_perms_pad_to_old_target():
    """3 non-perm + 3 perm = 6 total. Pre-fix this would have hit the
    old combined-count target and skipped the alert. Post-fix, it
    correctly fires (only 3 non-perm; needs 3 more)."""
    _reset()
    config = _make_config()
    state = _make_state()
    for i in range(3):
        _add_player(state, str(i), f"Active{i}", permanent=False)
    for i in range(3):
        _add_player(state, f"p{i}", f"Permy{i}", permanent=True)
    checker.check_recruitment_needs(config, state, now=datetime.now(timezone.utc))
    msgs = _recruit_msgs()
    assert len(msgs) == 1
    text = msgs[0]["text"]
    assert "3 seats open (3/6 players +3 perm)." in text, text


def test_notice_stands_down_for_the_campaign_the_focus_advert_covers(monkeypatch):
    """Lewis, 2026-10-03: "We have 2 different posts doing the same chat,
    the top post is better." The campaign the daily recruit-focus advert
    already names gets no second notice."""
    _reset()
    config = _make_config()
    state = _make_state()
    _add_player(state, "1", "Solo", permanent=False)
    pair = config["topic_pairs"][0]
    monkeypatch.setattr(recruit_focus, "pick_recruit_pair", lambda c, s: pair)
    checker.check_recruitment_needs(config, state, now=datetime.now(timezone.utc))
    assert _sent_messages == []


def test_notice_uses_the_focus_advert_layout():
    """Same separator, header, seat line and players line as the advert."""
    _reset()
    config = _make_config()
    state = _make_state()
    _add_player(state, "1", "Solo", permanent=False)
    checker.check_recruitment_needs(config, state, now=datetime.now(timezone.utc))
    text = _recruit_msgs()[0]["text"]
    lines = text.split("\n")
    assert lines[0] == "━" * 16, lines
    assert lines[1].startswith("🧭 This table has room: "), lines
    assert lines[2] == "⏳ 5 seats open (1/6 players).", lines
    assert lines[3] == "👥 Current players: @solo", lines
    assert "📢" not in text and "needs" not in text
