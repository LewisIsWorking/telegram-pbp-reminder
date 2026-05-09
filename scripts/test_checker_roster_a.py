"""Tests for checker.py — roster (part a) group.

Extracted from test_checker.py during the test-split refactor (phase 2).
Module imports, helpers, and the _LOGS_DIR redirection setup live in
``_test_checker_helpers``.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_roster_user_stats():
    now = _utc(2026, 2, 20, 12, 0)
    # 4 posts: now, 6h ago, 2d ago, 10d ago
    timestamps = [
        now.isoformat(),
        (now - timedelta(hours=6)).isoformat(),
        (now - timedelta(days=2)).isoformat(),
        (now - timedelta(days=10)).isoformat(),
    ]
    stats = checker._roster_user_stats(timestamps, 20, now)
    assert stats["total"] == 20
    assert stats["sessions"] >= 3  # 3+ sessions after dedup
    assert stats["week_count"] >= 2  # At least 2 posts in the last week
    assert "hours" in stats["avg_gap_str"] or "minutes" in stats["avg_gap_str"]
    assert "today" in stats["last_post_str"]

def test_roster_block():
    stats = {
        "total": 15,
        "sessions": 5,
        "week_count": 3,
        "avg_gap_str": "24.0 hours",
        "last_post_str": "today (2026-02-20)",
    }
    block = checker._roster_block("Alice", "alice123", stats)
    assert "Alice" in block
    assert "@alice123" in block
    assert "15 posts total" in block
    assert "5 posting sessions" in block
    assert "3 posts in the last week" in block
    assert "24.0 hours" in block

def test_roster_block_no_username():
    stats = {"total": 1, "sessions": 1, "week_count": 0, "avg_gap_str": "N/A", "last_post_str": "N/A"}
    block = checker._roster_block("Bob", "", stats)
    assert "Bob" in block
    assert "@" not in block
    assert "1 posting session." in block  # Singular

def test_gather_potw_candidates():
    now = _utc(2026, 2, 20, 12, 0)
    week_ago = now - timedelta(days=7)
    # Player with 6 sessions this week
    timestamps = {
        "player1": [(now - timedelta(hours=h)).isoformat() for h in [2, 14, 26, 38, 50, 62]],
        "gm999": [(now - timedelta(hours=h)).isoformat() for h in [1, 3, 5]],  # GM
    }
    state = _make_state()
    state["players"]["100:player1"] = {
        "first_name": "Alice", "last_name": "B", "username": "alice",
        "pbp_topic_id": "100", "user_id": "player1", "campaign_name": "Test",
        "last_post_time": now.isoformat(), "last_warned_week": 0,
    }
    candidates = checker._gather_potw_candidates(timestamps, {"gm999"}, week_ago, "100", state)
    assert len(candidates) == 1
    assert candidates[0]["user_id"] == "player1"
    assert candidates[0]["first_name"] == "Alice"
    assert candidates[0]["avg_gap_hours"] > 0

def test_gather_potw_excludes_low_posts():
    now = _utc(2026, 2, 20, 12, 0)
    week_ago = now - timedelta(days=7)
    # Only 2 posts (below default POTW_MIN_POSTS of 5)
    timestamps = {
        "player1": [(now - timedelta(hours=h)).isoformat() for h in [2, 50]],
    }
    state = _make_state()
    state["players"]["100:player1"] = {
        "first_name": "Bob", "last_name": "", "username": "",
        "pbp_topic_id": "100", "user_id": "player1", "campaign_name": "Test",
        "last_post_time": now.isoformat(), "last_warned_week": 0,
    }
    candidates = checker._gather_potw_candidates(timestamps, set(), week_ago, "100", state)
    assert len(candidates) == 0

def test_gather_leaderboard_stats_basic():
    _reset()
    now = datetime.now(timezone.utc)
    config = _make_config()
    state = _make_state()

    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "B",
        "username": "alice", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": (now - timedelta(hours=2)).isoformat(),
        "last_warned_week": 0,
    }
    state["message_counts"]["100"] = {"42": 10, "999": 20}
    state["post_timestamps"]["100"] = {
        "42": [(now - timedelta(hours=h)).isoformat() for h in [2, 24, 48, 72, 120]],
        "999": [(now - timedelta(hours=h)).isoformat() for h in [1, 12, 36, 60, 96]],
    }

    stats, global_players, streaks = checker._gather_leaderboard_stats(config, state, now)
    assert len(stats) == 1
    assert stats[0]["name"] == "TestCampaign"
    assert stats[0]["total_7d"] > 0
    assert stats[0]["gm_7d"] > 0
    assert stats[0]["player_7d"] > 0
    assert "42" in global_players
    assert global_players["42"]["full_name"] == "Alice B"

def test_gather_leaderboard_stats_empty():
    _reset()
    now = datetime.now(timezone.utc)
    config = _make_config()
    state = _make_state()

    stats, global_players, streaks = checker._gather_leaderboard_stats(config, state, now)
    assert len(stats) == 1  # Campaign exists but with no data
    assert stats[0]["total_7d"] == 0
    assert len(global_players) == 0
    assert len(streaks) == 0

def test_leaderboard_includes_streaks():
    _reset()
    now = datetime.now(timezone.utc)
    config = _make_config()
    state = _make_state()

    state["players"]["100:42"] = {
        "user_id": "42", "first_name": "Alice", "last_name": "B",
        "username": "alice", "campaign_name": "TestCampaign",
        "pbp_topic_id": "100", "last_post_time": now.isoformat(),
        "last_warned_week": 0,
    }
    state["message_counts"]["100"] = {"42": 10, "999": 20}
    # 5 consecutive days of posts
    state["post_timestamps"]["100"] = {
        "42": [(now - timedelta(days=d, hours=3)).isoformat() for d in range(5)],
        "999": [(now - timedelta(hours=h)).isoformat() for h in [1, 12, 36, 60, 96]],
    }

    stats, global_players, streaks = checker._gather_leaderboard_stats(config, state, now)
    assert len(streaks) >= 1
    assert streaks[0]["name"] == "Alice B"
    assert streaks[0]["streak"] >= 2

    result = checker._format_leaderboard(stats, global_players, now, streaks)
    assert "Longest Active Streaks" in result
    assert "Alice B" in result
