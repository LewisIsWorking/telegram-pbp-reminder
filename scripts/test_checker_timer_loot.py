"""Tests for checker.py — timer_loot group.

Extracted from test_checker.py during the test-split refactor (phase 2.3).
Module imports, helpers, and the _LOGS_DIR redirection setup live in
``_test_checker_helpers``.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_expire_pending_boons():
    _reset()
    state = _make_state()
    old_time = (datetime.now(timezone.utc) - timedelta(hours=170)).isoformat()
    state["pending_potw_boons"]["100"] = {
        "message_id": 555,
        "winner_user_id": "42",
        "boons": ["Boon A", "Boon B"],
        "base_message": "Winner!",
        "campaign_name": "TestCampaign",
        "posted_at": old_time,
    }
    checker.expire_pending_boons(_make_config(), state)
    assert "100" not in state["pending_potw_boons"]
    auto_msgs = [m for m in _sent_messages if "auto-selected" in m.get("text", "")]
    assert len(auto_msgs) >= 1

def test_loot_add():
    """/loot adds an item."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/loot +1 striking longsword", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    loot = state.get("loot", {}).get("100", [])
    assert len(loot) == 1
    assert loot[0]["text"] == "+1 striking longsword"
    assert "💰" in _sent_messages[-1]["text"]

def test_loot_non_gm():
    """/loot from non-GM is ignored."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/loot stolen gem", user_id=42, first_name="Player")]
    checker.process_updates(updates, config, state)

    loot = state.get("loot", {}).get("100", [])
    assert len(loot) == 0

def test_lootlist():
    """/lootlist shows all items."""
    state = {"loot": {"100": [
        {"text": "+1 longsword", "added_at": "2026-02-27T10:00:00+00:00"},
        {"text": "500 gp", "added_at": "2026-02-28T10:00:00+00:00"},
    ]}}
    result = checker._build_lootlist("100", "TestCampaign", state)
    assert "+1 longsword" in result
    assert "500 gp" in result
    assert "2/50 items" in result

def test_delloot():
    """/delloot removes an item."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["loot"] = {"100": [
        {"text": "+1 longsword", "added_at": "2026-02-27T10:00:00+00:00"},
    ]}

    updates = [_make_msg(1, 100, "/delloot 1", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert len(state["loot"]["100"]) == 0
    assert "🗑️" in _sent_messages[-1]["text"]

def test_timer_set():
    """/timer sets a deadline."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/timer 24h Post your actions", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    timer = state.get("timers", {}).get("100")
    assert timer is not None
    assert timer["reason"] == "Post your actions"
    assert "⏳" in _sent_messages[-1]["text"]

def test_timer_bad_duration():
    """/timer with bad duration gives error."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/timer blah", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert "100" not in state.get("timers", {})
    assert "parse" in _sent_messages[-1]["text"].lower() or "Nh" in _sent_messages[-1]["text"]

def test_showtimer():
    """/showtimer displays timer."""
    from datetime import timezone
    state = {"timers": {"100": {
        "deadline": (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat(),
        "reason": "Act now!",
        "set_at": datetime.now(timezone.utc).isoformat(),
    }}}
    result = checker._build_timer("100", "TestCampaign", state)
    assert "remaining" in result
    assert "Act now!" in result

def test_canceltimer():
    """/canceltimer removes the timer."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["timers"] = {"100": {
        "deadline": (datetime.now(timezone.utc) + timedelta(hours=5)).isoformat(),
        "reason": "test",
        "set_at": datetime.now(timezone.utc).isoformat(),
    }}

    updates = [_make_msg(1, 100, "/canceltimer", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert "100" not in state.get("timers", {})

def test_timer_expiry_notification():
    """check_expired_timers posts notification."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["timers"] = {"100": {
        "deadline": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        "reason": "Time's up!",
        "set_at": datetime.now(timezone.utc).isoformat(),
    }}

    checker.check_expired_timers(config, state)

    expired_msgs = [m for m in _sent_messages if "expired" in m.get("text", "").lower()]
    assert len(expired_msgs) >= 1
    assert state["timers"]["100"].get("notified")

def test_timer_non_gm():
    """/timer from non-GM is ignored."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/timer 24h hack", user_id=42, first_name="Player")]
    checker.process_updates(updates, config, state)

    assert "100" not in state.get("timers", {})
