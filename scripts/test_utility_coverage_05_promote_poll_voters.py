"""Tests extracted from test_utility_coverage.py — bin 5.

Sections in this file:
  - promote_poll_voters.py  — test helper functions
"""
"""
Coverage tests for:
  migrate_gist_to_files.py
  promote_poll_voters.py
  scheduled/session_poll_build.py
  scheduled/state_backup.py
  helpers_pkg/groups.py
"""
import sys, os, json, pytest, tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

import importlib.util as _ilu

def _g_config():
    return {
        "group_id": -1001,
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C00", "name": "R"},
            {"pbp_topic_ids": [101], "code": "C01", "name": "D",
             "group_id": -2002, "linked_polls": ["C11"]},
        ]
    }

def _now():
    return datetime(2026, 4, 3, 12, 0, tzinfo=timezone.utc)  # Friday

# ═══════════════════════════════════════════════════════════════════════════════
# promote_poll_voters.py  — test helper functions
# ═══════════════════════════════════════════════════════════════════════════════

_ppv_spec = _ilu.spec_from_file_location(
    "_promote",
    os.path.join(os.path.dirname(__file__), "promote_poll_voters.py")
)
_ppv = _ilu.module_from_spec(_ppv_spec)
_ppv_spec.loader.exec_module(_ppv)


def test_is_placeholder_true():
    assert _ppv._is_placeholder(9000000000) is True
    assert _ppv._is_placeholder(9000000050) is True
    assert _ppv._is_placeholder(9000000099) is True


def test_is_placeholder_false():
    assert _ppv._is_placeholder(123456789) is False
    assert _ppv._is_placeholder(9000000100) is False


def test_promote_replaces_id():
    pair = {
        "poll_user_ids": [9000000000, 123],
        "poll_user_names": {"9000000000": "alice"}
    }
    _ppv._promote(pair, "9000000000", "999888777", "alice")
    assert 999888777 in pair["poll_user_ids"]
    assert 9000000000 not in pair["poll_user_ids"]
    assert "999888777" in pair["poll_user_names"]
    assert "9000000000" not in pair["poll_user_names"]


def test_main_no_unknown_voters(tmp_path, capsys):
    config = {"topic_pairs": []}
    state = {"poll_unknown_voters": {}}
    cfg_file = tmp_path / "config.json"
    st_file = tmp_path / "live.json"
    cfg_file.write_text(json.dumps(config), encoding="utf-8")
    st_file.write_text(json.dumps(state), encoding="utf-8")
    with patch.object(_ppv, "CONFIG", cfg_file):
        with patch.object(_ppv, "STATE", st_file):
            with patch("sys.argv", ["promote_poll_voters.py"]):
                _ppv.main()
    out = capsys.readouterr().out
    assert "nothing to promote" in out.lower() or "No unknown" in out


def test_main_dry_run(tmp_path, capsys):
    config = {"topic_pairs": [
        {"pbp_topic_ids": [100], "code": "C11",
         "poll_user_ids": [9000000000], "poll_user_names": {"9000000000": "alice"},
         "poll_options": ["Mon", "Tue"]}
    ]}
    state = {
        "poll_unknown_voters": {"C11": ["999888777"]},
        "session_poll": {"C11": {"votes": {"0": ["999888777"]}}},
    }
    cfg_file = tmp_path / "config.json"
    st_file = tmp_path / "live.json"
    cfg_file.write_text(json.dumps(config), encoding="utf-8")
    st_file.write_text(json.dumps(state), encoding="utf-8")
    with patch.object(_ppv, "CONFIG", cfg_file):
        with patch.object(_ppv, "STATE", st_file):
            with patch("sys.argv", ["promote_poll_voters.py"]):
                _ppv.main()
    out = capsys.readouterr().out
    assert "Dry run" in out
