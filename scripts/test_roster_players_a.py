"""Tests for /rosterplayers (Shape 2) — bin A: aggregation and table.

Covers the cross-campaign player aggregation and table output.
At-risk and history-footer cases live in test_roster_players_b.py
to keep both files under the 200-line cap.
"""
import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(__file__))


def _now_iso(days_ago: int = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def _config_multi():
    return {
        "topic_pairs": [
            {"code": "C00", "name": "Riddleport", "pbp_topic_ids": [100]},
            {"code": "C04", "name": "Magni Guard", "pbp_topic_ids": [200]},
            {"code": "C09", "name": "Metal City",  "pbp_topic_ids": [300]},
        ],
    }


def _state_multi_campaign_player():
    """Bob is in all 3 campaigns; Alice only in C00."""
    return {"players": {
        "100:u1": {"user_id": "u1", "first_name": "Alice",
                   "pbp_topic_id": 100, "last_post_time": _now_iso(2)},
        "100:u2": {"user_id": "u2", "first_name": "Bob",
                   "pbp_topic_id": 100, "last_post_time": _now_iso(5)},
        "200:u2": {"user_id": "u2", "first_name": "Bob",
                   "pbp_topic_id": 200, "last_post_time": _now_iso(10)},
        "300:u2": {"user_id": "u2", "first_name": "Bob",
                   "pbp_topic_id": 300, "last_post_time": _now_iso(1)},
    }}


def test_players_view_groups_by_user_across_campaigns():
    """A multi-campaign player shows on ONE row with all their campaigns."""
    from commands.roster_players import build_roster_players
    out = build_roster_players(_config_multi(),
                               _state_multi_campaign_player())
    bob_lines = [line for line in out.splitlines()
                 if "Bob" in line and "\u2022" in line]
    assert len(bob_lines) == 1, (
        f"Expected one row for Bob, got {len(bob_lines)}: {bob_lines}"
    )
    bob_line = bob_lines[0]
    assert "C00" in bob_line and "C04" in bob_line and "C09" in bob_line


def test_players_view_uses_most_recent_days_across_campaigns():
    """Last-seen for a multi-campaign player is the most-recent post,
    not an average or the earliest entry."""
    from commands.roster_players import build_roster_players
    out = build_roster_players(_config_multi(),
                               _state_multi_campaign_player())
    bob_line = next(line for line in out.splitlines()
                    if "Bob" in line and "\u2022" in line)
    # Bob's most recent: C09 = 1d ago
    assert "1d ago" in bob_line, (
        f"Expected '1d ago' (Bob's most recent), got: {bob_line!r}"
    )


def test_players_view_header_counts_unique_players_and_campaigns():
    """Header reports unique-player count and campaign count."""
    from commands.roster_players import build_roster_players
    out = build_roster_players(_config_multi(),
                               _state_multi_campaign_player())
    # 2 unique users (u1=Alice, u2=Bob), 3 campaigns
    assert "2 unique players" in out
    assert "across 3 campaigns" in out


def test_players_view_tags_perm():
    """Permanent players get the [perm] tag in the player row."""
    from commands.roster_players import build_roster_players
    state = {"players": {
        "100:p1": {"user_id": "p1", "first_name": "Anthony",
                   "pbp_topic_id": 100, "permanent": True,
                   "last_post_time": _now_iso(100)},
    }}
    out = build_roster_players(_config_multi(), state)
    anthony_line = next(line for line in out.splitlines()
                        if "Anthony" in line and "\u2022" in line)
    assert "[perm]" in anthony_line


def test_players_view_sorts_by_recency_with_unknown_last():
    """Players with no last_post_time sort to the bottom."""
    from commands.roster_players import build_roster_players
    state = {"players": {
        "100:u1": {"user_id": "u1", "first_name": "RecentPlayer",
                   "pbp_topic_id": 100, "last_post_time": _now_iso(2)},
        "100:u2": {"user_id": "u2", "first_name": "NeverPosted",
                   "pbp_topic_id": 100},
    }}
    out = build_roster_players(_config_multi(), state)
    pos_recent = out.find("RecentPlayer")
    pos_never  = out.find("NeverPosted")
    assert pos_recent < pos_never, (
        "Players with no last_post_time should sort to the bottom"
    )


def test_players_view_handles_empty_state():
    """Empty state \u2192 zero-player table, no crash."""
    from commands.roster_players import build_roster_players
    out = build_roster_players(_config_multi(), {"players": {}})
    assert "0 unique players" in out
