"""Tests for /rostercampaigns (Shape 1) — bin A.

Verifies that build_roster_campaigns emits one block per campaign
in config['topic_pairs'] order, reusing build_roster_campaign's
X/Y +Z perm format for each block.
"""
import sys
import os
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(__file__))


def _now_iso(days_ago: int = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def _two_campaign_config():
    return {
        "topic_pairs": [
            {"code": "C00", "name": "Riddleport", "pbp_topic_ids": [100]},
            {"code": "C04", "name": "Magni Guard", "pbp_topic_ids": [200]},
        ],
    }


def _state_with_players_in_each():
    return {"players": {
        "100:u1": {"user_id": "u1", "first_name": "Alice",
                   "pbp_topic_id": 100, "last_post_time": _now_iso(5)},
        "100:u2": {"user_id": "u2", "first_name": "Bob",
                   "pbp_topic_id": 100, "permanent": True,
                   "last_post_time": _now_iso(99)},
        "200:u3": {"user_id": "u3", "first_name": "Carol",
                   "pbp_topic_id": 200, "last_post_time": _now_iso(3)},
    }}


def test_campaigns_view_emits_block_per_campaign():
    """Every campaign in config gets its own block in the output."""
    from commands.roster_views import build_roster_campaigns
    out = build_roster_campaigns(_two_campaign_config(),
                                 _state_with_players_in_each())
    assert "C00: Riddleport" in out
    assert "C04: Magni Guard" in out


def test_campaigns_view_uses_xyz_perm_format():
    """Blocks inherit the X/Y +Z perm header format from build_roster_campaign."""
    from commands.roster_views import build_roster_campaigns
    out = build_roster_campaigns(_two_campaign_config(),
                                 _state_with_players_in_each())
    # C00 has 1 non-perm (Alice) + 1 perm (Bob) \u2192 "1/6 +1 perm"
    assert "1/6 +1 perm active player" in out
    # C04 has 1 non-perm (Carol) + 0 perm \u2192 "1/6" (no suffix)
    assert "1/6 active player" in out


def test_campaigns_view_splits_current_and_perm_sections():
    """Each campaign block in /rostercampaigns gets the same Current/
    Perm split as a standalone drill-down. Inline [perm] tag is gone
    as of 2026-05-17 (L26)."""
    from commands.roster_views import build_roster_campaigns
    out = build_roster_campaigns(_two_campaign_config(),
                                 _state_with_players_in_each())
    # Bob is the perm player — should appear under a Perm: section.
    assert "Perm:\n  \u2022 Bob" in out, (
        f"Expected Bob under a Perm: section; got:\n{out}"
    )
    # Alice (non-perm) should appear under a Current: section.
    alice_under_current = [line for line in out.splitlines()
                           if line.startswith("  \u2022 Alice")]
    assert alice_under_current, "Alice should appear in a names list"
    # Inline [perm] tag is GONE.
    assert "[perm]" not in out


def test_campaigns_view_block_order_matches_config():
    """Blocks appear in config['topic_pairs'] order, not sorted by count."""
    from commands.roster_views import build_roster_campaigns
    out = build_roster_campaigns(_two_campaign_config(),
                                 _state_with_players_in_each())
    pos_riddleport = out.find("Riddleport")
    pos_magni = out.find("Magni Guard")
    assert pos_riddleport < pos_magni, (
        "Riddleport (first in config) should appear before Magni Guard"
    )


def test_campaigns_view_handles_empty_config():
    """No campaigns configured \u2192 fallback message, no crash."""
    from commands.roster_views import build_roster_campaigns
    out = build_roster_campaigns({"topic_pairs": []}, {"players": {}})
    assert "no campaigns configured" in out.lower()


def test_campaigns_view_includes_history_per_block():
    """Each block carries its own join/leave history from player_history."""
    from commands.roster_views import build_roster_campaigns
    state = _state_with_players_in_each()
    state["player_history"] = [
        {"event": "join", "pid": "100", "name": "Alice",
         "at": _now_iso(3), "username": ""},
    ]
    out = build_roster_campaigns(_two_campaign_config(), state)
    # build_roster_campaign filters by pid, so Alice's join shows under C00
    assert "joined" in out and "Alice" in out
