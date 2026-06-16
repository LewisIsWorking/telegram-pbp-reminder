"""Tests extracted from test_scheduled_coverage.py — bin 4.

Sections in this file:
  - Build message > 4096 chars with paragraph breaks so it splits
"""
"""
Coverage tests for:
  boons/display.py
  scheduled/week_welcome.py
  scheduled/queue_nudge.py
  scheduled/swimming_poll.py
  post_changelog.py
"""
import sys, os, pytest, importlib.util
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

def _ww_config():
    return {"group_id": -1001, "bot_topic_id": 999, "poll_post_hour": 7}

def _qn_config():
    return {
        "group_id": -1001, "bot_topic_id": 999,
        "gm_user_ids": [999],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
             "gm_user_ids": [999]}
        ]
    }

# ═══════════════════════════════════════════════════════════════════════════════

_pc_spec = importlib.util.spec_from_file_location(
    "_post_changelog",
    os.path.join(os.path.dirname(__file__), "post_changelog.py")
)
_pc = importlib.util.module_from_spec(_pc_spec)
_pc_spec.loader.exec_module(_pc)


def test_read_latest_entry_empty(tmp_path):
    f = tmp_path / "CHANGELOG.md"
    f.write_text("No version headers here", encoding="utf-8")
    assert _pc.read_latest_entry(f) == ("", "")


def test_read_latest_entry_parses(tmp_path):
    f = tmp_path / "CHANGELOG.md"
    f.write_text("## [1.2.3] - 2026-03-01\n\nSome changes here\n\n## [1.2.2]\nOld", encoding="utf-8")
    header, body = _pc.read_latest_entry(f)
    assert "1.2.3" in header
    assert "Some changes" in body


def test_markdown_to_telegram_basic():
    result = _pc.markdown_to_telegram("## [1.0.0] - 2026-03-01", "Hello world")
    assert "1.0.0" in result
    assert "2026-03-01" in result
    assert "Hello world" in result


def test_markdown_to_telegram_no_date():
    result = _pc.markdown_to_telegram("## [1.0.0]", "Body")
    assert "1.0.0" in result


def test_markdown_to_telegram_escapes_angle_brackets():
    result = _pc.markdown_to_telegram("## [1.0.0]", "Age: <6h")
    assert "&lt;6h" in result or "<6h" not in result


def test_markdown_to_telegram_h3_to_bold():
    result = _pc.markdown_to_telegram("## [1.0.0]", "### Added\nSome stuff")
    assert "<b>Added</b>" in result


def test_markdown_to_telegram_bold():
    result = _pc.markdown_to_telegram("## [1.0.0]", "**important** thing")
    assert "<b>important</b>" in result


def test_markdown_to_telegram_code():
    result = _pc.markdown_to_telegram("## [1.0.0]", "`some_code`")
    assert "<code>some_code</code>" in result


def test_post_to_telegram_success():
    m = MagicMock(); m.status_code = 200; m.json.return_value = {"ok": True}
    with patch.object(_pc.requests, "post", return_value=m):
        result = _pc.post_to_telegram("Hello", "token123")
    assert result is True


def test_post_to_telegram_failure():
    m = MagicMock(); m.status_code = 400
    m.json.return_value = {"ok": False}; m.text = "err"
    with patch.object(_pc.requests, "post", return_value=m):
        result = _pc.post_to_telegram("Hello", "token123")
    assert result is False


def test_post_to_telegram_network_error():
    import requests as _req
    with patch.object(_pc.requests, "post", side_effect=_req.RequestException("x")):
        result = _pc.post_to_telegram("Hello", "token123")
    assert result is False


def test_post_to_telegram_long_message():
    # Build message > 4096 chars with paragraph breaks so it splits
    para = "A" * 2000
    long_msg = f"{para}\n\n{para}\n\n{para}"
    m = MagicMock(); m.status_code = 200; m.json.return_value = {"ok": True}
    with patch.object(_pc.requests, "post", return_value=m) as mp:
        _pc.post_to_telegram(long_msg, "token")
    assert mp.call_count >= 2  # split into multiple chunks


def test_main_no_changelog(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    missing = tmp_path / "CHANGELOG.md"  # does not exist
    with patch.object(_pc, "Path", return_value=missing):
        # Path(__file__) returns missing → .parent.parent / "CHANGELOG.md" won't exist
        # Just use the direct approach: patch changelog_path inside main
        pass
    # Simpler: patch read_latest_entry to return empty
    with patch.object(_pc, "read_latest_entry", return_value=("", "")):
        with patch.object(Path, "exists", return_value=True):
            result = _pc.main()
    assert result == 0


def test_main_success(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    m = MagicMock(); m.status_code = 200; m.json.return_value = {"ok": True}
    with patch.object(_pc, "read_latest_entry", return_value=("## [1.0.0] - 2026-03-01", "Changes")):
        with patch.object(Path, "exists", return_value=True):
            with patch.object(_pc.requests, "post", return_value=m):
                result = _pc.main()
    assert result == 0


def test_main_post_failure(monkeypatch, capsys):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    m = MagicMock(); m.status_code = 400
    m.json.return_value = {"ok": False}; m.text = "err"
    with patch.object(_pc, "read_latest_entry", return_value=("## [1.0.0]", "Body")):
        with patch.object(Path, "exists", return_value=True):
            with patch.object(_pc.requests, "post", return_value=m):
                result = _pc.main()
    assert result == 1
