"""Tests for checker.py — combat (part a) group.

Extracted from test_checker.py during the test-split refactor (phase 2).
Module imports, helpers, and the _LOGS_DIR redirection setup live in
``_test_checker_helpers``.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_handle_round_command():
    _reset()
    state = _make_state()
    checker._handle_round_command("/round 1 players", "100", "Test", "now", -100, 100, state)
    assert "100" in state["combat"]
    assert state["combat"]["100"]["round"] == 1
    assert state["combat"]["100"]["current_phase"] == "players"
    assert len(_sent_messages) == 1
    assert "Round 1" in _sent_messages[0]["text"]

def test_handle_round_command_enemies():
    _reset()
    state = _make_state()
    checker._handle_round_command("/round 2 enemies", "100", "Test", "now", -100, 100, state)
    assert state["combat"]["100"]["current_phase"] == "enemies"

def test_handle_round_command_resets_players_acted():
    _reset()
    state = _make_state()
    state["combat"]["100"] = {
        "active": True, "round": 1, "current_phase": "enemies",
        "players_acted": ["42"], "last_ping_at": None,
        "campaign_name": "Test", "phase_started_at": "now",
    }
    checker._handle_round_command("/round 2 players", "100", "Test", "now", -100, 100, state)
    assert state["combat"]["100"]["players_acted"] == []
    assert state["combat"]["100"]["round"] == 2

def test_handle_combat_message_tracks_player():
    _reset()
    state = _make_state()
    state["combat"]["100"] = {
        "active": True, "round": 1, "current_phase": "players",
        "players_acted": [], "last_ping_at": None,
        "campaign_name": "Test", "phase_started_at": "now",
    }
    checker._handle_combat_message("I attack!", "I attack!", "42", "Player", {"999"}, "100", "Test", "now", -100, 100, state)
    assert "42" in state["combat"]["100"]["players_acted"]

def test_handle_combat_message_gm_not_tracked():
    _reset()
    state = _make_state()
    state["combat"]["100"] = {
        "active": True, "round": 1, "current_phase": "players",
        "players_acted": [], "last_ping_at": None,
        "campaign_name": "Test", "phase_started_at": "now",
    }
    checker._handle_combat_message("narrative text", "narrative text", "999", "GM", {"999"}, "100", "Test", "now", -100, 100, state)
    assert "999" not in state["combat"]["100"]["players_acted"]

def test_handle_combat_endcombat():
    _reset()
    state = _make_state()
    state["combat"]["100"] = {
        "active": True, "round": 1, "current_phase": "players",
        "players_acted": [], "last_ping_at": None,
        "campaign_name": "Test", "phase_started_at": "now",
    }
    checker._handle_combat_message("/endcombat", "/endcombat", "999", "GM", {"999"}, "100", "Test", "now", -100, 100, state)
    assert "100" not in state["combat"]

def test_roll_basic():
    """Basic 1d20 roll."""
    result = helpers.roll_dice("1d20")
    assert result["error"] is None
    assert len(result["results"]) == 1
    r = result["results"][0]
    assert 1 <= r["total"] <= 20
    assert len(r["rolls"]) == 1

def test_roll_with_modifier():
    """1d20+5 adds modifier to total."""
    result = helpers.roll_dice("1d20+5")
    assert result["error"] is None
    r = result["results"][0]
    assert r["modifier"] == 5
    assert r["total"] == r["rolls"][0] + 5

def test_roll_negative_modifier():
    """1d20-3 subtracts modifier."""
    result = helpers.roll_dice("1d20-3")
    assert result["error"] is None
    r = result["results"][0]
    assert r["modifier"] == -3
    assert r["total"] == r["rolls"][0] - 3

def test_roll_multiple_dice():
    """2d6 rolls two dice."""
    result = helpers.roll_dice("2d6")
    assert result["error"] is None
    r = result["results"][0]
    assert len(r["rolls"]) == 2
    assert all(1 <= x <= 6 for x in r["rolls"])
    assert r["total"] == sum(r["rolls"])

def test_roll_keep_highest():
    """4d6kh3 keeps highest 3."""
    result = helpers.roll_dice("4d6kh3")
    assert result["error"] is None
    r = result["results"][0]
    assert len(r["rolls"]) == 4
    assert len(r["kept"]) == 3
    assert r["total"] == sum(r["kept"])
    # Kept should be the 3 highest
    assert sorted(r["kept"], reverse=True) == r["kept"]

def test_roll_keep_lowest():
    """2d20kl1 keeps lowest."""
    result = helpers.roll_dice("2d20kl1")
    assert result["error"] is None
    r = result["results"][0]
    assert len(r["rolls"]) == 2
    assert len(r["kept"]) == 1
    assert r["total"] == min(r["rolls"])

def test_roll_with_label():
    """1d20+12 Stealth extracts label."""
    result = helpers.roll_dice("1d20+12 Stealth")
    assert result["error"] is None
    assert result["label"] == "Stealth"
    assert len(result["results"]) == 1

def test_roll_multiple_expressions():
    """1d20+5 2d6+3 rolls both."""
    result = helpers.roll_dice("1d20+5 2d6+3")
    assert result["error"] is None
    assert len(result["results"]) == 2

def test_roll_no_dice():
    """Invalid expression returns error."""
    result = helpers.roll_dice("hello")
    assert result["error"] is not None

def test_roll_empty():
    """Empty expression returns error."""
    result = helpers.roll_dice("")
    assert result["error"] is not None

def test_roll_command():
    """/roll processes dice and sends result."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/roll 1d20+5 Stealth", user_id=42, first_name="Alice")]
    checker.process_updates(updates, config, state)

    roll_msgs = [m for m in _sent_messages if "🎲" in m.get("text", "")]
    assert len(roll_msgs) >= 1, f"Should send dice result, got: {_sent_messages}"
    assert "Stealth" in roll_msgs[0]["text"]

def test_roll_command_no_args():
    """/roll with no args shows usage."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/roll", user_id=42, first_name="Alice")]
    checker.process_updates(updates, config, state)

    assert any("Usage" in m.get("text", "") for m in _sent_messages)

def test_dc_level():
    """DC lookup for level 5."""
    result = helpers.dc_lookup("5")
    assert "Level 5" in result
    assert "DC 20" in result  # Standard DC for level 5

def test_dc_level_hard():
    """DC lookup for level 5 hard."""
    result = helpers.dc_lookup("5 hard")
    assert "DC 22" in result  # 20 + 2

def test_dc_proficiency():
    """Proficiency DC lookup."""
    result = helpers.dc_lookup("trained")
    assert "15" in result
