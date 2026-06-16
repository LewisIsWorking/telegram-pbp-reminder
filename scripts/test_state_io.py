"""
Tests for state.py — file I/O, public load/save API, and save guard.

Partition contract tests live in test_state_partitions.py.
"""

import json
import sys
import os
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

import state as state_store
from state import PARTITIONS, DEFAULT_STATE


# ── Shared fixture ─────────────────────────────────────────────────────────────

def _make_full_state() -> dict:
    """Minimal complete state covering every partition key."""
    s = dict(DEFAULT_STATE)
    s.update({
        "players": {"100:111": {"name": "Alice"}},
        "removed_players": {}, "player_registry": {}, "player_boons": {},
        "mvp_wins": {}, "characters": {"100": {"111": "Aldric"}}, "away": {},
        "gm_queue": {"100": []}, "gm_queue_replied": {}, "queue_history": {},
        "queue_archive": [], "pending_potw_boons": {},
        "post_timestamps": {"100": {"111": ["2026-03-27T10:00:00+00:00"]}},
        "message_counts": {}, "activity_hours": {}, "activity_days": {},
        "word_counts": {}, "session_counts": {}, "session_last_day": {},
        "poll_history": {}, "poll_results": {},
        "clocks": {}, "conditions": {}, "hp_tracker": {}, "loot": {},
        "npcs": {}, "pins": {}, "quests": {}, "reactions": {},
        "timers": {}, "votes": {}, "campaign_notes": {},
        "last_weekly_digest": None, "last_daily_tip": None,
        "used_tip_indices": [], "last_pace_drop_check": None,
        "dying_alerts_sent": {}, "last_campaign_table": None,
        "session_poll": {}, "last_state_backup": None,
        "last_queue_daily": None, "last_queue_fingerprint": "",
        "queue_nudged": {}, "celebrated_streaks": {},
        "celebrated_milestones": {}, "last_archived_week": None,
        "last_recruitment_check": {}, "last_anniversary": {},
        "combat": {}, "last_leaderboard": None,
        "paused_campaigns": {}, "current_scenes": {},
    })
    return s


# ── File round-trip ────────────────────────────────────────────────────────────

def test_save_and_load_round_trip(tmp_path):
    original = _make_full_state()
    with patch("state._state_dir", return_value=tmp_path):
        state_store._loaded_ok = True
        state_store._save_to_files(original)
        loaded = state_store._load_from_files()
    all_keys = {k for keys in PARTITIONS.values() for k in keys}
    for k in all_keys:
        if k in original:
            assert loaded[k] == original[k], f"Round-trip mismatch: '{k}'"


def test_save_creates_one_file_per_partition(tmp_path):
    with patch("state._state_dir", return_value=tmp_path):
        state_store._loaded_ok = True
        state_store._save_to_files(_make_full_state())
    files = {f.name for f in tmp_path.iterdir()}
    expected = {"live.json", "players.json", "queue.json",
                "activity.json", "trackers.json"}
    assert files == expected


def test_save_file_is_valid_json(tmp_path):
    with patch("state._state_dir", return_value=tmp_path):
        state_store._loaded_ok = True
        state_store._save_to_files(_make_full_state())
    for f in tmp_path.glob("*.json"):
        assert isinstance(json.loads(f.read_text(encoding="utf-8")), dict)


def test_each_partition_file_contains_correct_keys(tmp_path):
    state = _make_full_state()
    with patch("state._state_dir", return_value=tmp_path):
        state_store._loaded_ok = True
        state_store._save_to_files(state)
    for partition, keys in PARTITIONS.items():
        data = json.loads((tmp_path / f"{partition}.json").read_text(encoding="utf-8"))
        for k in keys:
            if k in state:
                assert k in data, f"Key '{k}' missing from {partition}.json"


def test_characters_survives_round_trip(tmp_path):
    """Regression: characters was missing from partitions before v4.19."""
    state = _make_full_state()
    state["characters"] = {"100": {"111": "Aldric the Bold"}}
    with patch("state._state_dir", return_value=tmp_path):
        state_store._loaded_ok = True
        state_store._save_to_files(state)
        loaded = state_store._load_from_files()
    assert loaded["characters"] == state["characters"]


# ── Missing / partial files ────────────────────────────────────────────────────

def test_load_returns_none_when_files_missing(tmp_path):
    with patch("state._state_dir", return_value=tmp_path):
        assert state_store._load_from_files() is None


def test_load_returns_none_when_partial_files(tmp_path):
    data = {k: {} for k in PARTITIONS["live"]}
    (tmp_path / "live.json").write_text(json.dumps(data), encoding="utf-8")
    with patch("state._state_dir", return_value=tmp_path):
        assert state_store._load_from_files() is None


def test_load_tolerates_missing_trackers_json(tmp_path):
    """trackers.json absence must not block load (backwards compat)."""
    state = _make_full_state()
    with patch("state._state_dir", return_value=tmp_path):
        state_store._loaded_ok = True
        state_store._save_to_files(state)
    (tmp_path / "trackers.json").unlink()
    with patch("state._state_dir", return_value=tmp_path):
        result = state_store._load_from_files()
    assert result is not None
    assert result["offset"] == state["offset"]


# ── Public load() ──────────────────────────────────────────────────────────────

def test_public_load_uses_files_when_present(tmp_path):
    state_store._loaded_ok = False
    state_store._GIST_TOKEN = ""
    state_store._GIST_API = ""
    original = _make_full_state()
    with patch("state._state_dir", return_value=tmp_path):
        state_store._save_to_files(original)
        state_store._loaded_ok = False
        with patch("state.gist_save"):
            result = state_store.load()
    assert result["offset"] == original["offset"]
    assert result["players"] == original["players"]


def test_public_load_fills_missing_defaults(tmp_path):
    state_store._loaded_ok = False
    state_store._GIST_TOKEN = ""
    state_store._GIST_API = ""
    state = _make_full_state()
    del state["last_leaderboard"]
    with patch("state._state_dir", return_value=tmp_path):
        state_store._save_to_files(state)
        state_store._loaded_ok = False
        result = state_store.load()
    assert "last_leaderboard" in result


# ── Save guard ─────────────────────────────────────────────────────────────────

def test_save_refused_when_not_loaded(tmp_path, capsys):
    state_store._loaded_ok = False
    with patch("state._state_dir", return_value=tmp_path), \
         patch("state.gist_save"):
        state_store.save(_make_full_state())
    assert "REFUSING" in capsys.readouterr().out
    assert not any(tmp_path.iterdir())
