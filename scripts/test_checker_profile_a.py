"""Tests for checker.py — profile (part a) group.

Extracted from test_checker.py during the test-split refactor (phase 2).
Module imports, helpers, and the _LOGS_DIR redirection setup live in
``_test_checker_helpers``.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_kick_by_username():
    _reset()
    state = _make_state()
    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "",
        "username": "alice99", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": "2026-01-01T00:00:00",
        "last_warned_week": 0,
    }
    checker._handle_kick("100", "TestCampaign", "alice99", state, -100, 200)
    assert "100:42" not in state["players"]
    assert "100:42" in state["removed_players"]
    assert state["removed_players"]["100:42"]["kicked"] is True
    assert any("removed" in m.get("text", "").lower() for m in _sent_messages)

def test_kick_by_first_name():
    _reset()
    state = _make_state()
    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "Smith",
        "username": "alice99", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": "2026-01-01T00:00:00",
        "last_warned_week": 0,
    }
    checker._handle_kick("100", "TestCampaign", "Alice Smith", state, -100, 200)
    assert "100:42" not in state["players"]

def test_kick_no_match():
    _reset()
    state = _make_state()
    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "",
        "username": "alice99", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": "2026-01-01T00:00:00",
        "last_warned_week": 0,
    }
    checker._handle_kick("100", "TestCampaign", "nobody", state, -100, 200)
    assert "100:42" in state["players"]  # Not removed
    assert any("no player" in m.get("text", "").lower() for m in _sent_messages)

def test_addplayer():
    _reset()
    state = _make_state()
    now_iso = datetime.now(timezone.utc).isoformat()
    checker._handle_addplayer("100", "TestCampaign", "@bob Bob Jones",
                              now_iso, state, -100, 200)
    key = "100:pending_bob"
    assert key in state["players"]
    assert state["players"][key]["first_name"] == "Bob"
    assert state["players"][key]["last_name"] == "Jones"
    assert state["players"][key]["username"] == "bob"
    assert any("added" in m.get("text", "").lower() for m in _sent_messages)

def test_addplayer_duplicate():
    _reset()
    state = _make_state()
    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Bob", "last_name": "",
        "username": "bob", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": "2026-01-01T00:00:00",
        "last_warned_week": 0,
    }
    now_iso = datetime.now(timezone.utc).isoformat()
    checker._handle_addplayer("100", "TestCampaign", "@bob Bob",
                              now_iso, state, -100, 200)
    assert "100:pending_bob" not in state["players"]  # Not added
    assert any("already tracked" in m.get("text", "").lower() for m in _sent_messages)

def test_addplayer_clears_removed():
    _reset()
    state = _make_state()
    state["removed_players"]["100:42"] = {
        "removed_at": "2026-01-01T00:00:00",
        "first_name": "Bob", "username": "bob",
        "campaign_name": "TestCampaign",
    }
    now_iso = datetime.now(timezone.utc).isoformat()
    checker._handle_addplayer("100", "TestCampaign", "@bob Bob",
                              now_iso, state, -100, 200)
    assert "100:42" not in state["removed_players"]
    assert "100:pending_bob" in state["players"]

def test_character_name_helper():
    config = {
        "topic_pairs": [
            {"name": "A", "chat_topic_id": 10, "pbp_topic_ids": [100],
             "characters": {"42": "Cardigan", "50": "Amar"}},
        ],
    }
    assert helpers.character_name(config, "100", "42") == "Cardigan"
    assert helpers.character_name(config, "100", "50") == "Amar"
    assert helpers.character_name(config, "100", "999") is None
    assert helpers.character_name(config, "999", "42") is None

def test_party_with_characters():
    _reset()
    now = datetime.now(timezone.utc)
    config = {
        "group_id": -100,
        "gm_user_ids": [999],
        "topic_pairs": [
            {"name": "TestCampaign", "chat_topic_id": 200, "pbp_topic_ids": [100],
             "characters": {"42": "Cardigan", "50": "Amar"}},
        ],
    }
    state = _make_state()
    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "",
        "username": "", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": now.isoformat(),
        "last_warned_week": 0,
    }

    result = checker._build_party("100", "TestCampaign", config, state)
    assert "Cardigan" in result
    assert "Alice" in result
    assert "Amar" in result
    assert "1 active" in result
    assert "1 inactive" in result

def test_party_no_characters():
    _reset()
    config = _make_config()
    state = _make_state()
    result = checker._build_party("100", "TestCampaign", config, state)
    assert "no characters" in result.lower()

def test_mystats_with_character():
    _reset()
    now = datetime.now(timezone.utc)
    config = {
        "group_id": -100,
        "gm_user_ids": [999],
        "topic_pairs": [
            {"name": "Test", "chat_topic_id": 200, "pbp_topic_ids": [100],
             "characters": {"42": "Cardigan"}},
        ],
    }
    state = _make_state()
    state["post_timestamps"]["100"] = {
        "42": [(now - timedelta(hours=h)).isoformat() for h in range(10)],
    }
    state["message_counts"]["100"] = {"42": 10}

    result = checker._build_mystats("100", "42", "Test", state, {"999"}, config)
    assert "Cardigan" in result

def test_mystats_shows_word_count():
    """The /mystats output includes word count when available."""
    _reset()
    now = datetime.now(timezone.utc)
    state = _make_state()
    state["post_timestamps"]["100"] = {
        "42": [(now - timedelta(hours=h)).isoformat() for h in range(5)],
    }
    state["message_counts"]["100"] = {"42": 5}
    state["word_counts"] = {"100": {"42": 250}}

    result = checker._build_mystats("100", "42", "Test", state, {"999"})
    assert "250" in result
    assert "50/post" in result
