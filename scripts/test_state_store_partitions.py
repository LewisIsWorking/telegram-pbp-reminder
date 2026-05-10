"""Tests for state_store.StateStore - partition API (slices 3 & 4 of P3/9).

Sibling of ``test_state_store.py``; that file covers the aux file API
(slices 1-2: load_aux / save_aux / delete_aux / list_aux). Both files
live next to each other to keep each under the 200-line cap while
still grouping tests by the API surface they exercise.

Slice 3 coverage (read path):
  * partition_exists: True/False after save/missing
  * load_partition: None for missing, round-trip for present, None
    plus diagnostic for corrupt

Slice 4 coverage (write path with atomic semantics):
  * save_partition: round-trip
  * save_partition: tmp+rename leaves no .tmp sibling on success
  * save_partition: creates state_dir if missing
  * save_partition: overwrite replaces atomically (last-write-wins)
  * save_partition: partition_exists flips True after first save
"""

from state_store import StateStore


# --- partition API read path (slice 3) -----------------------------

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
    """Corrupt partition file returns None; callers (state.py) decide
    whether to fall back to gist or use defaults."""
    store = StateStore(state_dir=tmp_path)
    bad = tmp_path / "live.json"
    bad.write_text("{ corrupt", encoding="utf-8")
    assert store.load_partition("live") is None
    captured = capsys.readouterr()
    assert "Corrupt partition file" in captured.out


# --- partition API write path (slice 4) ----------------------------

def test_save_partition_round_trip(tmp_path):
    store = StateStore(state_dir=tmp_path)
    payload = {
        "offset": 619334477,
        "topics": {"100": {"last_message_time": "2026-05-09T10:00:00"}},
    }
    store.save_partition("live", payload)
    assert store.load_partition("live") == payload


def test_save_partition_is_atomic_no_tmp_left_behind(tmp_path):
    """Tmp+rename means no .tmp sibling visible after a successful save."""
    store = StateStore(state_dir=tmp_path)
    store.save_partition("live", {"offset": 1})
    leftovers = list(tmp_path.glob("*.tmp"))
    assert leftovers == [], f"atomic write left tmp files: {leftovers}"


def test_save_partition_creates_state_dir(tmp_path):
    """First save creates the state dir if missing."""
    target = tmp_path / "fresh"
    store = StateStore(state_dir=target)
    assert not target.exists()
    store.save_partition("live", {"offset": 0})
    assert (target / "live.json").exists()


def test_save_partition_overwrite_replaces_atomically(tmp_path):
    """Subsequent save replaces the file completely (last-write-wins)."""
    store = StateStore(state_dir=tmp_path)
    store.save_partition("live", {"offset": 1})
    store.save_partition("live", {"offset": 2})
    assert store.load_partition("live") == {"offset": 2}


def test_save_partition_then_partition_exists_returns_true(tmp_path):
    """Saving creates the file so partition_exists flips True."""
    store = StateStore(state_dir=tmp_path)
    assert store.partition_exists("live") is False
    store.save_partition("live", {"offset": 0})
    assert store.partition_exists("live") is True
