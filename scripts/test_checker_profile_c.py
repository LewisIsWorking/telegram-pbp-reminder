"""Tests for checker.py — profile (part c) group.

Extracted from test_checker.py during the test-split refactor (phase 2).
Module imports, helpers, and the _LOGS_DIR redirection setup live in
``_test_checker_helpers``.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_delnpc():
    """/delnpc removes an NPC."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["npcs"] = {"100": [
        {"name": "Gorund", "desc": "Blacksmith", "added_at": "2026-02-27T10:00:00+00:00"},
    ]}

    updates = [_make_msg(1, 100, "/delnpc 1", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert len(state["npcs"]["100"]) == 0

def test_npc_non_gm():
    """/npc from non-GM is ignored."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/npc Bad Guy", user_id=42, first_name="Player")]
    checker.process_updates(updates, config, state)

    assert len(state.get("npcs", {}).get("100", [])) == 0
