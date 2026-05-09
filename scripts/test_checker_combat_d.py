"""Tests for checker.py — combat (part d) group.

Extracted from test_checker.py during the test-split refactor (phase 2).
Module imports, helpers, and the _LOGS_DIR redirection setup live in
``_test_checker_helpers``.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_hp_non_gm_view():
    """/hp from non-GM shows tracker (read-only)."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["hp_tracker"] = {"100": {"Ogre": {"current": 45, "max": 45}}}

    updates = [_make_msg(1, 100, "/hp", user_id=42, first_name="Player")]
    checker.process_updates(updates, config, state)

    hp_msgs = [m for m in _sent_messages if "Ogre" in m.get("text", "")]
    assert len(hp_msgs) >= 1

def test_hp_no_heal_over_max():
    """/hp h doesn't overheal past max."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["hp_tracker"] = {"100": {"Ogre": {"current": 40, "max": 45}}}

    updates = [_make_msg(1, 100, "/hp h Ogre 100", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert state["hp_tracker"]["100"]["Ogre"]["current"] == 45

def test_tick():
    """/tick advances a clock."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["clocks"] = {"100": {"Investigation": {"filled": 2, "segments": 6}}}

    updates = [_make_msg(1, 100, "/tick Investigation", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert state["clocks"]["100"]["Investigation"]["filled"] == 3

def test_tick_amount():
    """/tick with amount advances multiple segments."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["clocks"] = {"100": {"Investigation": {"filled": 1, "segments": 6}}}

    updates = [_make_msg(1, 100, "/tick Investigation 3", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert state["clocks"]["100"]["Investigation"]["filled"] == 4

def test_tick_complete():
    """/tick that completes a clock shows COMPLETE."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["clocks"] = {"100": {"Investigation": {"filled": 5, "segments": 6}}}

    updates = [_make_msg(1, 100, "/tick Investigation", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert state["clocks"]["100"]["Investigation"]["filled"] == 6
    assert "COMPLETE" in _sent_messages[-1]["text"]

def test_untick():
    """/untick reverses a clock."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["clocks"] = {"100": {"Investigation": {"filled": 3, "segments": 6}}}

    updates = [_make_msg(1, 100, "/untick Investigation", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert state["clocks"]["100"]["Investigation"]["filled"] == 2

def test_hp_bar():
    """HP bar renders correctly."""
    import helpers
    result = helpers.hp_bar(30, 45, 10)
    assert "30/45" in result
    assert "█" in result
    assert "░" in result

def test_hp_bar_full():
    """Full HP bar is all filled."""
    import helpers
    result = helpers.hp_bar(100, 100, 10)
    assert "100/100" in result
    assert "░" not in result

def test_hp_bar_empty():
    """Empty HP bar is all empty."""
    import helpers
    result = helpers.hp_bar(0, 100, 10)
    assert "0/100" in result
    assert "█" not in result
