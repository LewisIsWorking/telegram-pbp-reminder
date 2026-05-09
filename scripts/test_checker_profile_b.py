"""Tests for checker.py — profile (part b) group.

Extracted from test_checker.py during the test-split refactor (phase 2).
Module imports, helpers, and the _LOGS_DIR redirection setup live in
``_test_checker_helpers``.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_profile_shows_word_count():
    """The /profile output includes word count when available."""
    _reset()
    now = datetime.now(timezone.utc)
    config = {
        "group_id": -100,
        "gm_user_ids": [999],
        "topic_pairs": [
            {"name": "Test", "chat_topic_id": 200, "pbp_topic_ids": [100]},
        ],
    }
    state = _make_state()
    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "",
        "username": "alice", "campaign_name": "Test",
        "pbp_topic_id": "100", "last_post_time": now.isoformat(),
        "last_warned_week": 0,
    }
    state["message_counts"]["100"] = {"42": 20}
    state["post_timestamps"]["100"] = {
        "42": [(now - timedelta(hours=h)).isoformat() for h in range(20)],
    }
    state["word_counts"] = {"100": {"42": 1500}}

    result = checker._build_profile("alice", config, state)
    assert "1,500 words" in result

def test_profile_command():
    """/profile shows cross-campaign stats for a player."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["players"] = {
        "100:42": {
            "user_id": "42", "first_name": "Alice", "last_name": "",
            "username": "alice", "campaign_name": "TestCampaign",
            "pbp_topic_id": "100", "last_post_time": datetime.now(timezone.utc).isoformat(),
            "last_warned_week": 0,
        },
    }
    state["message_counts"] = {"100": {"42": 25}}
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 9202,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 42, "first_name": "Alice"},
            "date": now_ts,
            "text": "/profile alice",
        },
    }]

    checker.process_updates(updates, config, state)
    profile_msgs = [m for m in _sent_messages if "Alice" in m.get("text", "")]
    assert len(profile_msgs) >= 1

def test_profile_not_found():
    """/profile with unknown player shows error."""
    _reset()
    result = checker._build_profile("nonexistent", _make_config(), _make_state())
    assert "No player matching" in result

def test_profile_no_target():
    """/profile with no name shows usage."""
    _reset()
    config = _make_config()
    state = _make_state()
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 9203,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 42, "first_name": "Alice"},
            "date": now_ts,
            "text": "/profile",
        },
    }]

    checker.process_updates(updates, config, state)
    usage_msgs = [m for m in _sent_messages if "Usage" in m.get("text", "")]
    assert len(usage_msgs) >= 1

def test_profile_cross_campaign():
    """/profile shows stats across multiple campaigns."""
    _reset()
    config = _make_config(pairs=[
        {"name": "Campaign A", "chat_topic_id": 200, "pbp_topic_ids": [100]},
        {"name": "Campaign B", "chat_topic_id": 400, "pbp_topic_ids": [300]},
    ])
    state = _make_state()
    now = datetime.now(timezone.utc).isoformat()
    state["players"] = {
        "100:42": {
            "user_id": "42", "first_name": "Alice", "last_name": "",
            "username": "alice", "campaign_name": "Campaign A",
            "pbp_topic_id": "100", "last_post_time": now,
            "last_warned_week": 0,
        },
        "300:42": {
            "user_id": "42", "first_name": "Alice", "last_name": "",
            "username": "alice", "campaign_name": "Campaign B",
            "pbp_topic_id": "300", "last_post_time": now,
            "last_warned_week": 0,
        },
    }
    state["message_counts"] = {"100": {"42": 15}, "300": {"42": 10}}

    result = checker._build_profile("alice", config, state)
    assert "Campaign A" in result
    assert "Campaign B" in result
    assert "25 posts across 2 campaigns" in result

def test_npc_add():
    """/npc adds an NPC with name and description."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/npc Gorund — Dwarven blacksmith", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    npcs = state.get("npcs", {}).get("100", [])
    assert len(npcs) == 1
    assert npcs[0]["name"] == "Gorund"
    assert npcs[0]["desc"] == "Dwarven blacksmith"
    assert "🎭" in _sent_messages[-1]["text"]

def test_npc_name_only():
    """/npc with just a name (no description)."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/npc Mysterious Stranger", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    npcs = state.get("npcs", {}).get("100", [])
    assert len(npcs) == 1
    assert npcs[0]["name"] == "Mysterious Stranger"
    assert npcs[0]["desc"] == ""

def test_npcs_list():
    """/npcs shows all NPCs."""
    state = {"npcs": {"100": [
        {"name": "Gorund", "desc": "Blacksmith", "added_at": "2026-02-27T10:00:00+00:00"},
        {"name": "Elara", "desc": "Temple priestess", "added_at": "2026-02-28T10:00:00+00:00"},
    ]}}
    result = checker._build_npcs("100", "TestCampaign", state)
    assert "Gorund" in result
    assert "Elara" in result
    assert "2/40 NPCs" in result
