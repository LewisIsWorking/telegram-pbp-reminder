"""Tests for posting.refusal_log — persistent refusal audit trail.

Covers:
  * record_refusal appends to disk
  * get_unalerted_refusals returns only entries newer than marker
  * mark_alerted updates the marker correctly
  * missing/corrupt files don't crash anyone
  * timestamps default to now-UTC and round-trip cleanly
"""

import json
from pathlib import Path

import pytest

from posting import refusal_log as rl


@pytest.fixture(autouse=True)
def isolated_log(tmp_path, monkeypatch):
    """Point both files at tmp_path so production state isn't touched."""
    monkeypatch.setattr(rl, "_LOG_PATH",
                        tmp_path / "refusal_log.json")
    monkeypatch.setattr(rl, "_ALERTED_PATH",
                        tmp_path / "refusal_log_alerted.json")
    rl.reset_for_test()
    yield
    rl.reset_for_test()


def test_record_refusal_appends_to_disk():
    rl.record_refusal(-1001, 12345)
    with open(rl._LOG_PATH, encoding="utf-8") as f:
        entries = json.load(f)
    assert len(entries) == 1
    assert entries[0]["chat_id"] == -1001
    assert entries[0]["message_id"] == 12345
    assert "timestamp" in entries[0]


def test_record_refusal_with_explicit_timestamp():
    rl.record_refusal(-1001, 99, timestamp="2026-01-01T00:00:00+00:00")
    with open(rl._LOG_PATH, encoding="utf-8") as f:
        entries = json.load(f)
    assert entries[0]["timestamp"] == "2026-01-01T00:00:00+00:00"


def test_record_multiple_refusals_appends_in_order():
    rl.record_refusal(-1001, 1, timestamp="2026-01-01T00:00:00+00:00")
    rl.record_refusal(-1001, 2, timestamp="2026-01-02T00:00:00+00:00")
    rl.record_refusal(-1001, 3, timestamp="2026-01-03T00:00:00+00:00")
    with open(rl._LOG_PATH, encoding="utf-8") as f:
        entries = json.load(f)
    assert [e["message_id"] for e in entries] == [1, 2, 3]


def test_get_unalerted_returns_all_when_no_marker():
    rl.record_refusal(-1001, 1, timestamp="2026-01-01T00:00:00+00:00")
    rl.record_refusal(-1001, 2, timestamp="2026-01-02T00:00:00+00:00")
    unalerted = rl.get_unalerted_refusals()
    assert len(unalerted) == 2


def test_get_unalerted_filters_by_marker():
    rl.record_refusal(-1001, 1, timestamp="2026-01-01T00:00:00+00:00")
    rl.record_refusal(-1001, 2, timestamp="2026-01-02T00:00:00+00:00")
    rl.record_refusal(-1001, 3, timestamp="2026-01-03T00:00:00+00:00")
    rl.mark_alerted("2026-01-01T12:00:00+00:00")
    unalerted = rl.get_unalerted_refusals()
    assert [e["message_id"] for e in unalerted] == [2, 3]


def test_get_unalerted_returns_empty_when_marker_at_end():
    rl.record_refusal(-1001, 1, timestamp="2026-01-01T00:00:00+00:00")
    rl.mark_alerted("2026-12-31T00:00:00+00:00")
    assert rl.get_unalerted_refusals() == []


def test_mark_alerted_default_is_now():
    rl.record_refusal(-1001, 1, timestamp="2026-01-01T00:00:00+00:00")
    rl.mark_alerted()  # default = now
    # The marker should be > the entry timestamp (now > 2026-01-01)
    assert rl.get_unalerted_refusals() == []


def test_corrupt_log_file_returns_empty():
    rl._LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    rl._LOG_PATH.write_text("{ corrupt", encoding="utf-8")
    assert rl.get_unalerted_refusals() == []


def test_missing_log_file_returns_empty():
    # Default fixture state: no log file exists yet
    assert rl.get_unalerted_refusals() == []


def test_corrupt_marker_file_treated_as_no_marker():
    rl._ALERTED_PATH.parent.mkdir(parents=True, exist_ok=True)
    rl._ALERTED_PATH.write_text("{ corrupt", encoding="utf-8")
    rl.record_refusal(-1001, 1, timestamp="2026-01-01T00:00:00+00:00")
    assert len(rl.get_unalerted_refusals()) == 1
