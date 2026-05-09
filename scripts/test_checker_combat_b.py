"""Tests for checker.py — combat (part b) group.

Extracted from test_checker.py during the test-split refactor (phase 2).
Module imports, helpers, and the _LOGS_DIR redirection setup live in
``_test_checker_helpers``.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_dc_legendary():
    """Legendary proficiency DC."""
    result = helpers.dc_lookup("legendary")
    assert "40" in result

def test_dc_alias():
    """Short alias works."""
    result = helpers.dc_lookup("vh")
    assert "Very Hard" in result

def test_dc_empty():
    """Empty query shows help."""
    result = helpers.dc_lookup("")
    assert "Usage" in result

def test_dc_out_of_range():
    """Level out of range gives error."""
    result = helpers.dc_lookup("25")
    assert "0–20" in result

def test_condition_add():
    """/condition adds a condition with target and effect."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/condition Cardigan — Frightened 2 | end of next turn", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    conds = state.get("conditions", {}).get("100", [])
    assert len(conds) == 1
    assert conds[0]["target"] == "Cardigan"
    assert conds[0]["effect"] == "Frightened 2"
    assert conds[0]["duration"] == "end of next turn"
    assert "⚡" in _sent_messages[-1]["text"]

def test_condition_no_duration():
    """/condition without duration."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/condition All — Inspired +1", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    conds = state.get("conditions", {}).get("100", [])
    assert len(conds) == 1
    assert conds[0]["duration"] == ""

def test_conditions_list():
    """/conditions shows all active conditions."""
    state = {"conditions": {"100": [
        {"target": "Cardigan", "effect": "Frightened 2", "duration": "1 round", "added_at": "2026-02-27T10:00:00+00:00"},
        {"target": "Rax", "effect": "Flat-footed", "duration": "", "added_at": "2026-02-27T10:00:00+00:00"},
    ]}}
    config = _make_config()
    result = checker._build_conditions("100", "TestCampaign", state, config)
    assert "Cardigan" in result
    assert "Frightened 2" in result
    assert "(1 round)" in result
    assert "Rax" in result
    assert "2 active" in result

def test_endcondition():
    """/endcondition removes a condition."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["conditions"] = {"100": [
        {"target": "Cardigan", "effect": "Frightened 2", "duration": "", "added_at": "2026-02-27T10:00:00+00:00"},
    ]}

    updates = [_make_msg(1, 100, "/endcondition 1", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert len(state["conditions"]["100"]) == 0
    assert "✅ Ended" in _sent_messages[-1]["text"]

def test_clearconditions():
    """/clearconditions removes all conditions."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["conditions"] = {"100": [
        {"target": "A", "effect": "X", "duration": "", "added_at": ""},
        {"target": "B", "effect": "Y", "duration": "", "added_at": ""},
    ]}

    updates = [_make_msg(1, 100, "/clearconditions", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert len(state["conditions"]["100"]) == 0
    assert "Cleared 2" in _sent_messages[-1]["text"]

def test_condition_non_gm():
    """/condition from non-GM is ignored."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/condition Me — Invincible", user_id=42, first_name="Player")]
    checker.process_updates(updates, config, state)

    assert len(state.get("conditions", {}).get("100", [])) == 0

def test_combat_start():
    """/combat starts combat with enemy roster."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/combat Ogre, 2 Skeletons", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    combat = state["combat"].get("100")
    assert combat is not None
    assert combat["active"] is True
    assert combat["round"] == 1
    assert combat["current_phase"] == "players"
    assert combat["enemies"] == ["Ogre", "2 Skeletons"]
    assert "⚔️" in _sent_messages[-1]["text"]
    assert "Ogre" in _sent_messages[-1]["text"]

def test_combat_start_no_enemies():
    """/combat works without enemy list."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/combat", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    combat = state["combat"].get("100")
    assert combat is not None
    assert combat["enemies"] == []

def test_combat_auto_notify():
    """GM gets pinged when all players have acted."""
    _reset()
    config = _make_config()
    state = _make_state()
    now = datetime.now(timezone.utc)

    # Register two players
    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "",
        "username": "", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": now.isoformat(),
        "last_warned_week": 0,
    }
    state["players"]["100:43"] = {
        "user_id": "43", "first_name": "Bob", "last_name": "",
        "username": "", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": now.isoformat(),
        "last_warned_week": 0,
    }
    state["combat"]["100"] = {
        "active": True, "round": 1, "current_phase": "players",
        "players_acted": {"42": now.isoformat()}, "last_ping_at": None,
        "enemies": [], "combat_log": [], "campaign_name": "TestCampaign",
        "phase_started_at": now.isoformat(), "started_at": now.isoformat(),
        "all_players_notified": False,
    }

    # Bob posts — now everyone has acted
    updates = [_make_msg(1, 100, "I swing my axe!", user_id=43, first_name="Bob")]
    checker.process_updates(updates, config, state)

    # Should see auto-notify
    notify_msgs = [m for m in _sent_messages if "All players have posted" in m.get("text", "")]
    assert len(notify_msgs) >= 1
    assert state["combat"]["100"]["all_players_notified"] is True
