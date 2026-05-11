"""Tests for /rosterall (Shape 3): per-campaign blocks + footer.

build_roster_all = build_roster_campaigns + (at-risk / history footer
from roster_players). Verifies both halves appear in the output and
the footer is omitted gracefully when there's nothing to report.
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
            {"code": "C04", "name": "Magni Guard", "pbp_topic_ids": [200]},
        ],
    }


def test_all_view_includes_every_campaign_block():
    """Per-campaign blocks from Shape 1 appear in the output."""
    from commands.roster_views import build_roster_all
    state = {"players": {
        "100:u1": {"user_id": "u1", "first_name": "Alice",
                   "pbp_topic_id": 100, "last_post_time": _now_iso(5)},
        "200:u2": {"user_id": "u2", "first_name": "Bob",
                   "pbp_topic_id": 200, "last_post_time": _now_iso(3)},
    }}
    out = build_roster_all(_config(), state)
    assert "C00: Riddleport" in out
    assert "C04: Magni Guard" in out


def test_all_view_appends_at_risk_footer():
    """At-risk players surface in the footer below the per-campaign blocks."""
    from commands.roster_views import build_roster_all
    state = {"players": {
        "100:u1": {"user_id": "u1", "first_name": "Risky",
                   "pbp_topic_id": 100,
                   "last_post_time": _now_iso(22),
                   "last_warned_week": 3},
    }}
    out = build_roster_all(_config(), state)
    # Block reference appears before the at-risk footer (rule between them)
    pos_block = out.find("Riddleport")
    pos_footer = out.find("At risk")
    assert pos_block < pos_footer, (
        "At-risk footer should come after the per-campaign blocks"
    )
    assert "Risky" in out
    assert "\U0001f525" in out  # fire emoji


def test_all_view_appends_history_footer():
    """Recent joins/leaves appear in the footer."""
    from commands.roster_views import build_roster_all
    state = {
        "players": {},
        "player_history": [
            {"event": "join", "pid": "100", "name": "NewPlayer",
             "at": _now_iso(7), "username": ""},
            {"event": "leave", "pid": "100", "name": "GonePlayer",
             "at": _now_iso(14), "username": ""},
        ],
    }
    out = build_roster_all(_config(), state)
    assert "Recently joined" in out and "NewPlayer" in out
    assert "Recently left" in out and "GonePlayer" in out


def test_all_view_omits_footer_when_nothing_to_report():
    """No at-risk / no history \u2192 footer omitted entirely (clean output)."""
    from commands.roster_views import build_roster_all
    state = {"players": {
        "100:u1": {"user_id": "u1", "first_name": "Calm",
                   "pbp_topic_id": 100,
                   "last_post_time": _now_iso(2)},
    }}
    out = build_roster_all(_config(), state)
    assert "At risk" not in out
    assert "Recently joined" not in out
    assert "Recently left" not in out
    # No trailing rule when no footer
    assert not out.endswith("\u2550")


def test_all_view_omits_player_table_redundant_with_blocks():
    """The cross-campaign player table from /rosterplayers is NOT
    re-emitted in /rosterall \u2014 it's redundant with the per-campaign
    blocks that already list every player. Only the actionable
    footer (at-risk + history) carries over."""
    from commands.roster_views import build_roster_all
    state = {"players": {
        "100:u1": {"user_id": "u1", "first_name": "OnlyAlice",
                   "pbp_topic_id": 100, "last_post_time": _now_iso(2)},
    }}
    out = build_roster_all(_config(), state)
    # The "Player Roster — N unique players across M campaigns" header
    # from build_roster_players should NOT appear in build_roster_all
    assert "unique players across" not in out
