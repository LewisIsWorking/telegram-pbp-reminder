"""Tests for checker.py — session (part b) group.

Extracted from test_checker.py during the test-split refactor (phase 2).
Module imports, helpers, and the _LOGS_DIR redirection setup live in
``_test_checker_helpers``.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_catchup_with_messages():
    _reset()
    now = datetime.now(timezone.utc)
    state = _make_state()
    # Player posted 24 hours ago, others posted since
    my_post = (now - timedelta(hours=24)).isoformat()
    gm_post = (now - timedelta(hours=12)).isoformat()
    other_post1 = (now - timedelta(hours=6)).isoformat()
    other_post2 = (now - timedelta(hours=3)).isoformat()

    state["post_timestamps"]["100"] = {
        "42": [my_post],
        "999": [gm_post],
        "50": [other_post1, other_post2],
    }
    state["players"]["100:50"] = {
        "user_id": "50", "first_name": "Bob", "last_name": "",
        "username": "bob", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": other_post2,
        "last_warned_week": 0,
    }

    result = checker._build_catchup("100", "42", "TestCampaign", state, {"999"})
    assert "GM" in result
    assert "Bob" in result
    assert "3 posts" in result  # 1 GM + 2 Bob

def test_catchup_with_combat():
    _reset()
    now = datetime.now(timezone.utc)
    state = _make_state()
    state["post_timestamps"]["100"] = {
        "42": [(now - timedelta(hours=5)).isoformat()],
        "999": [(now - timedelta(hours=2)).isoformat()],
    }
    state["combat"]["100"] = {
        "active": True, "round": 3, "current_phase": "players",
        "players_acted": {},
    }

    result = checker._build_catchup("100", "42", "TestCampaign", state, {"999"})
    assert "combat" in result.lower()
    assert "Round 3" in result
    assert "haven't acted" in result

def test_archive_includes_player_breakdown():
    _reset()
    config = _make_config()
    now = datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc)  # Friday

    state = _make_state()
    # Plant timestamps for player 42 (not GM 999) in last week
    week_start = now - timedelta(days=now.weekday() + 7)
    ts1 = (week_start + timedelta(hours=2)).isoformat()
    ts2 = (week_start + timedelta(days=1, hours=3)).isoformat()
    ts3 = (week_start + timedelta(days=2, hours=4)).isoformat()
    state["post_timestamps"]["100"] = {
        "42": [ts1, ts2, ts3],
        "999": [(week_start + timedelta(hours=5)).isoformat()],
    }
    state["players"]["100:42"] = {
        "first_name": "Alice",
        "last_post_time": ts3,
        "pbp_topic_id": "100",
        "campaign_name": "TestCampaign",
    }

    # Ensure archive file doesn't exist yet
    import pathlib
    archive_path = helpers.ARCHIVE_PATH
    if archive_path.exists():
        archive_path.unlink()

    checker.archive_weekly_data(config, state, now=now)

    # Read the archive
    import json
    with open(archive_path) as f:
        archive = json.load(f)

    # Find our entry
    entries = [v for v in archive.values() if v["campaign"] == "TestCampaign"]
    assert len(entries) == 1
    entry = entries[0]

    assert "player_breakdown" in entry
    pb = entry["player_breakdown"]
    # Alice should be in the breakdown
    alice_entries = [v for k, v in pb.items() if "Alice" in k]
    assert len(alice_entries) == 1
    assert alice_entries[0]["posts"] == 3
    assert alice_entries[0]["sessions"] >= 1
    assert alice_entries[0]["avg_gap_h"] is not None

def test_scene_command():
    """GM /scene sets current scene and writes to transcript."""
    _reset()
    config = _make_config()
    state = _make_state()
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 9100,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 999, "first_name": "GM"},
            "date": now_ts,
            "text": "/scene The Docks at Midnight",
        },
    }]

    checker.process_updates(updates, config, state)
    assert state.get("current_scenes", {}).get("100") == "The Docks at Midnight"
    scene_msgs = [m for m in _sent_messages if "Scene" in m.get("text", "")]
    assert len(scene_msgs) >= 1

def test_scene_no_name():
    """GM /scene with no name shows usage."""
    _reset()
    config = _make_config()
    state = _make_state()
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 9101,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 999, "first_name": "GM"},
            "date": now_ts,
            "text": "/scene",
        },
    }]

    checker.process_updates(updates, config, state)
    assert "100" not in state.get("current_scenes", {})
    usage_msgs = [m for m in _sent_messages if "Usage" in m.get("text", "")]
    assert len(usage_msgs) >= 1

def test_scene_non_gm_ignored():
    """Non-GM /scene is ignored."""
    _reset()
    config = _make_config()
    state = _make_state()
    now_ts = int(datetime.now(timezone.utc).timestamp())

    updates = [{
        "update_id": 9102,
        "message": {
            "chat": {"id": -100},
            "message_thread_id": 100,
            "from": {"id": 42, "first_name": "Player"},
            "date": now_ts,
            "text": "/scene Sneaky Scene",
        },
    }]

    checker.process_updates(updates, config, state)
    assert "100" not in state.get("current_scenes", {})
