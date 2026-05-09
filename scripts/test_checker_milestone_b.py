"""Tests for checker.py — milestone (part b) group.

Extracted from test_checker.py during the test-split refactor. Module
imports, helper functions (_make_config, _make_state, _make_msg, _utc,
_reset, _run_all), and the _LOGS_DIR redirection setup all live in the
shared ``_test_checker_helpers`` module so this file contains test
functions only.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_milestone_messages_milestone_missing_uses_generic():
    """Thread is in JSON but milestone key missing — falls back to generic."""
    from scheduled.message_milestones import _MilestoneMessages, _build_msg
    _MilestoneMessages.reset()
    _MilestoneMessages._data = {"66154": {"1000": "Different milestone."}}
    msg = _build_msg("66154", "Riddleport PBP", "🎯", 500)
    assert "collaborative storytelling" in msg
    _MilestoneMessages.reset()

def test_milestone_messages_dir_not_found():
    """Missing data directory → falls back to empty dict gracefully."""
    from unittest.mock import patch
    from scheduled.message_milestones import _MilestoneMessages
    _MilestoneMessages.reset()
    with patch("os.path.isdir", return_value=False):
        result = _MilestoneMessages.get("66154", 500)
    assert result is None
    _MilestoneMessages.reset()

def test_milestone_messages_json_decode_error():
    """Corrupt JSON file in directory → skipped gracefully."""
    from unittest.mock import patch, mock_open
    from scheduled.message_milestones import _MilestoneMessages
    _MilestoneMessages.reset()
    with patch("os.path.isdir", return_value=True), \
         patch("os.listdir", return_value=["bad.json"]), \
         patch("builtins.open", mock_open(read_data="not-json")):
        result = _MilestoneMessages.get("66154", 500)
    assert result is None
    _MilestoneMessages.reset()

def test_milestone_messages_file_not_found():
    """FileNotFoundError for a file in directory → skipped gracefully."""
    from unittest.mock import patch
    from scheduled.message_milestones import _MilestoneMessages
    _MilestoneMessages.reset()
    with patch("os.path.isdir", return_value=True), \
         patch("os.listdir", return_value=["c00.json"]), \
         patch("builtins.open", side_effect=FileNotFoundError):
        result = _MilestoneMessages.get("66154", 500)
    assert result is None
    _MilestoneMessages.reset()

def test_milestone_messages_non_json_file_skipped():
    """Non-.json files in the directory are ignored."""
    import json as _json
    from unittest.mock import patch, mock_open
    from scheduled.message_milestones import _MilestoneMessages
    _MilestoneMessages.reset()
    with patch("os.path.isdir", return_value=True), \
         patch("os.listdir", return_value=["README.md", "c00.json"]), \
         patch("builtins.open", mock_open(
             read_data=_json.dumps({"66154": {"500": "found"}}))):
        result = _MilestoneMessages.get("66154", 500)
    assert result == "found"
    _MilestoneMessages.reset()

def test_milestone_messages_multiple_files_merged():
    """Multiple JSON files in directory are merged together."""
    import json as _json
    import io as _io
    from unittest.mock import patch
    from scheduled.message_milestones import _MilestoneMessages
    _MilestoneMessages.reset()
    file_data = {
        "c00.json": _json.dumps({"66154": {"500": "riddleport"}}),
        "c01.json": _json.dumps({"25059": {"500": "doomsday"}}),
    }

    def fake_open(path, **kw):
        import os as _os
        fname = _os.path.basename(path)
        return _io.StringIO(file_data[fname])

    with patch("os.path.isdir", return_value=True), \
         patch("os.listdir", return_value=list(file_data.keys())), \
         patch("builtins.open", side_effect=fake_open):
        assert _MilestoneMessages.get("66154", 500) == "riddleport"
        assert _MilestoneMessages.get("25059", 500) == "doomsday"
    _MilestoneMessages.reset()

def test_milestone_messages_cached_after_first_load():
    """Second call to _load() returns cached data without re-reading files."""
    from scheduled.message_milestones import _MilestoneMessages
    _MilestoneMessages.reset()
    # Inject data directly to simulate a loaded state
    _MilestoneMessages._data = {"66154": {"500": "cached"}}
    result = _MilestoneMessages.get("66154", 500)
    assert result == "cached"
    _MilestoneMessages.reset()

def test_milestone_specific_body_appears_in_sent_message():
    """End-to-end: specific body from patched JSON appears in Telegram send."""
    from unittest.mock import patch
    from scheduled.message_milestones import _MilestoneMessages
    _reset()
    _MilestoneMessages.reset()
    _MilestoneMessages._data = {"100": {"500": "Custom Riddleport body."}}
    config = _make_config()
    state = _make_state()
    state["thread_message_counts"] = {"100": {"42": 300, "50": 200}}
    state["celebrated_milestones"] = {}

    checker.check_message_milestones(config, state)

    assert any("Custom Riddleport body." in m.get("text", "") for m in _sent_messages)
    _MilestoneMessages.reset()
