"""Coverage tests for state.py file-I/O paths."""
import sys, os, json, pytest, tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.dirname(__file__))

# ═══════════════════════════════════════════════════════════════════════════════
# state.py — gist and file I/O paths
# ═══════════════════════════════════════════════════════════════════════════════

import state as st


def test_load_falls_back_to_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(st, "_loaded_ok", False)
    with patch.object(st, "_load_from_files", return_value=None):
        with patch.object(st, "gist_load", return_value=None):
            result = st.load()
    assert "offset" in result


def test_save_refuses_if_not_loaded():
    with patch.object(st, "_loaded_ok", False):
        with patch.object(st, "_save_to_files") as mock_files:
            st.save({})
            mock_files.assert_not_called()


def test_load_from_files_missing_core(tmp_path):
    with patch.object(st, "_state_dir", return_value=tmp_path):
        result = st._load_from_files()
    assert result is None


def test_load_from_files_json_error(tmp_path):
    # Create all core partition files but one is corrupt
    for p in ["live", "players", "queue", "activity"]:
        (tmp_path / f"{p}.json").write_text("{}")
    (tmp_path / "live.json").write_text("not json")
    with patch.object(st, "_state_dir", return_value=tmp_path):
        result = st._load_from_files()
    assert result is None


def test_save_to_files(tmp_path):
    with patch.object(st, "_state_dir", return_value=tmp_path):
        with patch.object(st, "gist_save"):
            with patch.object(st, "_loaded_ok", True):
                st.save({"offset": 99, "players": {}})
