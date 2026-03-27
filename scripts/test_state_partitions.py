"""
Tests for state.py — PARTITIONS contract.

Verifies that every state key used in the codebase is assigned to exactly
one partition, and that critical keys land in the right partition.
File I/O and public API tests live in test_state_io.py.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from state import PARTITIONS, DEFAULT_STATE


# ── Partition structure ────────────────────────────────────────────────────────

def test_all_partitions_are_named():
    assert set(PARTITIONS) == {"live", "players", "queue", "activity", "trackers"}


def test_no_key_in_multiple_partitions():
    seen = {}
    for partition, keys in PARTITIONS.items():
        for k in keys:
            assert k not in seen, (
                f"Key '{k}' appears in both '{seen[k]}' and '{partition}'"
            )
            seen[k] = partition


def test_all_default_state_keys_are_partitioned():
    """Every DEFAULT_STATE key must appear in exactly one partition."""
    all_mapped = {k for keys in PARTITIONS.values() for k in keys}
    unpartitioned = set(DEFAULT_STATE) - all_mapped
    assert not unpartitioned, f"Unpartitioned DEFAULT_STATE keys: {unpartitioned}"


# ── Critical key placement ────────────────────────────────────────────────────

def test_characters_in_players_partition():
    """/setchar writes here — must persist between runs."""
    assert "characters" in PARTITIONS["players"]


def test_away_in_players_partition():
    assert "away" in PARTITIONS["players"]


def test_paused_campaigns_in_live_partition():
    assert "paused_campaigns" in PARTITIONS["live"]


def test_tracker_keys_in_trackers_partition():
    for key in ("clocks", "conditions", "hp_tracker", "loot",
                "npcs", "pins", "quests", "timers", "votes"):
        assert key in PARTITIONS["trackers"], (
            f"'{key}' missing from trackers partition"
        )


def test_poll_keys_in_activity_partition():
    assert "poll_history" in PARTITIONS["activity"]
    assert "poll_results" in PARTITIONS["activity"]


def test_gm_queue_in_queue_partition():
    assert "gm_queue" in PARTITIONS["queue"]
    assert "queue_archive" in PARTITIONS["queue"]


def test_post_timestamps_in_activity_partition():
    assert "post_timestamps" in PARTITIONS["activity"]


def test_offset_in_live_partition():
    """offset is the most critical key — must always be in live.json."""
    assert "offset" in PARTITIONS["live"]
