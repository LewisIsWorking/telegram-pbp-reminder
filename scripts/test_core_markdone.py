"""Coverage tests for commands/markdone.py."""
import sys, os, json, pytest, tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.dirname(__file__))

# ═══════════════════════════════════════════════════════════════════════════════
# commands/markdone.py
# ═══════════════════════════════════════════════════════════════════════════════

from commands.markdone import handle_markdone, _clear_entries, _clear_by_msg_id


def _md_ctx(text="/markdone", uid="GM1", entries=None):
    return {
        "cmd_word": text.split()[0],
        "text": text,
        "user_id": uid,
        "gm_ids": {"GM1"},
        "pid": "100",
        "group_id": -1,
        "thread_id": 999,
        "state": {},
        "config": {"group_id": -1, "gm_user_ids": [1]},
        "campaign_name": "Kibwe",
    }


def test_markdone_wrong_cmd():
    ctx = _md_ctx("/queue")
    assert handle_markdone(ctx) is False


def test_markdone_non_gm():
    ctx = _md_ctx(uid="U99")
    assert handle_markdone(ctx) is False


@patch("commands.markdone.scan_transcripts", return_value={})
def test_markdone_no_entries(mock_scan):
    ctx = _md_ctx()
    assert handle_markdone(ctx) is True


@patch("commands.markdone.scan_transcripts")
def test_markdone_all(mock_scan):
    mock_scan.return_value = {"100": {"entries": [
        {"message_id": "1", "time": "2026-03-01 10:00:00", "name": "Alice", "preview": "hi"},
        {"message_id": "2", "time": "2026-03-02 10:00:00", "name": "Bob", "preview": "yo"},
    ]}}
    ctx = _md_ctx("/markdone all")
    assert handle_markdone(ctx) is True


@patch("commands.markdone.scan_transcripts")
def test_markdone_by_position(mock_scan):
    mock_scan.return_value = {"100": {"entries": [
        {"message_id": "42", "time": "2026-03-01 10:00:00", "name": "Alice", "preview": "hi"},
    ]}}
    ctx = _md_ctx("/markdone 1")
    assert handle_markdone(ctx) is True


@patch("commands.markdone.scan_transcripts")
def test_markdone_position_out_of_range(mock_scan):
    mock_scan.return_value = {"100": {"entries": [
        {"message_id": "42", "time": "2026-03-01 10:00:00", "name": "Alice", "preview": "hi"},
    ]}}
    ctx = _md_ctx("/markdone 99")
    assert handle_markdone(ctx) is True


@patch("commands.markdone._clear_by_msg_id", return_value=True)
@patch("commands.markdone.scan_transcripts")
def test_markdone_by_msg_id_fallback(mock_scan, mock_clear):
    mock_scan.return_value = {"100": {"entries": []}}
    ctx = _md_ctx("/markdone 140368")
    assert handle_markdone(ctx) is True


@patch("commands.markdone._clear_by_msg_id", return_value=False)
@patch("commands.markdone.scan_transcripts")
def test_markdone_by_msg_id_not_found(mock_scan, mock_clear):
    mock_scan.return_value = {"100": {"entries": []}}
    ctx = _md_ctx("/markdone 140368")
    assert handle_markdone(ctx) is True


@patch("commands.markdone.scan_transcripts")
def test_markdone_url_extracts_id(mock_scan):
    mock_scan.return_value = {"100": {"entries": []}}
    ctx = _md_ctx("/markdone https://t.me/Path_Wars/40585/140368")
    with patch("commands.markdone._clear_by_msg_id", return_value=True):
        handle_markdone(ctx)


@patch("commands.markdone.scan_transcripts")
def test_markdone_no_arg_shows_usage(mock_scan):
    """No argument shows usage message and clears nothing."""
    mock_scan.return_value = {"100": {"entries": [
        {"message_id": "1", "time": "2026-03-01 10:00:00", "name": "Alice", "preview": "hi"},
    ]}}
    ctx = _md_ctx("/markdone")
    sent = []
    with patch("commands.markdone.tg.send_message", side_effect=lambda g,t,m: sent.append(m)):
        result = handle_markdone(ctx)
    assert result is True
    assert any("markdone" in m.lower() or "tip" in m.lower() or "usage" in m.lower() for m in sent), "Expected usage message"
    # Nothing should have been cleared
    assert mock_scan.call_count >= 1


@patch("commands.markdone.scan_transcripts")
def test_markdone_invalid_arg(mock_scan):
    mock_scan.return_value = {"100": {"entries": [
        {"message_id": "1", "time": "2026-03-01 10:00:00", "name": "Alice", "preview": "hi"},
    ]}}
    ctx = _md_ctx("/markdone notanumber")
    assert handle_markdone(ctx) is True


def test_clear_entries(tmp_path, monkeypatch):
    from commands import queue_io
    monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path)
    entries = [{"message_id": "42", "time": "2026-03-01 10:00:00",
                "name": "Alice", "preview": "hi"}]
    now = datetime(2026, 3, 27, tzinfo=timezone.utc)
    count = _clear_entries(entries, "100", {}, now)
    assert count == 1


def test_clear_by_msg_id_found(tmp_path, monkeypatch):
    from commands import queue_io
    monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path)
    cq = {"unreplied": [{"message_id": 42, "time": "2026-03-01 10:00:00",
                          "user_name": "Alice", "preview": "hi"}],
          "replied": [], "reply_log": []}
    (tmp_path / "100.json").write_text(json.dumps(cq), encoding="utf-8")
    now = datetime(2026, 3, 27, tzinfo=timezone.utc)
    result = _clear_by_msg_id("42", "100", {}, now)
    assert result is True


def test_clear_by_msg_id_not_found(tmp_path, monkeypatch):
    from commands import queue_io
    monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path)
    now = datetime(2026, 3, 27, tzinfo=timezone.utc)
    result = _clear_by_msg_id("99999", "100", {}, now)
    assert result is False
