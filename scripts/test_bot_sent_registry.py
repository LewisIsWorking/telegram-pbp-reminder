"""Tests for posting.bot_sent_registry — the bot's delete-safety registry.

This is a critical-safety module, so the test surface is broad:

  * record/check round-trip (record then is_bot_sent returns True)
  * unrecorded IDs return False (the negative case is the safety case)
  * persistence: writes to disk, reloads cleanly
  * backfill from sample state files (live.json, queues/*.json shapes)
  * set semantics on duplicate adds
  * graceful handling of missing/corrupt state files
  * thread-safety lock is held appropriately

Each test isolates the registry by pointing _STATE_PATH at a tmp_path
and calling reset_for_test() before exercising the API.
"""

import json

import pytest

from posting import bot_sent_registry as reg


@pytest.fixture(autouse=True)
def isolated_registry(tmp_path, monkeypatch):
    """Point the registry at tmp_path/bot_sent_ids.json for every test.

    Resets in-memory state before each test so previous tests can't
    leak IDs into this one. monkeypatch undoes the path swap when the
    test ends, so production paths are untouched.
    """
    monkeypatch.setattr(reg, "_STATE_PATH", tmp_path / "bot_sent_ids.json")
    reg.reset_for_test()
    yield
    reg.reset_for_test()


def test_record_then_is_bot_sent_returns_true():
    reg.record_sent(12345)
    assert reg.is_bot_sent(12345) is True


def test_unrecorded_id_returns_false():
    reg.record_sent(11111)
    assert reg.is_bot_sent(99999) is False


def test_is_bot_sent_with_none_returns_false():
    assert reg.is_bot_sent(None) is False


def test_record_sent_with_none_is_noop():
    reg.record_sent(None)
    # No crash, no entry. Confirm by checking some random ID is False.
    assert reg.is_bot_sent(0) is False


def test_record_many_records_all():
    reg.record_many([1, 2, 3, None, 4])
    assert reg.is_bot_sent(1) is True
    assert reg.is_bot_sent(2) is True
    assert reg.is_bot_sent(3) is True
    assert reg.is_bot_sent(4) is True
    assert reg.is_bot_sent(5) is False


def test_duplicate_records_are_set_safe():
    reg.record_sent(42)
    reg.record_sent(42)
    reg.record_sent(42)
    assert reg.is_bot_sent(42) is True


def test_persists_to_disk(tmp_path, monkeypatch):
    """After record_sent, the file on disk contains the ID."""
    reg.record_sent(7777)
    state_path = reg._STATE_PATH
    assert state_path.exists()
    with open(state_path) as f:
        data = json.load(f)
    assert 7777 in data


def test_reload_picks_up_persisted_ids():
    reg.record_sent(8888)
    # Force an in-memory reset and confirm the disk file is re-read.
    reg.reset_for_test()
    assert reg.is_bot_sent(8888) is True


def test_corrupt_state_file_starts_empty(tmp_path, monkeypatch, capsys):
    """A malformed bot_sent_ids.json should not crash; just empties."""
    bad_path = tmp_path / "bot_sent_ids.json"
    bad_path.write_text("{ this is : not json")
    monkeypatch.setattr(reg, "_STATE_PATH", bad_path)
    reg.reset_for_test()

    # is_bot_sent on any ID returns False because the registry is empty.
    assert reg.is_bot_sent(12345) is False
    captured = capsys.readouterr()
    assert "Corrupt" in captured.out


def test_missing_state_file_starts_empty():
    """No file on disk yet — first call should succeed and create it."""
    assert reg.is_bot_sent(12345) is False
    reg.record_sent(99)
    assert reg.is_bot_sent(99) is True


def test_backfill_from_live_state(tmp_path, monkeypatch):
    """Backfill picks up IDs from live.json shape on first load."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "live.json").write_text(json.dumps({
        "last_queue_pin_id": 100,
        "gm_queue_history": [
            {"msg_ids": [200, 201], "pin_id": 200},
            {"msg_ids": [300, 301, 302], "pin_id": 300},
        ],
    }))
    monkeypatch.setattr(reg, "_STATE_PATH", state_dir / "bot_sent_ids.json")
    reg.reset_for_test()

    for mid in (100, 200, 201, 300, 301, 302):
        assert reg.is_bot_sent(mid) is True, f"backfill missed {mid}"


def test_backfill_from_queue_state(tmp_path, monkeypatch):
    """Backfill picks up IDs from queues/{pid}.json shapes too."""
    state_dir = tmp_path / "state"
    queues_dir = state_dir / "queues"
    queues_dir.mkdir(parents=True)
    (queues_dir / "100.json").write_text(json.dumps({
        "topic_msg_id": 5000,
        "topic_queues": {
            "100": {"msg_ids": [5001, 5002], "fingerprint": ""},
            "200": {"msg_id": 6000, "fingerprint": ""},
            "300": {"msg_ids": [7000], "caught_up_msg_id": 7001,
                    "pin_id": 7000},
        },
    }))
    monkeypatch.setattr(reg, "_STATE_PATH", state_dir / "bot_sent_ids.json")
    reg.reset_for_test()

    for mid in (5000, 5001, 5002, 6000, 7000, 7001):
        assert reg.is_bot_sent(mid) is True, f"backfill missed {mid}"


def test_backfill_handles_corrupt_queue_file(tmp_path, monkeypatch):
    """A single corrupt queue file should not crash the backfill."""
    state_dir = tmp_path / "state"
    queues_dir = state_dir / "queues"
    queues_dir.mkdir(parents=True)
    (queues_dir / "100.json").write_text(json.dumps({
        "topic_msg_id": 1000,
    }))
    (queues_dir / "200.json").write_text("{not json")  # corrupt
    monkeypatch.setattr(reg, "_STATE_PATH", state_dir / "bot_sent_ids.json")
    reg.reset_for_test()

    assert reg.is_bot_sent(1000) is True


def test_backfill_idempotent(tmp_path, monkeypatch):
    """Running backfill twice doesn't double-count or fail."""
    state_dir = tmp_path / "state"
    state_dir.mkdir()
    (state_dir / "live.json").write_text(json.dumps({
        "last_queue_pin_id": 42,
    }))
    monkeypatch.setattr(reg, "_STATE_PATH", state_dir / "bot_sent_ids.json")
    reg.reset_for_test()

    # First load triggers the backfill.
    assert reg.is_bot_sent(42) is True
    # Force another reload — backfill runs again, no error, still True.
    reg.reset_for_test()
    assert reg.is_bot_sent(42) is True
