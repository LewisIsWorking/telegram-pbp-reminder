"""Tests for checker.py — quest_clock group.

Extracted from test_checker.py during the test-split refactor (phase 2.3).
Module imports, helpers, and the _LOGS_DIR redirection setup live in
``_test_checker_helpers``.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_quest_add():
    """/quest adds a quest to the campaign."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/quest Find the missing merchant", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    quests = state.get("quests", {}).get("100", [])
    assert len(quests) == 1
    assert quests[0]["text"] == "Find the missing merchant"
    assert quests[0]["status"] == "active"
    assert "📋" in _sent_messages[-1]["text"]

def test_quest_non_gm():
    """/quest from non-GM should be ignored."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/quest Hack the system", user_id=42, first_name="Player")]
    checker.process_updates(updates, config, state)

    quests = state.get("quests", {}).get("100", [])
    assert len(quests) == 0

def test_quests_list():
    """/quests shows active and completed quests."""
    _reset()
    config = _make_config()
    state = _make_state()
    now = datetime.now(timezone.utc).isoformat()
    state["quests"] = {
        "100": [
            {"text": "Find the gem", "status": "active", "created_at": now, "completed_at": None},
            {"text": "Save the prince", "status": "completed", "created_at": now, "completed_at": now},
        ]
    }

    result = checker._build_quests("100", "TestCampaign", state)
    assert "Find the gem" in result
    assert "Save the prince" in result
    assert "1 active" in result
    assert "1 completed" in result

def test_quest_done():
    """/done marks a quest as completed."""
    _reset()
    config = _make_config()
    state = _make_state()
    now = datetime.now(timezone.utc).isoformat()
    state["quests"] = {
        "100": [{"text": "Find the gem", "status": "active", "created_at": now, "completed_at": None}]
    }

    updates = [_make_msg(1, 100, "/done 1", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert state["quests"]["100"][0]["status"] == "completed"
    assert state["quests"]["100"][0]["completed_at"] is not None
    assert "✅" in _sent_messages[-1]["text"]

def test_quest_delete():
    """/delquest removes a quest entirely."""
    _reset()
    config = _make_config()
    state = _make_state()
    now = datetime.now(timezone.utc).isoformat()
    state["quests"] = {
        "100": [{"text": "Find the gem", "status": "active", "created_at": now, "completed_at": None}]
    }

    updates = [_make_msg(1, 100, "/delquest 1", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert len(state["quests"]["100"]) == 0
    assert "🗑️" in _sent_messages[-1]["text"]

def test_quests_empty():
    """/quests with no quests shows helpful message."""
    result = checker._build_quests("100", "TestCampaign", {"quests": {}})
    assert "No quests" in result

def test_clog():
    """/clog adds a combat log entry."""
    _reset()
    config = _make_config()
    state = _make_state()
    now = datetime.now(timezone.utc)
    state["combat"]["100"] = {
        "active": True, "round": 2, "current_phase": "players",
        "players_acted": {}, "last_ping_at": None, "enemies": [],
        "combat_log": [], "campaign_name": "TestCampaign",
        "phase_started_at": now.isoformat(), "started_at": now.isoformat(),
        "all_players_notified": False,
    }

    updates = [_make_msg(1, 100, "/clog The ogre crits Cardigan for 28!", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    log = state["combat"]["100"]["combat_log"]
    assert len(log) == 1
    assert log[0]["round"] == 2
    assert "ogre crits" in log[0]["text"]

def test_clock_create():
    """/clock creates a progress clock."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/clock Investigation 6", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    clocks = state.get("clocks", {}).get("100", {})
    assert "Investigation" in clocks
    assert clocks["Investigation"]["segments"] == 6
    assert clocks["Investigation"]["filled"] == 0
    assert "○" in _sent_messages[-1]["text"]

def test_delclock():
    """/delclock removes a clock."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["clocks"] = {"100": {"Investigation": {"filled": 3, "segments": 6}}}

    updates = [_make_msg(1, 100, "/delclock Investigation", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert "Investigation" not in state["clocks"]["100"]

def test_clocks_list():
    """/clocks shows all clocks."""
    state = {"clocks": {"100": {
        "Investigation": {"filled": 3, "segments": 6},
        "Ritual": {"filled": 4, "segments": 4},
    }}}
    result = checker._build_clocks("100", "TestCampaign", state)
    assert "Investigation" in result
    assert "Ritual" in result
    assert "◉" in result
    assert "✅" in result  # Ritual is complete

def test_clock_non_gm():
    """/clock from non-GM is ignored."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/clock Cheat 6", user_id=42, first_name="Player")]
    checker.process_updates(updates, config, state)

    assert len(state.get("clocks", {}).get("100", {})) == 0

def test_clock_display():
    """Clock display renders correctly."""
    import helpers
    result = helpers.clock_display(3, 6)
    assert "◉◉◉○○○" in result
    assert "3/6" in result

def test_clock_display_full():
    """Full clock is all filled."""
    import helpers
    result = helpers.clock_display(6, 6)
    assert "◉◉◉◉◉◉" in result
    assert "○" not in result
