"""Tests extracted from test_commands_coverage.py - bin 4.

Sections in this file:
  - Still "2026-04-03" - not run again
"""
"""
Coverage tests for:
  commands/queue_io.py
  commands/player_registry.py
  scheduled/poll_result.py
  scheduled/diagnostic.py
  scheduled/reports.py  (partial - tg-calling functions mocked)
"""
import sys, os, json, pytest, tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

@pytest.fixture
def tmp_queues(tmp_path, monkeypatch):
    """Redirect queue_io file operations to a temp directory."""
    monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path)
    return tmp_path

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

from scheduled.diagnostic import run_daily_diagnostic, _gh_request, _fetch_run_log


def test_diagnostic_skips_wrong_hour():
    # ⛔ Was hour 10, written when the gate was ``now.hour != 8``. Since
    # scheduled/due.py (2026-09-06) a late hour is a catch-up run, so hour
    # 10 went on to call the REAL GitHub API and the result depended on
    # whether GitHub answered. Before the hour is the only wrong hour now.
    config = {"group_id": -1, "bot_topic_id": 999, "diagnostic_hour": 8}
    now = datetime(2026, 4, 3, 7, 59, tzinfo=timezone.utc)
    state = {}
    with patch("scheduled.diagnostic._gh_request") as gh:
        run_daily_diagnostic(config, state, now=now)
    gh.assert_not_called()
    assert "last_diagnostic" not in state


def test_diagnostic_catches_up_after_its_hour():
    """A run at 10:00 still does the 08:00 diagnostic (see scheduled/due.py)."""
    config = {"group_id": -1, "bot_topic_id": 999, "diagnostic_hour": 8}
    now = datetime(2026, 4, 3, 10, tzinfo=timezone.utc)
    recent_run = {"created_at": "2026-04-03T09:00:00Z", "id": 1}
    state = {}
    with patch("scheduled.diagnostic._gh_request",
               return_value={"workflow_runs": [recent_run]}), \
         patch("scheduled.diagnostic._fetch_run_log", return_value=""):
        run_daily_diagnostic(config, state, now=now)
    assert state.get("last_diagnostic") == "2026-04-03"


def test_diagnostic_skips_already_run():
    config = {"group_id": -1, "bot_topic_id": 999, "diagnostic_hour": 8}
    now = datetime(2026, 4, 3, 8, tzinfo=timezone.utc)
    state = {"last_diagnostic": "2026-04-03"}
    run_daily_diagnostic(config, state, now=now)
    # Still "2026-04-03" - not run again
    assert state["last_diagnostic"] == "2026-04-03"


def test_diagnostic_skips_no_bot_topic():
    config = {"group_id": -1, "diagnostic_hour": 8}
    now = datetime(2026, 4, 3, 8, tzinfo=timezone.utc)
    state = {}
    run_daily_diagnostic(config, state, now=now)
    assert "last_diagnostic" not in state


def test_diagnostic_skips_no_gh_data():
    config = {"group_id": -1, "bot_topic_id": 999, "diagnostic_hour": 8}
    now = datetime(2026, 4, 3, 8, tzinfo=timezone.utc)
    state = {}
    with patch("scheduled.diagnostic._gh_request", return_value=None):
        run_daily_diagnostic(config, state, now=now)
    assert "last_diagnostic" not in state


def test_diagnostic_skips_no_recent_runs():
    config = {"group_id": -1, "bot_topic_id": 999, "diagnostic_hour": 8}
    now = datetime(2026, 4, 3, 8, tzinfo=timezone.utc)
    old_run = {"created_at": "2026-04-01T00:00:00Z", "id": 1}
    with patch("scheduled.diagnostic._gh_request", return_value={"workflow_runs": [old_run]}):
        run_daily_diagnostic({"group_id": -1, "bot_topic_id": 999, "diagnostic_hour": 8}, {}, now=now)


def test_diagnostic_runs_and_posts():
    config = {"group_id": -1, "bot_topic_id": 999, "diagnostic_hour": 8}
    now = datetime(2026, 4, 3, 8, tzinfo=timezone.utc)
    recent_run = {"created_at": "2026-04-03T07:00:00Z", "id": 123}
    state = {}
    with patch("scheduled.diagnostic._gh_request", return_value={"workflow_runs": [recent_run]}):
        with patch("scheduled.diagnostic._fetch_run_log", return_value="State loaded from files"):
            run_daily_diagnostic(config, state, now=now)
    assert state.get("last_diagnostic") == "2026-04-03"


def test_gh_request_success():
    m = MagicMock()
    m.read.return_value = json.dumps({"ok": True}).encode()
    with patch("scheduled.diagnostic.urllib.request.urlopen", return_value=m):
        result = _gh_request("/repos/x")
    assert result == {"ok": True}


def test_gh_request_error():
    with patch("scheduled.diagnostic.urllib.request.urlopen", side_effect=Exception("x")):
        assert _gh_request("/repos/x") is None


def test_fetch_run_log_success():
    import zipfile, io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("0_check-inactivity.txt", "State loaded")
    buf.seek(0)
    m = MagicMock(); m.read.return_value = buf.read()
    with patch("scheduled.diagnostic.urllib.request.urlopen", return_value=m):
        result = _fetch_run_log(123)
    assert "State loaded" in result


def test_fetch_run_log_error():
    with patch("scheduled.diagnostic.urllib.request.urlopen", side_effect=Exception("x")):
        result = _fetch_run_log(123)
    assert result == ""

