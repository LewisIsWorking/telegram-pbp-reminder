"""Tests extracted from test_commands_coverage.py — bin 1.

Sections in this file:
  - commands/queue_io.py
  - commands/player_registry.py
  - commands/player_registry.py
"""
"""
Coverage tests for:
  commands/queue_io.py
  commands/player_registry.py
  scheduled/poll_result.py
  scheduled/diagnostic.py
  scheduled/reports.py  (partial — tg-calling functions mocked)
"""
import sys, os, json, pytest, tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

@pytest.fixture
def tmp_queues(tmp_path, monkeypatch):
    """Redirect queue_io file operations to a temp directory."""
    monkeypatch.setattr(queue_io, "_store", StateStore(state_dir=tmp_path))
    queues_dir = tmp_path / "queues"
    queues_dir.mkdir(parents=True, exist_ok=True)
    return queues_dir

def _pr_config():
    return {
        "group_id": -1001,
        "topic_pairs": [{
            "pbp_topic_ids": [100], "code": "C01",
            "name": "DF", "hybrid_live": True,
            "chat_topic_id": 21514,
            "poll_options": ["Friday", "Saturday", "Either", "Both", "Can't make it"],
            "allows_multiple_answers": False,
        }]
    }

def _rpt_config():
    return {
        "group_id": -1001,
        "bot_topic_id": 999,
        "gm_user_ids": [999],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C00", "name": "R",
             "gm_user_ids": [999], "chat_topic_id": 21514}
        ]
    }

# ═══════════════════════════════════════════════════════════════════════════════
# commands/queue_io.py

# ═══════════════════════════════════════════════════════════════════════════════

from commands import queue_io
from state_store import StateStore


@pytest.fixture
def tmp_queues(tmp_path, monkeypatch):
    """Redirect queue_io file operations to a temp directory."""
    monkeypatch.setattr(queue_io, "_store", StateStore(state_dir=tmp_path))
    queues_dir = tmp_path / "queues"
    queues_dir.mkdir(parents=True, exist_ok=True)
    return queues_dir


def test_load_missing_returns_empty(tmp_queues):
    result = queue_io.load("999")
    assert result["unreplied"] == []
    assert result["replied"] == []
    assert result["reply_log"] == []


def test_load_existing(tmp_queues):
    data = {"pid": "100", "unreplied": [{"message_id": 1}], "replied": [], "reply_log": []}
    (tmp_queues / "100.json").write_text(json.dumps(data), encoding="utf-8")
    result = queue_io.load("100")
    assert result["unreplied"][0]["message_id"] == 1


def test_load_corrupt_returns_empty(tmp_queues):
    (tmp_queues / "100.json").write_text("not json{{}", encoding="utf-8")
    result = queue_io.load("100")
    assert result["unreplied"] == []


def test_save_creates_file(tmp_queues):
    cq = {"pid": "100", "unreplied": [], "replied": [], "reply_log": []}
    assert queue_io.save("100", cq) is True
    assert (tmp_queues / "100.json").exists()


def test_save_oserror(tmp_queues, monkeypatch):
    def _raise(*_a, **_k):
        raise OSError("disk full")
    monkeypatch.setattr(queue_io._store, "save_queue", _raise)
    assert queue_io.save("100", {}) is False


def test_all_pids_empty(tmp_queues):
    assert queue_io.all_pids() == []


def test_all_pids_with_files(tmp_queues):
    (tmp_queues / "100.json").write_text("{}", encoding="utf-8")
    (tmp_queues / "200.json").write_text("{}", encoding="utf-8")
    pids = queue_io.all_pids()
    assert set(pids) == {"100", "200"}


def test_all_pids_dir_missing(tmp_path, monkeypatch):
    missing = tmp_path / "nonexistent"
    monkeypatch.setattr(queue_io, "_store", StateStore(state_dir=missing))
    assert queue_io.all_pids() == []


def test_replied_set(tmp_queues):
    data = {"replied": ["msg:123", "2026-03-01 10:00:00"]}
    (tmp_queues / "100.json").write_text(json.dumps(data), encoding="utf-8")
    rs = queue_io.replied_set("100")
    assert "msg:123" in rs


def test_mark_replied_adds_entries(tmp_queues):
    cq = {"pid": "100", "unreplied": [
        {"message_id": 42, "time": "2026-03-01 10:00:00"}
    ], "replied": [], "reply_log": []}
    (tmp_queues / "100.json").write_text(json.dumps(cq), encoding="utf-8")
    queue_io.mark_replied("100", "msg:42", "2026-03-01 10:00:00",
                           {"msg_id": "42", "player": "Alice"})
    result = queue_io.load("100")
    assert "msg:42" in result["replied"]
    assert len(result["unreplied"]) == 0
    assert len(result["reply_log"]) == 1


def test_mark_replied_no_duplicate_keys(tmp_queues):
    cq = {"replied": ["msg:42"], "unreplied": [], "reply_log": []}
    (tmp_queues / "100.json").write_text(json.dumps(cq), encoding="utf-8")
    queue_io.mark_replied("100", "msg:42", None, {"msg_id": "42"})
    result = queue_io.load("100")
    assert result["replied"].count("msg:42") == 1


def test_migrate_from_state(tmp_queues):
    state = {
        "gm_queue_replied": {"100": ["msg:1", "2026-03-01"]},
        "gm_queue": {"100": [{"message_id": 5}]},
        "gm_reply_log": [{"pid": "100", "msg_id": "1"}],
    }
    count = queue_io.migrate_from_state(state)
    assert count == 1
    result = queue_io.load("100")
    assert "msg:1" in result["replied"]


def test_migrate_skips_already_migrated(tmp_queues):
    state = {"gm_queue_replied": {"100": ["msg:1"]}}
    queue_io.migrate_from_state(state)  # first time
    count = queue_io.migrate_from_state(state)  # second time
    assert count == 0



# ═══════════════════════════════════════════════════════════════════════════════
# commands/player_registry.py
