"""Tests for checker.py — roster (part b) group.

Extracted from test_checker.py during the test-split refactor (phase 2).
Module imports, helpers, and the _LOGS_DIR redirection setup live in
``_test_checker_helpers``.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_leaderboard_week_number_and_totals_and_mvp():
    """Week number, totals line, and MVP prize appear in leaderboard."""
    _reset()
    now = datetime(2026, 3, 4, 12, 0, tzinfo=timezone.utc)  # Week 10

    config = _make_config()
    state = _make_state()

    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "B",
        "username": "alice", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": now.isoformat(),
        "last_warned_week": 0,
    }
    state["message_counts"]["100"] = {"42": 10, "999": 20}
    state["post_timestamps"]["100"] = {
        "42": [(now - timedelta(hours=h)).isoformat() for h in range(10)],
        "999": [(now - timedelta(hours=h)).isoformat() for h in [1, 12, 36, 60, 96]],
    }

    stats, global_players, streaks = checker._gather_leaderboard_stats(config, state, now)
    result = checker._format_leaderboard(stats, global_players, now, streaks)

    # Week number in dates
    assert "(W10)" in result

    # Totals line
    assert "This week:" in result
    assert "player" in result and "GM" in result

    # MVP prize
    assert "MVP of the Week" in result
    assert "Hero Point" in result
    # /heropoint fallback is advertised so the typed claim is discoverable
    # when the button callback lags behind the hourly cron.
    assert "/heropoint" in result
    assert "Alice B" in result
    now = datetime.now(timezone.utc)
    stats = {
        "total": 20, "sessions": 15, "week_count": 5,
        "avg_gap_str": "4.2h", "last_post_str": "2h ago", "streak": 8,
    }
    result = checker._roster_block("Alice", "alice", stats)
    assert "8-day streak" in result
    assert "🔥" in result

def test_roster_block_hides_short_streak():
    stats = {
        "total": 20, "sessions": 15, "week_count": 5,
        "avg_gap_str": "4.2h", "last_post_str": "2h ago", "streak": 1,
    }
    result = checker._roster_block("Alice", "alice", stats)
    assert "streak" not in result

def test_sparkline_basic():
    result = checker._sparkline([0, 2, 4, 8, 4, 2, 0, 1])
    assert len(result) == 8
    assert result[3] == "█"  # Peak
    assert result[0] == " "  # Zero

def test_sparkline_all_zeros():
    result = checker._sparkline([0, 0, 0])
    assert result == "▁▁▁"

def test_sparkline_uniform():
    result = checker._sparkline([5, 5, 5])
    assert all(c == "█" for c in result)

def test_summary_basic():
    """/summary shows campaign state."""
    state = {
        "quests": {"100": [{"text": "Find the key", "status": "active", "created_at": ""}]},
        "npcs": {"100": [{"name": "Gorund", "desc": "Smith", "added_at": ""}]},
        "loot": {"100": [{"text": "Sword", "added_at": ""}]},
        "pins": {"100": [{"text": "Clue", "created_at": "", "author": ""}]},
        "conditions": {"100": [{"target": "Bob", "effect": "Stunned", "duration": "", "added_at": ""}]},
    }
    config = _make_config()
    result = checker._build_summary("100", "TestCampaign", state, config)
    assert "Find the key" in result
    assert "1 NPC" in result
    assert "1 loot" in result
    assert "1 pin" in result
    assert "Stunned" in result

def test_summary_empty():
    """/summary with nothing tracked."""
    state = {}
    config = _make_config()
    result = checker._build_summary("100", "TestCampaign", state, config)
    assert "Nothing special" in result

def test_summary_command():
    """/summary command sends result."""
    _reset()
    config = _make_config()
    state = _make_state()

    updates = [_make_msg(1, 100, "/summary", user_id=42, first_name="Alice")]
    checker.process_updates(updates, config, state)

    summary_msgs = [m for m in _sent_messages if "Summary" in m.get("text", "")]
    assert len(summary_msgs) >= 1
