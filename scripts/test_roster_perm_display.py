"""Tests for the permanent-player display in /roster output.

Added 2026-05-11 after Lewis spotted that /roster's "5/6" for
Grand Explorers didn't distinguish the 4 non-permanent active
players from the 1 permanent player holding a roster slot.
The new display format ``X/Y +Z perm`` makes that distinction
visible without changing which campaigns warn (the warning icon
still gates on the combined count).
"""
import sys, os
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


def _state(non_perm_recent: int = 0, perm: int = 0, pid: str = "100") -> dict:
    """Build a state with N non-permanent recent players + M permanent players
    all assigned to ``pid``."""
    players = {}
    for i in range(non_perm_recent):
        players[f"{pid}:n{i}"] = {
            "user_id": f"n{i}", "first_name": f"Active{i}",
            "pbp_topic_id": pid, "last_post_time": _now_iso(5),
        }
    for i in range(perm):
        players[f"{pid}:p{i}"] = {
            "user_id": f"p{i}", "first_name": f"Perm{i}",
            "pbp_topic_id": pid, "permanent": True,
            "last_post_time": _now_iso(120),  # Dormant 120d, still counted
        }
    return {"players": players}


def test_overview_shows_perm_suffix_when_perm_present():
    """``X/Y +Z perm`` suffix appears when a campaign has perm players."""
    from commands.roster import build_roster_overview
    state = _state(non_perm_recent=4, perm=2, pid="100")
    out = build_roster_overview(_config(), state)
    assert "C00: Riddleport \u2014 4/6 +2 perm" in out


def test_overview_omits_perm_suffix_when_zero_perm():
    """No ``+0 perm`` for campaigns without permanent players."""
    from commands.roster import build_roster_overview
    state = _state(non_perm_recent=5, perm=0, pid="100")
    out = build_roster_overview(_config(), state)
    # Should read cleanly as "5/6", not "5/6 +0 perm"
    assert "C00: Riddleport \u2014 5/6\n" in out or out.endswith("C00: Riddleport \u2014 5/6")
    assert "+0 perm" not in out


def test_overview_icon_uses_combined_count():
    """\u2705 vs \u26a0\ufe0f gates on combined count (non-perm + perm), so the
    same campaigns warn as before. Lewis's display change must not
    change warning semantics."""
    from commands.roster import build_roster_overview
    # 4 non-perm + 2 perm = 6 combined, hits target \u2192 \u2705
    state = _state(non_perm_recent=4, perm=2, pid="100")
    out = build_roster_overview(_config(), state)
    riddleport_line = next(line for line in out.splitlines()
                           if "Riddleport" in line)
    assert riddleport_line.startswith("\u2705"), (
        f"Expected \u2705 for combined 6/6, got: {riddleport_line!r}"
    )
    # 3 non-perm + 2 perm = 5 combined, under target \u2192 \u26a0\ufe0f
    state = _state(non_perm_recent=3, perm=2, pid="100")
    out = build_roster_overview(_config(), state)
    riddleport_line = next(line for line in out.splitlines()
                           if "Riddleport" in line)
    assert riddleport_line.startswith("\u26a0"), (
        f"Expected \u26a0\ufe0f for combined 5/6, got: {riddleport_line!r}"
    )


def test_campaign_view_tags_perm_players_in_name_list():
    """Per-campaign drill-down marks ``[perm]`` next to each permanent
    player's name so the GM can identify which slots are perm at a glance."""
    from commands.roster import build_roster_campaign
    pair = {"code": "C00", "name": "Riddleport", "pbp_topic_ids": [100]}
    state = _state(non_perm_recent=2, perm=1, pid="100")
    out = build_roster_campaign(pair, _config(), state)
    # Active0 is non-perm, Perm0 is perm
    assert "\u2022 Active0\n" in out + "\n"  # no [perm] tag on non-perm
    assert "\u2022 Perm0 [perm]" in out


def test_campaign_view_header_shows_perm_suffix():
    """Per-campaign header uses the same X/Y +Z perm format."""
    from commands.roster import build_roster_campaign
    pair = {"code": "C00", "name": "Riddleport", "pbp_topic_ids": [100]}
    state = _state(non_perm_recent=2, perm=1, pid="100")
    out = build_roster_campaign(pair, _config(), state)
    assert "2/6 +1 perm active player" in out


def test_split_active_partitions_correctly():
    """``_split_active`` returns (non_permanent, permanent) lists,
    preserving input order within each partition."""
    from commands.roster import _split_active
    players = [
        {"first_name": "Alice"},
        {"first_name": "Bob", "permanent": True},
        {"first_name": "Carol"},
        {"first_name": "Dave", "permanent": True},
    ]
    non_perm, perm = _split_active(players)
    assert [p["first_name"] for p in non_perm] == ["Alice", "Carol"]
    assert [p["first_name"] for p in perm] == ["Bob", "Dave"]
