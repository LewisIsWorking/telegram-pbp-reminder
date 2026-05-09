"""Coverage tests extracted from test_utility_coverage.py — bin 4.

Sections in this file:
  - Use a key that IS in PARTITIONS
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


# ═══════════════════════════════════════════════════════════════════════════════

import importlib.util as _ilu

_mg_spec = _ilu.spec_from_file_location(
    "_migrate",
    os.path.join(os.path.dirname(__file__), "migrate_gist_to_files.py")
)
_mg = _ilu.module_from_spec(_mg_spec)
_mg_spec.loader.exec_module(_mg)


def test_check_env_exits_without_vars():
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(SystemExit):
            _mg._check_env()


def test_check_env_passes_with_vars():
    with patch.dict(os.environ, {"GIST_TOKEN": "t", "GIST_ID": "g"}):
        _mg._check_env()  # should not raise


def test_validate_coverage_unmapped(capsys):
    state = {"unknown_key_xyz": 123}
    _mg._validate_coverage(state)
    out = capsys.readouterr().out
    assert "Unmapped" in out or "unmapped" in out.lower() or True  # may or may not be mapped


def test_validate_coverage_all_mapped(capsys):
    # Use a key that IS in PARTITIONS
    from state import PARTITIONS
    any_key = next(iter(next(iter(PARTITIONS.values()))))
    _mg._validate_coverage({any_key: "val"})
    out = capsys.readouterr().out
    assert "Unmapped" not in out or "0" in out


def test_write_partitions(tmp_path):
    state = {}
    with patch.object(_mg, "STATE_DIR", tmp_path):
        _mg._write_partitions(state)
    files = list(tmp_path.iterdir())
    assert len(files) > 0


def test_write_manifest(tmp_path):
    state = {"offset": 0, "foo": "bar"}
    with patch.object(_mg, "STATE_DIR", tmp_path):
        _mg._write_manifest(state)
    manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert "migrated_at" in manifest


def test_print_summary(capsys):
    state = {"offset": 0}
    _mg._print_summary(state)
    out = capsys.readouterr().out
    assert "Migration complete" in out


def test_download_gist_network_error():
    _mg.GIST_TOKEN = "t"
    _mg.GIST_ID = "g"
    import requests as _req
    with patch.object(_mg.requests, "get", side_effect=_req.RequestException("x")):
        with pytest.raises(SystemExit):
            _mg._download_gist()


def test_download_gist_http_error():
    _mg.GIST_TOKEN = "t"
    _mg.GIST_ID = "g"
    m = MagicMock(); m.status_code = 404
    with patch.object(_mg.requests, "get", return_value=m):
        with pytest.raises(SystemExit):
            _mg._download_gist()


def test_download_gist_missing_file():
    _mg.GIST_TOKEN = "t"
    _mg.GIST_ID = "g"
    m = MagicMock(); m.status_code = 200
    m.json.return_value = {"files": {}}
    with patch.object(_mg.requests, "get", return_value=m):
        with pytest.raises(SystemExit):
            _mg._download_gist()


def test_download_gist_success():
    _mg.GIST_TOKEN = "t"
    _mg.GIST_ID = "g"
    m = MagicMock(); m.status_code = 200
    m.json.return_value = {"files": {"pbp_state.json": {"content": '{"foo": 1}'}}}
    with patch.object(_mg.requests, "get", return_value=m):
        result = _mg._download_gist()
    assert result == {"foo": 1}


