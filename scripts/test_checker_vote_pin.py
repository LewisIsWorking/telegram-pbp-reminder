"""Tests for checker.py — vote_pin group.

Extracted from test_checker.py during the test-split refactor (phase 2.3).
Module imports, helpers, and the _LOGS_DIR redirection setup live in
``_test_checker_helpers``.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_pin_add():
    """/pin adds a bookmark."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/pin The dragon revealed its weakness", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    pins = state.get("pins", {}).get("100", [])
    assert len(pins) == 1
    assert pins[0]["text"] == "The dragon revealed its weakness"
    assert pins[0]["author"] == "GM"
    assert "📌" in _sent_messages[-1]["text"]

def test_pin_non_gm():
    """/pin from non-GM is ignored."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/pin some note", user_id=42, first_name="Player")]
    checker.process_updates(updates, config, state)

    pins = state.get("pins", {}).get("100", [])
    assert len(pins) == 0

def test_pins_list():
    """/pins shows all bookmarks."""
    state = {"pins": {"100": [
        {"text": "Found the key", "created_at": "2026-02-27T10:00:00+00:00", "author": "GM"},
        {"text": "Met the dragon", "created_at": "2026-02-28T10:00:00+00:00", "author": "GM"},
    ]}}
    result = checker._build_pins("100", "TestCampaign", state)
    assert "Found the key" in result
    assert "Met the dragon" in result
    assert "2/30 pins" in result

def test_delpin():
    """/delpin removes a pin."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["pins"] = {"100": [
        {"text": "Pin one", "created_at": "2026-02-27T10:00:00+00:00", "author": "GM"},
    ]}

    updates = [_make_msg(1, 100, "/delpin 1", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert len(state["pins"]["100"]) == 0
    assert "🗑️" in _sent_messages[-1]["text"]

def test_vote_start():
    """/vote creates a vote with options."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/vote Where next? | North | South | Stay", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    vote = state.get("votes", {}).get("100")
    assert vote is not None
    assert vote["question"] == "Where next?"
    assert vote["options"] == ["North", "South", "Stay"]
    assert not vote["closed"]
    assert "🗳️" in _sent_messages[-1]["text"]

def test_vote_too_few_options():
    """/vote with only 1 option rejected."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/vote Bad vote | Only one", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert "100" not in state.get("votes", {})

def test_endvote():
    """/endvote closes and shows results."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["votes"] = {"100": {
        "question": "A or B?",
        "options": ["A", "B"],
        "results": {"1": ["Alice", "Bob"], "2": ["Charlie"]},
        "closed": False,
        "created_at": "2026-02-28T10:00:00+00:00",
    }}

    updates = [_make_msg(1, 100, "/endvote", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert state["votes"]["100"]["closed"]
    last = _sent_messages[-1]["text"]
    assert "Winner" in last or "Tied" in last
    assert "A" in last

def test_showvote():
    """/showvote displays current vote."""
    state = {"votes": {"100": {
        "question": "Go where?",
        "options": ["Left", "Right"],
        "results": {"1": ["Alice"], "2": []},
        "closed": False,
    }}}
    result = checker._build_vote("100", "TestCampaign", state)
    assert "Go where?" in result
    assert "Left" in result
    assert "Alice" in result

def test_vote_non_gm():
    """/vote from non-GM is ignored."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/vote Cheat? | Yes | No", user_id=42, first_name="Player")]
    checker.process_updates(updates, config, state)

    assert "100" not in state.get("votes", {})
