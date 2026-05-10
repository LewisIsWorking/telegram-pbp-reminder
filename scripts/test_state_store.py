"""Tests for state_store.StateStore \u2014 slice 1 aux file API.

Coverage:
  * load_aux: missing file returns default
  * load_aux: existing file round-trips through JSON
  * load_aux: corrupt file returns default + prints diagnostic
  * save_aux: writes atomically (tmp + rename, no half-written file
    visible at any point)
  * save_aux: creates the state dir if missing
  * save_aux: round-trips lists, dicts, nested data
  * delete_aux: returns True on existing, False on missing
  * list_aux: returns sorted stems of .json files only
  * list_aux: missing state dir returns empty list
  * state_dir / aux_path: constructor override threads through
"""

import json
from pathlib import Path

import pytest

from state_store import StateStore


def test_default_state_dir_is_repo_data_state():
    store = StateStore()
    expected = Path(__file__).resolve().parent.parent / "data" / "state"
    assert store.state_dir == expected


def test_constructor_override_threads_through(tmp_path):
    store = StateStore(state_dir=tmp_path)
    assert store.state_dir == tmp_path
    assert store.aux_path("foo") == tmp_path / "foo.json"


def test_load_aux_missing_returns_default(tmp_path):
    store = StateStore(state_dir=tmp_path)
    assert store.load_aux("missing") is None
    assert store.load_aux("missing", default=[]) == []
    assert store.load_aux("missing", default={"x": 1}) == {"x": 1}


def test_save_then_load_aux_round_trips(tmp_path):
    store = StateStore(state_dir=tmp_path)
    store.save_aux("ids", [1, 2, 3, 4])
    assert store.load_aux("ids") == [1, 2, 3, 4]


def test_save_aux_round_trips_dicts(tmp_path):
    store = StateStore(state_dir=tmp_path)
    payload = {"alerted_through": "2026-05-09T10:00:00+00:00", "n": 5}
    store.save_aux("marker", payload)
    assert store.load_aux("marker") == payload


def test_save_aux_round_trips_nested_data(tmp_path):
    store = StateStore(state_dir=tmp_path)
    payload = [{"a": 1, "b": [2, 3]}, {"c": {"d": "deep"}}]
    store.save_aux("nested", payload)
    assert store.load_aux("nested") == payload


def test_save_aux_creates_state_dir_if_missing(tmp_path):
    target = tmp_path / "deep" / "nested" / "state"
    store = StateStore(state_dir=target)
    assert not target.exists()
    store.save_aux("ids", [42])
    assert target.exists()
    assert (target / "ids.json").exists()


def test_save_aux_is_atomic_no_tmp_left_behind(tmp_path):
    store = StateStore(state_dir=tmp_path)
    store.save_aux("ids", [1, 2, 3])
    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == [], f"atomic write left tmp files: {leftovers}"


def test_save_aux_overwrite_replaces_atomically(tmp_path):
    """Two consecutive saves \u2014 last write wins, no merge weirdness."""
    store = StateStore(state_dir=tmp_path)
    store.save_aux("ids", [1, 2, 3])
    store.save_aux("ids", [99])
    assert store.load_aux("ids") == [99]


def test_load_aux_corrupt_returns_default(tmp_path, capsys):
    store = StateStore(state_dir=tmp_path)
    bad = tmp_path / "broken.json"
    bad.write_text("{ this is not json", encoding="utf-8")
    assert store.load_aux("broken", default=[]) == []
    captured = capsys.readouterr()
    assert "Corrupt aux file" in captured.out
    assert "broken.json" in captured.out


def test_delete_aux_existing_returns_true(tmp_path):
    store = StateStore(state_dir=tmp_path)
    store.save_aux("temp", [1])
    assert store.delete_aux("temp") is True
    assert not (tmp_path / "temp.json").exists()


def test_delete_aux_missing_returns_false(tmp_path):
    store = StateStore(state_dir=tmp_path)
    assert store.delete_aux("never_existed") is False


def test_list_aux_returns_sorted_stems(tmp_path):
    store = StateStore(state_dir=tmp_path)
    store.save_aux("zulu", [])
    store.save_aux("alpha", [])
    store.save_aux("mike", [])
    assert store.list_aux() == ["alpha", "mike", "zulu"]


def test_list_aux_missing_dir_returns_empty(tmp_path):
    store = StateStore(state_dir=tmp_path / "no_such_dir")
    assert store.list_aux() == []


def test_list_aux_does_not_recurse_into_queues(tmp_path):
    """``queues/`` is a partition concern \u2014 list_aux must not
    descend into it. (Slice 5 adds list_queues separately.)"""
    store = StateStore(state_dir=tmp_path)
    store.save_aux("foo", [])
    queues_dir = tmp_path / "queues"
    queues_dir.mkdir()
    (queues_dir / "100.json").write_text("[]", encoding="utf-8")
    assert store.list_aux() == ["foo"]


def test_save_aux_indented_for_human_readability(tmp_path):
    """State files get committed to git \u2014 readable diffs matter."""
    store = StateStore(state_dir=tmp_path)
    store.save_aux("ids", [1, 2, 3])
    raw = (tmp_path / "ids.json").read_text(encoding="utf-8")
    # indent=2 means at least one newline separating list elements
    assert "\n" in raw


def test_save_aux_uses_default_str_for_unserialisable(tmp_path):
    """``default=str`` lets us serialise datetime objects without
    callers having to convert them first \u2014 same contract as the
    legacy state.py:_save_to_files used."""
    from datetime import datetime, timezone
    store = StateStore(state_dir=tmp_path)
    payload = {"when": datetime(2026, 5, 9, 12, 0, tzinfo=timezone.utc)}
    store.save_aux("event", payload)
    raw = json.loads((tmp_path / "event.json").read_text(encoding="utf-8"))
    assert "2026-05-09" in raw["when"]



# --- partition API (slice 3) ----------------------------------------

def test_partition_exists_missing(tmp_path):
    store = StateStore(state_dir=tmp_path)
    assert store.partition_exists("live") is False


def test_partition_exists_after_save(tmp_path):
    store = StateStore(state_dir=tmp_path)
    store.save_aux("live", {"offset": 0})
    assert store.partition_exists("live") is True


def test_load_partition_missing_returns_none(tmp_path):
    store = StateStore(state_dir=tmp_path)
    assert store.load_partition("never_existed") is None


def test_load_partition_round_trip(tmp_path):
    store = StateStore(state_dir=tmp_path)
    payload = {
        "offset": 42,
        "topics": {"100": {"last_message_time": "2026-05-09T10:00:00"}},
        "gm_queue_history": [],
    }
    store.save_aux("live", payload)
    assert store.load_partition("live") == payload


def test_load_partition_corrupt_returns_none(tmp_path, capsys):
    """Corrupt partition file returns None - callers (state.py) decide
    whether to fall back to gist or use defaults."""
    store = StateStore(state_dir=tmp_path)
    bad = tmp_path / "live.json"
    bad.write_text("{ corrupt", encoding="utf-8")
    assert store.load_partition("live") is None
    captured = capsys.readouterr()
    assert "Corrupt aux file" in captured.out
