"""Tests for checker.py — note group.

Extracted from test_checker.py during the test-split refactor (phase 2.3).
Module imports, helpers, and the _LOGS_DIR redirection setup live in
``_test_checker_helpers``.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_note_command():
    """GM /note adds a persistent note."""
    _reset()
    config = _make_config()
    state = _make_state()
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 9110,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 999, "first_name": "GM"},
            "date": now_ts,
            "text": "/note Party agreed to meet the informant at dawn",
        },
    }]

    checker.process_updates(updates, config, state)
    notes = state.get("campaign_notes", {}).get("100", [])
    assert len(notes) == 1
    assert notes[0]["text"] == "Party agreed to meet the informant at dawn"
    saved_msgs = [m for m in _sent_messages if "saved" in m.get("text", "").lower()]
    assert len(saved_msgs) >= 1

def test_note_no_text():
    """GM /note with no text shows usage."""
    _reset()
    config = _make_config()
    state = _make_state()
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 9111,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 999, "first_name": "GM"},
            "date": now_ts,
            "text": "/note",
        },
    }]

    checker.process_updates(updates, config, state)
    assert len(state.get("campaign_notes", {}).get("100", [])) == 0

def test_note_max_limit():
    """Notes capped at 20 per campaign."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["campaign_notes"] = {"100": [
        {"text": f"Note {i}", "created_at": "2026-01-01T00:00:00+00:00"}
        for i in range(20)
    ]}
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 9112,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 999, "first_name": "GM"},
            "date": now_ts,
            "text": "/note One too many",
        },
    }]

    checker.process_updates(updates, config, state)
    assert len(state["campaign_notes"]["100"]) == 20
    max_msgs = [m for m in _sent_messages if "Maximum" in m.get("text", "")]
    assert len(max_msgs) >= 1

def test_notes_command():
    """Anyone can view notes with /notes."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["campaign_notes"] = {"100": [
        {"text": "First note", "created_at": "2026-01-15T10:00:00+00:00"},
        {"text": "Second note", "created_at": "2026-01-16T10:00:00+00:00"},
    ]}
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 9113,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 42, "first_name": "Player"},
            "date": now_ts,
            "text": "/notes",
        },
    }]

    checker.process_updates(updates, config, state)
    notes_msgs = [m for m in _sent_messages if "First note" in m.get("text", "")]
    assert len(notes_msgs) >= 1

def test_notes_empty():
    """/notes with no notes shows helpful message."""
    _reset()
    result = checker._build_notes("100", "TestCampaign", {})
    assert "No GM notes" in result

def test_delnote_command():
    """GM /delnote removes a note by number."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["campaign_notes"] = {"100": [
        {"text": "Keep this", "created_at": "2026-01-15T10:00:00+00:00"},
        {"text": "Delete this", "created_at": "2026-01-16T10:00:00+00:00"},
    ]}
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 9114,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 999, "first_name": "GM"},
            "date": now_ts,
            "text": "/delnote 2",
        },
    }]

    checker.process_updates(updates, config, state)
    notes = state["campaign_notes"]["100"]
    assert len(notes) == 1
    assert notes[0]["text"] == "Keep this"
    del_msgs = [m for m in _sent_messages if "Deleted" in m.get("text", "")]
    assert len(del_msgs) >= 1

def test_delnote_invalid_number():
    """GM /delnote with invalid number shows error."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["campaign_notes"] = {"100": [
        {"text": "A note", "created_at": "2026-01-15T10:00:00+00:00"},
    ]}
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 9115,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 999, "first_name": "GM"},
            "date": now_ts,
            "text": "/delnote 5",
        },
    }]

    checker.process_updates(updates, config, state)
    assert len(state["campaign_notes"]["100"]) == 1
    err_msgs = [m for m in _sent_messages if "not found" in m.get("text", "")]
    assert len(err_msgs) >= 1

def test_notes_show_in_campaign():
    """Notes appear in /campaign output."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["campaign_notes"] = {"100": [
        {"text": "Remember the artifact", "created_at": "2026-01-15T10:00:00+00:00"},
    ]}
    result = checker._build_campaign_report("100", config, state, {999})
    assert "Remember the artifact" in result
