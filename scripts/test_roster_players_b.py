"""Tests for /rosterplayers (Shape 2) — bin B: at-risk and history footer.

Companion to test_roster_players_a.py — covers the at-risk section,
the recent join/leave history, and the no-footer fallthrough.
"""
import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(__file__))


def _now_iso(days_ago: int = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def _config():
    return {
        "topic_pairs": [
            {"code": "C00", "name": "Riddleport", "pbp_topic_ids": [100]},
        ],
    }


def test_at_risk_section_lists_week3_warned_players():
    """Players with last_warned_week >= 3 appear with the \U0001f525 marker."""
    from commands.roster_players import build_roster_players
    state = {"players": {
        "100:u1": {"user_id": "u1", "first_name": "Almost",
                   "pbp_topic_id": 100,
                   "last_post_time": _now_iso(22),
                   "last_warned_week": 3},
    }}
    out = build_roster_players(_config(), state)
    assert "At risk" in out
    assert "\U0001f525" in out  # fire emoji
    assert "Almost" in out
    assert "week-3 warning issued" in out


def test_at_risk_section_lists_week2_warned_players():
    """Players with last_warned_week == 2 appear with the \u26a0\ufe0f marker."""
    from commands.roster_players import build_roster_players
    state = {"players": {
        "100:u1": {"user_id": "u1", "first_name": "Wobbling",
                   "pbp_topic_id": 100,
                   "last_post_time": _now_iso(15),
                   "last_warned_week": 2},
    }}
    out = build_roster_players(_config(), state)
    assert "Wobbling" in out and "week-2 warning issued" in out


def test_at_risk_excludes_permanent_players():
    """Permanent players never appear at-risk even if last_warned_week is set."""
    from commands.roster_players import build_roster_players
    state = {"players": {
        "100:u1": {"user_id": "u1", "first_name": "Anthony",
                   "pbp_topic_id": 100, "permanent": True,
                   "last_post_time": _now_iso(100),
                   "last_warned_week": 3},
    }}
    out = build_roster_players(_config(), state)
    # Anthony shows in the table but NOT in an at-risk section
    assert "Anthony" in out
    assert "At risk" not in out


def test_no_at_risk_section_when_no_warned_players():
    """No \U0001f525/\u26a0\ufe0f section when no player has a relevant warning."""
    from commands.roster_players import build_roster_players
    state = {"players": {
        "100:u1": {"user_id": "u1", "first_name": "Active",
                   "pbp_topic_id": 100,
                   "last_post_time": _now_iso(2),
                   "last_warned_week": 0},
    }}
    out = build_roster_players(_config(), state)
    assert "At risk" not in out


def test_recent_history_shows_joins_within_window():
    """player_history join events in the last 30d show in the footer."""
    from commands.roster_players import build_roster_players
    state = {
        "players": {},
        "player_history": [
            {"event": "join", "pid": "100", "name": "NewArrival",
             "at": _now_iso(5), "username": ""},
        ],
    }
    out = build_roster_players(_config(), state)
    assert "Recently joined" in out
    assert "NewArrival" in out


def test_recent_history_shows_leaves_within_window():
    """player_history leave events in the last 30d show in the footer."""
    from commands.roster_players import build_roster_players
    state = {
        "players": {},
        "player_history": [
            {"event": "leave", "pid": "100", "name": "Departing",
             "at": _now_iso(10), "username": ""},
        ],
    }
    out = build_roster_players(_config(), state)
    assert "Recently left" in out
    assert "Departing" in out


def test_old_history_excluded_from_footer():
    """Events older than _HISTORY_DAYS don't appear in the footer."""
    from commands.roster_players import build_roster_players
    state = {
        "players": {},
        "player_history": [
            {"event": "join", "pid": "100", "name": "AncientJoiner",
             "at": _now_iso(120), "username": ""},
        ],
    }
    out = build_roster_players(_config(), state)
    assert "AncientJoiner" not in out
