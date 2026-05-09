"""Coverage tests extracted from test_zero_coverage.py — bin 5.

Sections in this file:
  - Load diagnostic.py to get the pattern constants
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


# ═══════════════════════════════════════════════════════════════════════════════

import sys as _sys
import importlib as _il
import importlib.util as _ilu

# Load diagnostic.py to get the pattern constants
_d_spec = _ilu.spec_from_file_location(
    "_diag", os.path.join(os.path.dirname(__file__), "scheduled", "diagnostic.py")
)
_diag = _ilu.module_from_spec(_d_spec)

# diagnostic.py imports telegram — patch it before exec
import types as _types
_fake_tg = _types.ModuleType("telegram")
_fake_tg.send_message = lambda *a, **kw: True
_sys.modules.setdefault("telegram", _fake_tg)

_d_spec.loader.exec_module(_diag)

from scheduled.diagnostic_analysis import _analyse_logs, _build_report


def test_analyse_logs_empty():
    result = _analyse_logs([])
    assert result["issues"] == {}
    assert result["events"] == []
    assert result["runs_with_errors"] == 0


def test_analyse_logs_detects_error():
    logs = ["Error processing update 123: something went wrong"]
    result = _analyse_logs(logs)
    assert len(result["issues"]) > 0
    assert result["runs_with_errors"] == 1


def test_analyse_logs_detects_poll_vote():
    logs = ["Poll vote recorded for user 123"]
    result = _analyse_logs(logs)
    assert any("Poll vote" in e or "vote" in e.lower() for e in result["events"])


def test_analyse_logs_detects_potw():
    logs = ["POTW for Kibwe: Alice (W14)"]
    result = _analyse_logs(logs)
    assert any("POTW" in e for e in result["events"])


def test_analyse_logs_detects_unknown_voter():
    logs = ["Unknown voter captured: 123456 in C11"]
    result = _analyse_logs(logs)
    assert any("Unknown voter captured" in e for e in result["events"])


def test_analyse_logs_detects_queue_reminder():
    logs = ["Queue reminder: 15 unreplied (2 msg)"]
    result = _analyse_logs(logs)
    assert any("Queue reminder" in e or "unreplied" in e for e in result["events"])


def test_analyse_logs_strips_timestamp():
    logs = ["2026-03-27T12:00:00Z Error processing update 1: oops"]
    result = _analyse_logs(logs)
    assert result["runs_with_errors"] == 1


def test_build_report_all_clear():
    analysis = {"issues": {}, "events": [], "runs_with_errors": 0}
    now = datetime(2026, 3, 27, tzinfo=timezone.utc)
    result = _build_report(analysis, 24, now)
    assert "All clear" in result
    assert "2026-03-27" in result


def test_build_report_with_issues():
    analysis = {
        "issues": {"Error": ["something broke", "something broke again"]},
        "events": [],
        "runs_with_errors": 3,
    }
    now = datetime(2026, 3, 27, tzinfo=timezone.utc)
    result = _build_report(analysis, 24, now)
    assert "1 issue type" in result
    assert "Error" in result


def test_build_report_with_all_event_types():
    analysis = {
        "issues": {},
        "events": [
            "Poll vote for user X",
            "POTW winner selected",
            "Unknown voter 99 captured",
            "Queue reminder: 5 unreplied (1 msg)",
        ],
        "runs_with_errors": 0,
    }
    now = datetime(2026, 3, 27, tzinfo=timezone.utc)
    result = _build_report(analysis, 24, now)
    assert "Activity" in result


def test_build_report_queue_peak_count():
    analysis = {
        "issues": {},
        "events": [
            "Queue reminder: 15 unreplied (2 msg)",
            "Queue reminder: 8 unreplied (1 msg)",
        ],
        "runs_with_errors": 0,
    }
    now = datetime(2026, 3, 27, tzinfo=timezone.utc)
    result = _build_report(analysis, 24, now)
    assert "15" in result

