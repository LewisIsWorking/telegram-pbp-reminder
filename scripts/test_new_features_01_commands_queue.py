"""test_new_features.py — bin 1.

  - commands.queue+reactions+timeline
"""
"""Tests for features added in v4.4-4.8."""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timezone, timedelta
from unittest.mock import patch


# --- Queue tests ---


def _run_all():
    tests = [(name, obj) for name, obj in globals().items()
             if name.startswith("test_") and callable(obj)]
    passed = failed = 0
    for name, func in sorted(tests):
        try:
            func()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  FAIL: {name}: {e}")
    print(f"\n{passed} passed, {failed} failed out of {passed + failed}")
    return failed

def test_build_queue_empty():
    from commands.queue import build_queue
    config = {"topic_pairs": []}
    state = {}
    result = build_queue(config, state)
    assert "caught up" in result.lower()

def test_build_queue_uses_scanner():
    """Queue uses transcript scanner, returns string output."""
    from commands.queue import build_queue
    # With no matching transcript files, should return caught up
    config = {"topic_pairs": [
        {"name": "NonexistentCamp", "pbp_topic_ids": [99999], "chat_topic_id": 200},
    ]}
    state = {}
    result = build_queue(config, state)
    assert "caught up" in result.lower()

def test_process_reaction_tracks_emoji():
    from commands.reactions import process_reaction
    config = {"group_id": -100}
    state = {}

    class FakeMaps:
        all_pbp_ids = {"100"}
        to_canonical = {"100": "100"}

    update = {"message_reaction": {
        "chat": {"id": -100},
        "message_thread_id": 100,
        "user": {"id": 42, "first_name": "Alice", "is_bot": False},
        "old_reaction": [],
        "new_reaction": [{"type": "emoji", "emoji": "❤️"}],
    }}
    process_reaction(update, config, state, FakeMaps())
    assert state["reactions"]["100"]["given"]["42"]["count"] == 1
    assert state["reactions"]["100"]["emojis"]["❤️"] == 1

def test_process_reaction_handles_removal():
    from commands.reactions import process_reaction
    config = {"group_id": -100}
    state = {"reactions": {"100": {
        "given": {"42": {"name": "Alice", "count": 3}},
        "emojis": {"❤️": 3},
    }}}

    class FakeMaps:
        all_pbp_ids = {"100"}
        to_canonical = {"100": "100"}

    update = {"message_reaction": {
        "chat": {"id": -100},
        "message_thread_id": 100,
        "user": {"id": 42, "first_name": "Alice", "is_bot": False},
        "old_reaction": [{"type": "emoji", "emoji": "❤️"}],
        "new_reaction": [],
    }}
    process_reaction(update, config, state, FakeMaps())
    assert state["reactions"]["100"]["given"]["42"]["count"] == 2
    assert state["reactions"]["100"]["emojis"]["❤️"] == 2

def test_build_reactions_empty():
    from commands.reactions import build_reactions
    result = build_reactions({}, {}, "100", "TestCamp")
    assert "no reactions" in result.lower()

def test_build_reactions_shows_data():
    from commands.reactions import build_reactions
    state = {"reactions": {"100": {
        "given": {"42": {"name": "Alice", "count": 5}},
        "emojis": {"❤️": 5, "😂": 3},
    }}}
    result = build_reactions({}, state, "100", "TestCamp")
    assert "Alice" in result
    assert "❤️" in result

def test_build_timeline_empty():
    from commands.timeline import build_timeline
    config = {"topic_pairs": []}
    result = build_timeline(config, {})
    assert "no timeline" in result.lower()

def test_build_timeline_shows_creation():
    from commands.timeline import build_timeline
    config = {"topic_pairs": [
        {"name": "TestCamp", "pbp_topic_ids": [100], "chat_topic_id": 200,
         "created": "2025-01-15"},
    ]}
    result = build_timeline(config, {})
    assert "TestCamp" in result
    assert "Campaign started" in result

def test_add_event():
    from commands.timeline import add_event
    state = {}
    result = add_event("100", "TestCamp", "The dragon attacks!", state)
    assert "logged" in result.lower()
    assert len(state["timeline_events"]["100"]) == 1
    assert state["timeline_events"]["100"][0]["text"] == "The dragon attacks!"

def test_add_event_empty():
    from commands.timeline import add_event
    result = add_event("100", "TestCamp", "", {})
    assert "usage" in result.lower()
