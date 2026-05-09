"""Tests for checker.py — misc (part b) group.

Extracted from test_checker.py during the test-split refactor (phase 2.3).
Module imports, helpers, and the _LOGS_DIR redirection setup live in
``_test_checker_helpers``.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_pick_vote():
    """/pick casts a vote."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["votes"] = {"100": {
        "question": "Left or right?",
        "options": ["Left", "Right"],
        "results": {"1": [], "2": []},
        "closed": False,
        "created_at": "2026-02-28T10:00:00+00:00",
    }}

    updates = [_make_msg(1, 100, "/pick 2", user_id=42, first_name="Alice")]
    checker.process_updates(updates, config, state)

    assert "Alice" in state["votes"]["100"]["results"]["2"]
    assert "✅" in _sent_messages[-1]["text"]

def test_pick_changes_vote():
    """/pick changes previous vote."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["votes"] = {"100": {
        "question": "A or B?",
        "options": ["A", "B"],
        "results": {"1": ["Alice"], "2": []},
        "closed": False,
        "created_at": "2026-02-28T10:00:00+00:00",
    }}

    updates = [_make_msg(1, 100, "/pick 2", user_id=42, first_name="Alice")]
    checker.process_updates(updates, config, state)

    assert "Alice" not in state["votes"]["100"]["results"]["1"]
    assert "Alice" in state["votes"]["100"]["results"]["2"]
