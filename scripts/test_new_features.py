"""Tests for features added in v4.4-4.8."""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from datetime import datetime, timezone, timedelta


# --- Queue tests ---

def test_build_queue_empty():
    from commands.queue import build_queue
    config = {"topic_pairs": []}
    state = {"gm_queue": {}}
    result = build_queue(config, state)
    assert "caught up" in result.lower()


def test_build_queue_shows_entries():
    from commands.queue import build_queue
    now = datetime.now(timezone.utc)
    config = {"topic_pairs": [
        {"name": "TestCamp", "pbp_topic_ids": [100], "chat_topic_id": 200},
    ]}
    state = {"gm_queue": {"100": [
        {"message_id": 1, "user_id": "42", "user_name": "Alice",
         "time": (now - timedelta(hours=25)).isoformat(), "preview": "Hello world"},
        {"message_id": 2, "user_id": "43", "user_name": "Bob",
         "time": (now - timedelta(hours=2)).isoformat(), "preview": "Testing"},
    ]}}
    result = build_queue(config, state)
    assert "TestCamp" in result
    assert "Alice" in result
    assert "Bob" in result
    assert "2" in result  # total count


# --- Reactions tests ---

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


# --- Timeline tests ---

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


# --- Boon reminders tests ---

def test_boon_reminder_24h():
    """24h reminder fires, reminders_sent goes to 1."""
    from boons.reminders import check_boon_reminders
    now = datetime.now(timezone.utc)
    config = {"group_id": -100, "bot_topic_id": 300}
    state = {
        "pending_potw_boons": {"100": {
            "message_id": 555,
            "winner_user_id": "42",
            "boons": ["Boon A"],
            "base_message": "Winner!",
            "campaign_name": "TestCamp",
            "posted_at": (now - timedelta(hours=25)).isoformat(),
        }},
        "players": {"100:42": {
            "user_id": "42", "first_name": "Alice", "username": "alice",
            "campaign_name": "TestCamp", "pbp_topic_id": "100",
            "last_post_time": now.isoformat(), "last_warned_week": 0,
        }},
    }
    # Mock telegram
    import telegram as tg
    sent = []
    orig = tg.send_message
    tg.send_message = lambda *a, **k: sent.append(a) or True
    try:
        check_boon_reminders(config, state, now=now)
    finally:
        tg.send_message = orig
    assert state["pending_potw_boons"]["100"]["reminders_sent"] == 1
    assert len(sent) == 1
    assert "unclaimed" in sent[0][2].lower()


def test_boon_reminder_7d_autoselect():
    """7d auto-pick fires and removes from pending."""
    from boons.reminders import check_boon_reminders
    now = datetime.now(timezone.utc)
    config = {"group_id": -100, "bot_topic_id": 300}
    state = {
        "pending_potw_boons": {"100": {
            "message_id": 555,
            "winner_user_id": "42",
            "boons": ["Boon A", "Boon B"],
            "base_message": "Winner!",
            "campaign_name": "TestCamp",
            "posted_at": (now - timedelta(hours=170)).isoformat(),
            "reminders_sent": 3,
        }},
        "players": {},
        "player_boons": {},
    }
    import telegram as tg
    sent = []
    orig_send = tg.send_message
    orig_edit = tg.edit_message
    tg.send_message = lambda *a, **k: sent.append(("send", a)) or True
    tg.edit_message = lambda *a, **k: sent.append(("edit", a)) or True
    try:
        check_boon_reminders(config, state, now=now)
    finally:
        tg.send_message = orig_send
        tg.edit_message = orig_edit
    assert "100" not in state["pending_potw_boons"]


# --- Resolve campaign tests ---

def test_resolve_campaign_exact():
    from dispatch.bot_topic import resolve_campaign

    class FakeMaps:
        name_to_pid = {"kibwe": "100", "doomsday funtime": "200", "doomsday": "200"}
        to_name = {"100": "Kibwe", "200": "Doomsday Funtime"}

    pid, name = resolve_campaign("kibwe", FakeMaps())
    assert pid == "100"
    assert name == "Kibwe"


def test_resolve_campaign_prefix():
    from dispatch.bot_topic import resolve_campaign

    class FakeMaps:
        name_to_pid = {"kibwe": "100", "doomsday funtime": "200", "doomsday": "200"}
        to_name = {"100": "Kibwe", "200": "Doomsday Funtime"}

    pid, name = resolve_campaign("doom", FakeMaps())
    assert pid == "200"


def test_resolve_campaign_not_found():
    from dispatch.bot_topic import resolve_campaign

    class FakeMaps:
        name_to_pid = {"kibwe": "100"}
        to_name = {"100": "Kibwe"}

    pid, name = resolve_campaign("nonexistent", FakeMaps())
    assert pid is None


# --- Queue reminder tests ---

def test_queue_reminder_skips_when_empty():
    from scheduled.queue_reminder import post_queue_reminder
    config = {"group_id": -100, "bot_topic_id": 300}
    state = {"gm_queue": {}}
    import telegram as tg
    sent = []
    orig = tg.send_message
    tg.send_message = lambda *a, **k: sent.append(a) or True
    try:
        post_queue_reminder(config, state)
    finally:
        tg.send_message = orig
    assert len(sent) == 0
    assert "last_queue_reminder" in state


# ------------------------------------------------------------------ #
#  Runner
# ------------------------------------------------------------------ #
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


if __name__ == "__main__":
    sys.exit(_run_all())
