"""Tests for checker.py — format group.

Extracted from test_checker.py during the test-split refactor. Module
imports, helper functions (_make_config, _make_state, _make_msg, _utc,
_reset, _run_all), and the _LOGS_DIR redirection setup all live in the
shared ``_test_checker_helpers`` module so this file contains test
functions only.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_format_boon_result():
    _reset()
    boons = ["Boon A", "Boon B", "Boon C"]
    result = checker._format_boon_result(boons, 1, "Winner!", "Chosen boon")
    assert "✓" in result
    assert "<s>" in result
    assert "Boon B" in result.split("✓")[0]  # Chosen boon before checkmark
    assert "Chosen boon:" in result

def test_format_boon_result_html_escapes():
    _reset()
    boons = ["<script>", "Normal"]
    result = checker._format_boon_result(boons, 0, "Test & Win", "Label")
    assert "&lt;script&gt;" in result
    assert "Test &amp; Win" in result

def test_format_leaderboard():
    now = _utc(2026, 2, 20, 12, 0)
    campaign_stats = [
        {
            "name": "Alpha",
            "total_7d": 30,
            "player_7d": 20,
            "gm_7d": 10,
            "trend_icon": "📈",
            "avg_gap_str": "4.0h",
            "player_avg_gap": 5.0,
            "player_avg_gap_str": "5.0h",
            "last_post_str": "today",
            "days_since_last": 0.1,
            "top_players": [{"full_name": "Alice B", "username": "alice", "count": 12}],
        },
        {
            "name": "Bravo",
            "total_7d": 0,
            "player_7d": 0,
            "gm_7d": 0,
            "trend_icon": "💤",
            "avg_gap_str": "N/A",
            "player_avg_gap": None,
            "player_avg_gap_str": "N/A",
            "last_post_str": "5d ago",
            "days_since_last": 5.0,
            "top_players": [],
        },
    ]
    global_players = {
        "u1": {"full_name": "Alice B", "username": "alice", "count": 12, "campaigns": 1},
    }
    result = checker._format_leaderboard(campaign_stats, global_players, now)
    assert "Weekly Campaign Leaderboard" in result
    assert "Alpha" in result
    assert "Dead campaigns" in result
    assert "Bravo" in result
    assert "Alice B" in result
    assert "Fastest player response gaps" in result

def test_format_log_entry_text():
    parsed = {
        "user_name": "Alice", "user_last_name": "B", "user_id": "42",
        "msg_time_iso": "2026-02-26T14:30:05+00:00",
        "raw_text": "I attack the goblin!", "media_type": None, "caption": "",
    }
    result = checker._format_log_entry(parsed, {"999"})
    assert "**Alice B**" in result
    assert "I attack the goblin!" in result
    assert "[GM]" not in result
    assert "2026-02-26 14:30:05" in result

def test_format_log_entry_gm():
    parsed = {
        "user_name": "Lewis", "user_last_name": "", "user_id": "999",
        "msg_time_iso": "2026-02-26T14:30:05+00:00",
        "raw_text": "The goblin snarls.", "media_type": None, "caption": "",
    }
    result = checker._format_log_entry(parsed, {"999"})
    assert "[GM]" in result

def test_format_log_entry_image():
    parsed = {
        "user_name": "Alice", "user_last_name": "", "user_id": "42",
        "msg_time_iso": "2026-02-26T14:30:05+00:00",
        "raw_text": "", "media_type": "image", "caption": "battle map",
    }
    result = checker._format_log_entry(parsed, {"999"})
    assert "[image]" in result
    assert "battle map" in result

def test_format_log_entry_sticker():
    parsed = {
        "user_name": "Bob", "user_last_name": "", "user_id": "42",
        "msg_time_iso": "2026-02-26T14:30:05+00:00",
        "raw_text": "", "media_type": "sticker:😂", "caption": "",
    }
    result = checker._format_log_entry(parsed, {"999"})
    assert "[sticker 😂]" in result

def test_format_elapsed():
    """_format_elapsed formats times correctly."""
    assert "30m" in checker._format_elapsed(0.5)
    assert "3h" in checker._format_elapsed(3.2)
    assert "1d" in checker._format_elapsed(26.5)
