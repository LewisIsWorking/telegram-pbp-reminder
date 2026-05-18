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


def test_overview_icon_gates_on_non_perm_count():
    """\u2705 vs \u26a0\ufe0f gates on NON-PERM count only. Permanent
    players are full members (always counted in the active list, shown
    with [perm] tags, never auto-kicked) but they don't fill the
    \"out of 6\" target slots. A campaign at \"4/6 +2 perm\" is still
    under-staffed because it needs 6 non-perm active players, not 6
    total. Lewis clarified this on 2026-05-12; see L23 in
    REFACTOR_PROGRESS.md."""
    from commands.roster import build_roster_overview
    # 4 non-perm + 2 perm = 6 combined, but non-perm 4 < target 6
    # \u2192 \u26a0\ufe0f (this is the case where the new logic
    # differs from the old combined-count logic).
    state = _state(non_perm_recent=4, perm=2, pid="100")
    out = build_roster_overview(_config(), state)
    riddleport_line = next(line for line in out.splitlines()
                           if "Riddleport" in line)
    assert riddleport_line.startswith("\u26a0"), (
        f"Expected \u26a0\ufe0f for 4/6 +2 perm (non-perm under target), "
        f"got: {riddleport_line!r}"
    )
    # 6 non-perm + 0 perm \u2192 \u2705 (clean target hit)
    state = _state(non_perm_recent=6, perm=0, pid="100")
    out = build_roster_overview(_config(), state)
    riddleport_line = next(line for line in out.splitlines()
                           if "Riddleport" in line)
    assert riddleport_line.startswith("\u2705"), (
        f"Expected \u2705 for 6/6 (non-perm at target), got: {riddleport_line!r}"
    )
    # 7 non-perm + 1 perm \u2192 \u2705 (non-perm above target, perm extra)
    state = _state(non_perm_recent=7, perm=1, pid="100")
    out = build_roster_overview(_config(), state)
    riddleport_line = next(line for line in out.splitlines()
                           if "Riddleport" in line)
    assert riddleport_line.startswith("\u2705"), (
        f"Expected \u2705 for 7/6 +1 perm (non-perm above target), "
        f"got: {riddleport_line!r}"
    )


def test_campaign_view_splits_current_and_perm_sections():
    """Per-campaign drill-down renders two separate sections (Current
    for non-perm, Perm for perm) rather than tagging perm players
    inline in a single list. Lewis flagged on 2026-05-17 that the
    inline [perm] tag was easy to miss when 3 of 4 listed names were
    perm. Two sections (omitted when empty) make the split visually
    unambiguous. See L26 in REFACTOR_PROGRESS.md."""
    from commands.roster import build_roster_campaign
    pair = {"code": "C00", "name": "Riddleport", "pbp_topic_ids": [100]}
    state = _state(non_perm_recent=2, perm=1, pid="100")
    out = build_roster_campaign(pair, _config(), state)
    # Two distinct labelled sections; Active0 under Current, Perm0 under Perm.
    assert "Current:\n  \u2022 Active0\n  \u2022 Active1" in out, (
        f"Expected Current section to list Active0 and Active1; got:\n{out}"
    )
    assert "Perm:\n  \u2022 Perm0" in out, (
        f"Expected Perm section to list Perm0; got:\n{out}"
    )
    # Inline [perm] tag is GONE — the section header carries the meaning.
    assert "[perm]" not in out


def test_campaign_view_header_shows_perm_suffix():
    """Per-campaign header uses the same X/Y +Z perm format."""
    from commands.roster import build_roster_campaign
    pair = {"code": "C00", "name": "Riddleport", "pbp_topic_ids": [100]}
    state = _state(non_perm_recent=2, perm=1, pid="100")
    out = build_roster_campaign(pair, _config(), state)
    assert "2/6 +1 perm active player" in out


def test_split_active_partitions_correctly():
    """``_split_active`` returns (non_permanent, permanent) lists,
    preserving input order within each partition. As of 2026-05-17
    (L26) the partition is by ``is_permanent(p, config)``, which
    folds in the ``permanent_user_ids`` config list."""
    from commands.roster import _split_active
    players = [
        {"first_name": "Alice", "user_id": "a"},
        {"first_name": "Bob", "user_id": "b", "permanent": True},
        {"first_name": "Carol", "user_id": "c"},
        {"first_name": "Dave", "user_id": "d", "permanent": True},
    ]
    # Empty config → only the per-record flag determines perm.
    non_perm, perm = _split_active(players, {})
    assert [p["first_name"] for p in non_perm] == ["Alice", "Carol"]
    assert [p["first_name"] for p in perm] == ["Bob", "Dave"]


def test_split_active_honours_config_perm_user_ids():
    """A player whose user_id is in ``config['permanent_user_ids']``
    partitions into perm even when their per-record flag is unset."""
    from commands.roster import _split_active
    players = [
        {"first_name": "Alice", "user_id": "a"},
        {"first_name": "Carol", "user_id": "c"},
    ]
    # Carol listed as a global perm via config → partitions into perm.
    config = {"permanent_user_ids": ["c"]}
    non_perm, perm = _split_active(players, config)
    assert [p["first_name"] for p in non_perm] == ["Alice"]
    assert [p["first_name"] for p in perm] == ["Carol"]
