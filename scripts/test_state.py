"""
Tests for state.py — file-primary, gist-backup state persistence.
"""

import json
import sys
import os
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

import state as state_store
from state import PARTITIONS, DEFAULT_STATE


# ── Helpers ────────────────────────────────────────────────────────────────────

def _make_full_state() -> dict:
    """Build a minimal but complete state covering every partition."""
    s = dict(DEFAULT_STATE)
    s.update({
        "players": {"100:111": {"name": "Alice"}},
        "removed_players": {},
        "player_registry": {},
        "player_boons": {},
        "mvp_wins": {},
        "gm_queue": {"100": []},
        "gm_queue_replied": {},
        "queue_history": {},
        "queue_archive": [],
        "pending_potw_boons": {},
        "post_timestamps": {"100": {"111": ["2026-03-27T10:00:00+00:00"]}},
        "message_counts": {},
        "activity_hours": {},
        "activity_days": {},
        "word_counts": {},
        "session_counts": {},
        "session_last_day": {},
        "last_weekly_digest": None,
        "last_daily_tip": None,
        "used_tip_indices": [],
        "last_pace_drop_check": None,
        "dying_alerts_sent": {},
        "last_campaign_table": None,
        "session_poll": {},
        "last_state_backup": None,
        "last_queue_daily": None,
        "last_queue_fingerprint": "",
        "queue_nudged": {},
        "celebrated_streaks": {},
        "celebrated_milestones": {},
        "last_archived_week": None,
        "last_recruitment_check": {},
        "last_anniversary": {},
        "combat": {},
        "last_leaderboard": None,
    })
    return s


# ── PARTITIONS contract ────────────────────────────────────────────────────────

def test_all_default_state_keys_are_partitioned():
    """Every DEFAULT_STATE key must appear in exactly one partition."""
    all_mapped = {k for keys in PARTITIONS.values() for k in keys}
    unpartitioned = set(DEFAULT_STATE) - all_mapped
    assert not unpartitioned, f"Unpartitioned DEFAULT_STATE keys: {unpartitioned}"


def test_no_key_in_multiple_partitions():
    """No key should appear in more than one partition."""
    seen = {}
    for partition, keys in PARTITIONS.items():
        for k in keys:
            assert k not in seen, (
                f"Key '{k}' appears in both '{seen[k]}' and '{partition}'"
            )
            seen[k] = partition


def test_all_partitions_are_named():
    """Partition names match expected set."""
    assert set(PARTITIONS) == {"live", "players", "queue", "activity"}


# ── File load/save round-trip ──────────────────────────────────────────────────

def test_save_and_load_round_trip(tmp_path):
    """State written to files should load back identically."""
    original = _make_full_state()

    with patch("state._state_dir", return_value=tmp_path):
        state_store._loaded_ok = True
        state_store._save_to_files(original)
        loaded = state_store._load_from_files()

    # Every partitioned key should survive the round-trip
    all_keys = {k for keys in PARTITIONS.values() for k in keys}
    for k in all_keys:
        if k in original:
            assert loaded[k] == original[k], f"Round-trip mismatch on key '{k}'"


def test_load_returns_none_when_files_missing(tmp_path):
    with patch("state._state_dir", return_value=tmp_path):
        result = state_store._load_from_files()
    assert result is None


def test_load_returns_none_when_partial_files(tmp_path):
    """Missing any single partition file → None (forces gist fallback)."""
    # Write only 'live' partition
    data = {k: {} for k in PARTITIONS["live"]}
    (tmp_path / "live.json").write_text(json.dumps(data))
    with patch("state._state_dir", return_value=tmp_path):
        result = state_store._load_from_files()
    assert result is None


def test_save_creates_one_file_per_partition(tmp_path):
    with patch("state._state_dir", return_value=tmp_path):
        state_store._loaded_ok = True
        state_store._save_to_files(_make_full_state())
    files = {f.name for f in tmp_path.iterdir()}
    assert files == {"live.json", "players.json", "queue.json", "activity.json"}


def test_save_file_is_valid_json(tmp_path):
    with patch("state._state_dir", return_value=tmp_path):
        state_store._loaded_ok = True
        state_store._save_to_files(_make_full_state())
    for f in tmp_path.glob("*.json"):
        data = json.loads(f.read_text())
        assert isinstance(data, dict)


def test_each_partition_file_contains_correct_keys(tmp_path):
    state = _make_full_state()
    with patch("state._state_dir", return_value=tmp_path):
        state_store._loaded_ok = True
        state_store._save_to_files(state)
    for partition, keys in PARTITIONS.items():
        data = json.loads((tmp_path / f"{partition}.json").read_text())
        for k in keys:
            if k in state:
                assert k in data, f"Key '{k}' missing from {partition}.json"


# ── public load() with file fallback ──────────────────────────────────────────

def test_public_load_uses_files_when_present(tmp_path):
    state_store._loaded_ok = False
    state_store._GIST_TOKEN = ""
    state_store._GIST_API = ""

    original = _make_full_state()
    # pre-write files
    with patch("state._state_dir", return_value=tmp_path):
        state_store._save_to_files(original)
        state_store._loaded_ok = False

        with patch("state._save_to_gist"):
            result = state_store.load()

    assert result["offset"] == original["offset"]
    assert result["players"] == original["players"]


def test_public_load_fills_missing_defaults(tmp_path):
    """load() back-fills any DEFAULT_STATE key absent from files."""
    state_store._loaded_ok = False
    state_store._GIST_TOKEN = ""
    state_store._GIST_API = ""

    # Write files without 'last_leaderboard'
    state = _make_full_state()
    del state["last_leaderboard"]
    with patch("state._state_dir", return_value=tmp_path):
        state_store._save_to_files(state)
        state_store._loaded_ok = False
        result = state_store.load()

    assert "last_leaderboard" in result


# ── save() guard ──────────────────────────────────────────────────────────────

def test_save_refused_when_not_loaded(tmp_path, capsys):
    state_store._loaded_ok = False
    with patch("state._state_dir", return_value=tmp_path), \
         patch("state._save_to_gist"):
        state_store.save(_make_full_state())
    captured = capsys.readouterr()
    assert "REFUSING" in captured.out
    assert not any(tmp_path.iterdir())   # no files written
