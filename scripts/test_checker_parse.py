"""Tests for checker.py — parse group.

Extracted from test_checker.py during the test-split refactor (phase 2.3).
Module imports, helpers, and the _LOGS_DIR redirection setup live in
``_test_checker_helpers``.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_cleanup_timestamps_prunes_old():
    now = datetime.now(timezone.utc)
    state = _make_state()
    state["post_timestamps"] = {
        "100": {
            "user1": [
                (now - timedelta(days=1)).isoformat(),   # Keep
                (now - timedelta(days=20)).isoformat(),  # Prune
            ],
            "user2": [
                (now - timedelta(days=30)).isoformat(),  # Prune (user removed entirely)
            ],
        }
    }
    checker.cleanup_timestamps(state)
    assert len(state["post_timestamps"]["100"]["user1"]) == 1
    assert "user2" not in state["post_timestamps"]["100"]

def test_cleanup_timestamps_empty_state():
    state = _make_state()
    checker.cleanup_timestamps(state)  # Should not crash

def test_validate_config_valid():
    config = _make_config()
    issues = helpers.validate_config(config)
    assert not any(i.startswith("ERROR:") for i in issues)

def test_validate_config_bad_group_id():
    config = _make_config()
    config["group_id"] = 12345
    issues = helpers.validate_config(config)
    assert any("group_id" in i for i in issues)

def test_validate_config_duplicate_pbp_ids():
    config = _make_config(pairs=[
        {"name": "A", "chat_topic_id": 1, "pbp_topic_ids": [100]},
        {"name": "B", "chat_topic_id": 2, "pbp_topic_ids": [100]},
    ])
    issues = helpers.validate_config(config)
    assert any("ERROR:" in i and "100" in i for i in issues)

def test_validate_config_unknown_feature():
    config = _make_config(pairs=[
        {"name": "A", "chat_topic_id": 1, "pbp_topic_ids": [100], "disabled_features": ["bogus"]},
    ])
    issues = helpers.validate_config(config)
    assert any("bogus" in i for i in issues)

def test_validate_config_bad_created_date():
    config = _make_config(pairs=[
        {"name": "A", "chat_topic_id": 1, "pbp_topic_ids": [100], "created": "15-01-2025"},
    ])
    issues = helpers.validate_config(config)
    assert any("YYYY-MM-DD" in i for i in issues)

def test_feature_enabled():
    config = _make_config(pairs=[
        {"name": "A", "chat_topic_id": 1, "pbp_topic_ids": [100], "disabled_features": ["roster"]},
    ])
    assert helpers.feature_enabled(config, "100", "roster") is False
    assert helpers.feature_enabled(config, "100", "alerts") is True
    assert helpers.feature_enabled(config, "999", "roster") is True

def test_parse_message_valid():
    maps = helpers.build_topic_maps({"group_id": -100, "topic_pairs": [
        {"name": "Test", "chat_topic_id": 200, "pbp_topic_ids": [100]},
    ]})
    msg = {
        "chat": {"id": -100},
        "message_thread_id": 100,
        "from": {"id": 42, "first_name": "Alice", "last_name": "B", "username": "alice"},
        "date": int(datetime.now(timezone.utc).timestamp()),
        "text": "Hello world",
    }
    result = checker._parse_message(msg, maps)
    assert result is not None
    assert result["pid"] == "100"
    assert result["user_id"] == "42"
    assert result["user_name"] == "Alice"
    assert result["text"] == "hello world"

def test_parse_message_wrong_group():
    maps = helpers.build_topic_maps({"group_id": -100, "topic_pairs": [
        {"name": "Test", "chat_topic_id": 200, "pbp_topic_ids": [100]},
    ]})
    msg = {"chat": {"id": -999}, "message_thread_id": 100, "from": {"id": 42}}
    assert checker._parse_message(msg, maps) is None

def test_parse_message_unknown_topic():
    maps = helpers.build_topic_maps({"group_id": -100, "topic_pairs": [
        {"name": "Test", "chat_topic_id": 200, "pbp_topic_ids": [100]},
    ]})
    msg = {"chat": {"id": -100}, "message_thread_id": 999, "from": {"id": 42}}
    assert checker._parse_message(msg, maps) is None

def test_parse_message_bot_skipped():
    maps = helpers.build_topic_maps({"group_id": -100, "topic_pairs": [
        {"name": "Test", "chat_topic_id": 200, "pbp_topic_ids": [100]},
    ]})
    msg = {"chat": {"id": -100}, "message_thread_id": 100, "from": {"id": 42, "is_bot": True}}
    assert checker._parse_message(msg, maps) is None

def test_sanitize_dirname():
    assert checker._sanitize_dirname("Doomsday Funtime") == "Doomsday_Funtime"
    assert checker._sanitize_dirname("Test/Bad:Name!") == "TestBadName"
    assert checker._sanitize_dirname("  Spaces  ") == "Spaces"

def test_parse_message_captures_media():
    maps = helpers.build_topic_maps({"group_id": -100, "topic_pairs": [
        {"name": "Test", "chat_topic_id": 200, "pbp_topic_ids": [100]},
    ]})
    msg = {
        "chat": {"id": -100},
        "message_thread_id": 100,
        "from": {"id": 42, "first_name": "Alice"},
        "date": int(datetime.now(timezone.utc).timestamp()),
        "photo": [{"file_id": "abc"}],
        "caption": "battle map",
    }
    result = checker._parse_message(msg, maps)
    assert result["media_type"] == "image"
    assert result["caption"] == "battle map"
    assert result["text"] == "battle map"  # Falls back to caption

def test_parse_away_duration_days():
    """Parse '3 days reason'."""
    now = datetime(2026, 2, 27, 12, 0, tzinfo=timezone.utc)
    until, reason = helpers.parse_away_duration("3 days vacation", now)
    assert until is not None
    assert (until - now).days == 3
    assert reason == "vacation"

def test_parse_away_duration_weeks():
    """Parse '2 weeks'."""
    now = datetime(2026, 2, 27, 12, 0, tzinfo=timezone.utc)
    until, reason = helpers.parse_away_duration("2 weeks", now)
    assert until is not None
    assert (until - now).days == 14
    assert reason == "Away"

def test_parse_away_duration_indefinite():
    """Parse plain text as indefinite."""
    now = datetime(2026, 2, 27, 12, 0, tzinfo=timezone.utc)
    until, reason = helpers.parse_away_duration("busy with real life stuff", now)
    assert until is None
    assert reason == "busy with real life stuff"

def test_parse_away_duration_empty():
    """Empty text gives indefinite with default reason."""
    now = datetime(2026, 2, 27, 12, 0, tzinfo=timezone.utc)
    until, reason = helpers.parse_away_duration("", now)
    assert until is None
    assert reason == "No reason given"

def test_parse_timer_hours():
    """Parse '24h' duration."""
    now = datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)
    deadline, reason = helpers.parse_timer_duration("24h", now)
    assert deadline == datetime(2026, 3, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert reason == ""

def test_parse_timer_minutes():
    """Parse '30m' duration."""
    now = datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)
    deadline, reason = helpers.parse_timer_duration("30m", now)
    assert deadline == datetime(2026, 2, 28, 12, 30, 0, tzinfo=timezone.utc)

def test_parse_timer_days():
    """Parse '2d' duration."""
    now = datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)
    deadline, reason = helpers.parse_timer_duration("2d", now)
    assert deadline == datetime(2026, 3, 2, 12, 0, 0, tzinfo=timezone.utc)

def test_parse_timer_with_reason():
    """Parse '24h Post your actions'."""
    now = datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)
    deadline, reason = helpers.parse_timer_duration("24h Post your actions", now)
    assert deadline is not None
    assert reason == "Post your actions"

def test_parse_timer_invalid():
    """Invalid duration returns None."""
    now = datetime(2026, 2, 28, 12, 0, 0, tzinfo=timezone.utc)
    deadline, reason = helpers.parse_timer_duration("blah", now)
    assert deadline is None
