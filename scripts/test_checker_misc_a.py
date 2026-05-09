"""Tests for checker.py — misc (part a) group.

Extracted from test_checker.py during the test-split refactor (phase 2.3).
Module imports, helpers, and the _LOGS_DIR redirection setup live in
``_test_checker_helpers``.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_calc_streak_consecutive_days():
    now = datetime(2025, 3, 15, 14, 0, 0, tzinfo=timezone.utc)
    timestamps = [
        (now - timedelta(days=d, hours=h)).isoformat()
        for d, h in [(0, 2), (1, 5), (2, 3), (3, 8)]  # 4 consecutive days
    ]
    assert checker._calc_streak(timestamps, now) == 4

def test_calc_streak_gap_breaks():
    now = datetime(2025, 3, 15, 14, 0, 0, tzinfo=timezone.utc)
    timestamps = [
        (now - timedelta(days=0, hours=2)).isoformat(),
        (now - timedelta(days=1, hours=5)).isoformat(),
        # Day 2 missing
        (now - timedelta(days=3, hours=3)).isoformat(),
    ]
    assert checker._calc_streak(timestamps, now) == 2

def test_calc_streak_no_recent_posts():
    now = datetime(2025, 3, 15, 14, 0, 0, tzinfo=timezone.utc)
    timestamps = [
        (now - timedelta(days=5)).isoformat(),  # Too old
    ]
    assert checker._calc_streak(timestamps, now) == 0

def test_calc_streak_multiple_posts_same_day():
    now = datetime(2025, 3, 15, 14, 0, 0, tzinfo=timezone.utc)
    timestamps = [
        (now - timedelta(hours=1)).isoformat(),
        (now - timedelta(hours=3)).isoformat(),
        (now - timedelta(hours=5)).isoformat(),
        (now - timedelta(days=1, hours=2)).isoformat(),
    ]
    assert checker._calc_streak(timestamps, now) == 2

def test_calc_streak_empty():
    now = datetime(2025, 3, 15, 14, 0, 0, tzinfo=timezone.utc)
    assert checker._calc_streak([], now) == 0

def test_overview_multi_campaign():
    _reset()
    now = datetime.now(timezone.utc)
    config = {
        "group_id": -100,
        "gm_user_ids": [999],
        "topic_pairs": [
            {"name": "Campaign A", "chat_topic_id": 200, "pbp_topic_ids": [100]},
            {"name": "Campaign B", "chat_topic_id": 400, "pbp_topic_ids": [300]},
        ],
    }
    state = _make_state()
    state["topics"]["100"] = {
        "last_message_time": (now - timedelta(hours=2)).isoformat(),
        "last_user": "Alice", "last_user_id": "42",
        "campaign_name": "Campaign A",
    }
    state["topics"]["300"] = {
        "last_message_time": (now - timedelta(days=3)).isoformat(),
        "last_user": "Bob", "last_user_id": "50",
        "campaign_name": "Campaign B",
    }
    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "",
        "username": "", "campaign_name": "Campaign A",
        "pbp_topic_id": "100", "last_post_time": now.isoformat(),
        "last_warned_week": 0,
    }

    result = checker._build_overview(config, state)
    assert "Campaign A" in result
    assert "Campaign B" in result
    assert "2 campaigns" in result
    assert "1 active players" in result

def test_get_characters():
    config = {
        "topic_pairs": [
            {"name": "A", "chat_topic_id": 10, "pbp_topic_ids": [100],
             "characters": {42: "Cardigan"}},
        ],
    }
    chars = helpers.get_characters(config, "100")
    assert chars == {"42": "Cardigan"}
    assert helpers.get_characters(config, "999") == {}

def test_pace_drop_detected():
    _reset()
    config = _make_config()
    now = datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc)
    state = _make_state()

    # Last week had 20 posts, this week has 5 -> 75% drop
    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    last_week_times = [(two_weeks_ago + timedelta(hours=i * 6)).isoformat() for i in range(20)]
    this_week_times = [(week_ago + timedelta(hours=i * 24)).isoformat() for i in range(5)]

    state["post_timestamps"]["100"] = {
        "42": last_week_times + this_week_times,
    }
    state["players"]["100"] = {
        "42": {"first_name": "Alice", "last_post": this_week_times[-1]},
    }

    checker.check_pace_drop(config, state, now=now)
    assert any("Pace check" in m.get("text", "") or "📉" in m.get("text", "") for m in _sent_messages)
    assert "last_pace_drop_check" in state

def test_pace_drop_skips_low_activity():
    _reset()
    config = _make_config()
    now = datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc)
    state = _make_state()

    # Last week had only 3 posts (below threshold of 5) — should not alert
    two_weeks_ago = now - timedelta(days=14)
    last_week_times = [(two_weeks_ago + timedelta(hours=i * 24)).isoformat() for i in range(3)]

    state["post_timestamps"]["100"] = {
        "42": last_week_times,
    }
    state["players"]["100"] = {
        "42": {"first_name": "Alice", "last_post": last_week_times[-1]},
    }

    checker.check_pace_drop(config, state, now=now)
    pace_msgs = [m for m in _sent_messages if "Pace check" in m.get("text", "") or "📉" in m.get("text", "")]
    assert len(pace_msgs) == 0

def test_pace_drop_weekly_gating():
    _reset()
    config = _make_config()
    now = datetime(2026, 2, 20, 12, 0, tzinfo=timezone.utc)
    state = _make_state()
    # Already checked recently
    state["last_pace_drop_check"] = (now - timedelta(days=1)).isoformat()

    checker.check_pace_drop(config, state, now=now)
    assert len(_sent_messages) == 0  # Should not run

def test_next_players_to_enemies():
    """/next advances from players to enemies phase."""
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

    updates = [_make_msg(1, 100, "/next", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert state["combat"]["100"]["current_phase"] == "enemies"
    assert "Enemies" in _sent_messages[-1]["text"]

def test_next_enemies_to_new_round():
    """/next advances from enemies to next round players."""
    _reset()
    config = _make_config()
    state = _make_state()
    now = datetime.now(timezone.utc)
    state["combat"]["100"] = {
        "active": True, "round": 1, "current_phase": "enemies",
        "players_acted": {}, "last_ping_at": None, "enemies": [],
        "combat_log": [], "campaign_name": "TestCampaign",
        "phase_started_at": now.isoformat(), "started_at": now.isoformat(),
        "all_players_notified": False,
    }

    updates = [_make_msg(1, 100, "/next", user_id=999, first_name="GM")]
    checker.process_updates(updates, config, state)

    assert state["combat"]["100"]["round"] == 2
    assert state["combat"]["100"]["current_phase"] == "players"
    assert state["combat"]["100"]["players_acted"] == {}
    assert "Round 2" in _sent_messages[-1]["text"]
