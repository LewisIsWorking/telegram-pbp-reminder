"""Tests for checker.py — combat (part c) group.

Extracted from test_checker.py during the test-split refactor (phase 2).
Module imports, helpers, and the _LOGS_DIR redirection setup live in
``_test_checker_helpers``.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_combatlog_view():
    """/combatlog shows the log."""
    state = {"combat": {"100": {
        "active": True, "round": 3, "current_phase": "players",
        "combat_log": [
            {"round": 1, "text": "Combat begins!", "at": "2026-02-28T10:00:00+00:00"},
            {"round": 2, "text": "Ogre drops to 0 HP", "at": "2026-02-28T11:00:00+00:00"},
        ],
        "phase_started_at": "2026-02-28T12:00:00+00:00",
    }}}
    result = checker._build_combatlog("100", "TestCampaign", state)
    assert "Combat begins!" in result
    assert "Ogre drops" in result
    assert "R1:" in result
    assert "R2:" in result

def test_enemies_set():
    """/enemies sets enemy roster mid-combat."""
    _reset()
    config = _make_config()
    state = _make_state()
    now = datetime.now(timezone.utc)
    state["combat"]["100"] = {
        "active": True, "round": 1, "current_phase": "players",
        "players_acted": {}, "last_ping_at": None, "enemies": [],
        "combat_log": [], "campaign_name": "TestCampaign",
        "phase_started_at": now.isoformat(), "started_at": now.isoformat(),
        "all_players_notified": False,
    }

    updates = [_make_msg(1, 100, "/enemies Dragon, 3 Kobolds", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert state["combat"]["100"]["enemies"] == ["Dragon", "3 Kobolds"]

def test_endcombat_summary():
    """/endcombat shows combat log summary."""
    _reset()
    config = _make_config()
    state = _make_state()
    now = datetime.now(timezone.utc)
    state["combat"]["100"] = {
        "active": True, "round": 3, "current_phase": "enemies",
        "players_acted": {}, "last_ping_at": None, "enemies": ["Ogre"],
        "combat_log": [
            {"round": 1, "text": "Combat begins!", "at": now.isoformat()},
            {"round": 3, "text": "Ogre falls!", "at": now.isoformat()},
        ],
        "campaign_name": "TestCampaign",
        "phase_started_at": now.isoformat(), "started_at": now.isoformat(),
        "all_players_notified": False,
    }

    updates = [_make_msg(1, 100, "/endcombat", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    end_msgs = [m for m in _sent_messages if "Combat ended" in m.get("text", "")]
    assert len(end_msgs) >= 1
    assert "3 rounds" in end_msgs[0]["text"]
    assert "Ogre falls!" in end_msgs[0]["text"]
    assert "100" not in state["combat"]

def test_whosturn_with_enemies():
    """/whosturn shows enemy roster."""
    now = datetime.now(timezone.utc)
    state = _make_state()
    state["combat"]["100"] = {
        "active": True, "round": 1, "current_phase": "players",
        "players_acted": {}, "last_ping_at": None,
        "enemies": ["Ogre", "2 Skeletons"],
        "combat_log": [], "campaign_name": "TestCampaign",
        "phase_started_at": (now - timedelta(hours=1)).isoformat(),
        "started_at": now.isoformat(), "all_players_notified": False,
    }
    result = checker._build_whosturn("100", "TestCampaign", state)
    assert "Ogre" in result
    assert "2 Skeletons" in result

def test_hp_set():
    """/hp set creates an HP entry."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/hp set Ogre 45/45", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    hp = state.get("hp_tracker", {}).get("100", {})
    assert "Ogre" in hp
    assert hp["Ogre"]["current"] == 45
    assert hp["Ogre"]["max"] == 45
    assert "█" in _sent_messages[-1]["text"]

def test_hp_damage():
    """/hp d deals damage."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["hp_tracker"] = {"100": {"Ogre": {"current": 45, "max": 45}}}

    updates = [_make_msg(1, 100, "/hp d Ogre 12", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert state["hp_tracker"]["100"]["Ogre"]["current"] == 33
    assert "12 damage" in _sent_messages[-1]["text"]

def test_hp_heal():
    """/hp h heals."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["hp_tracker"] = {"100": {"Ogre": {"current": 20, "max": 45}}}

    updates = [_make_msg(1, 100, "/hp h Ogre 10", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert state["hp_tracker"]["100"]["Ogre"]["current"] == 30
    assert "healed" in _sent_messages[-1]["text"]

def test_hp_kill():
    """/hp d that kills shows DOWN."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["hp_tracker"] = {"100": {"Ogre": {"current": 5, "max": 45}}}

    updates = [_make_msg(1, 100, "/hp d Ogre 20", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert state["hp_tracker"]["100"]["Ogre"]["current"] == 0
    assert "DOWN" in _sent_messages[-1]["text"]

def test_hp_remove():
    """/hp remove removes an entry."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["hp_tracker"] = {"100": {"Ogre": {"current": 45, "max": 45}}}

    updates = [_make_msg(1, 100, "/hp remove Ogre", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert "Ogre" not in state["hp_tracker"]["100"]

def test_hp_clear():
    """/hp clear removes all entries."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["hp_tracker"] = {"100": {
        "Ogre": {"current": 45, "max": 45},
        "Goblin": {"current": 10, "max": 10},
    }}

    updates = [_make_msg(1, 100, "/hp clear", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert len(state["hp_tracker"]["100"]) == 0

def test_hp_view():
    """/hp shows HP tracker."""
    state = {"hp_tracker": {"100": {
        "Ogre": {"current": 30, "max": 45},
        "Goblin": {"current": 0, "max": 10},
    }}}
    result = checker._build_hp_tracker("100", "TestCampaign", state)
    assert "Ogre" in result
    assert "Goblin" in result
    assert "█" in result
    assert "💀" in result  # Goblin at 0 HP
