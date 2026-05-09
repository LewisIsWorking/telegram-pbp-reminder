"""test_helpers.py — bin 1.

  - misc (part a)
"""
"""Tests for helpers.py utilities."""

import sys
from datetime import datetime, timezone, timedelta

import helpers



def _utc(*args):
    """Shorthand for timezone-aware UTC datetime."""
    return datetime(*args, tzinfo=timezone.utc)

def _run_all():
    """Find and run all test_ functions, report results."""
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

def test_hours_since():
    now = _utc(2026, 1, 10, 12, 0)
    then = _utc(2026, 1, 10, 6, 30)
    assert abs(helpers.hours_since(now, then) - 5.5) < 0.001

def test_days_since():
    now = _utc(2026, 1, 10, 12, 0)
    then = _utc(2026, 1, 7, 12, 0)
    assert helpers.days_since(now, then) == 3.0

def test_interval_elapsed_none():
    assert helpers.interval_elapsed(None, 7, _utc(2026, 1, 10, 12, 0)) is True

def test_interval_elapsed_fresh():
    now = _utc(2026, 1, 10, 12, 0)
    last = _utc(2026, 1, 10, 10, 0).isoformat()
    assert helpers.interval_elapsed(last, 1, now) is False

def test_interval_elapsed_stale():
    now = _utc(2026, 1, 10, 12, 0)
    last = _utc(2026, 1, 8, 12, 0).isoformat()
    assert helpers.interval_elapsed(last, 1, now) is True

def test_timestamps_in_window_after_only():
    now = _utc(2026, 1, 10, 12, 0)
    cutoff = now - timedelta(hours=24)
    timestamps = [
        (now - timedelta(hours=h)).isoformat()
        for h in [1, 5, 25, 50]
    ]
    result = helpers.timestamps_in_window(timestamps, cutoff)
    assert len(result) == 2

def test_timestamps_in_window_bounded():
    now = _utc(2026, 1, 10, 12, 0)
    after = now - timedelta(hours=48)
    before = now - timedelta(hours=24)
    timestamps = [
        (now - timedelta(hours=h)).isoformat()
        for h in [1, 30, 50]
    ]
    result = helpers.timestamps_in_window(timestamps, after, before)
    assert len(result) == 1

def test_timestamps_in_window_empty():
    assert helpers.timestamps_in_window([], _utc(2026, 1, 1, 0, 0)) == []

def test_avg_gap_hours_basic():
    times = [
        _utc(2026, 1, 10, 0, 0),
        _utc(2026, 1, 10, 6, 0),
        _utc(2026, 1, 10, 12, 0),
    ]
    assert helpers.avg_gap_hours(times) == 6.0

def test_avg_gap_hours_insufficient():
    assert helpers.avg_gap_hours([_utc(2026, 1, 10, 0, 0)]) is None
    assert helpers.avg_gap_hours([]) is None

def test_calc_avg_gap_str():
    now = _utc(2026, 1, 10, 12, 0)
    timestamps = [
        (now - timedelta(hours=h)).isoformat()
        for h in [0, 6, 12]
    ]
    result = helpers.calc_avg_gap_str(timestamps)
    assert "6.0 hours" == result

def test_calc_avg_gap_str_insufficient():
    assert helpers.calc_avg_gap_str([]) == "N/A"
    assert helpers.calc_avg_gap_str([_utc(2026, 1, 1, 0, 0).isoformat()]) == "N/A"

def test_deduplicate_posts_within_session():
    base = _utc(2026, 1, 10, 12, 0)
    posts = [
        base,
        base + timedelta(minutes=3),
        base + timedelta(minutes=8),
    ]
    sessions = helpers.deduplicate_posts(posts)
    assert len(sessions) == 1

def test_deduplicate_posts_across_sessions():
    base = _utc(2026, 1, 10, 12, 0)
    posts = [
        base,
        base + timedelta(minutes=5),
        base + timedelta(minutes=30),  # New session
        base + timedelta(hours=2),     # New session
    ]
    sessions = helpers.deduplicate_posts(posts)
    assert len(sessions) == 3

def test_deduplicate_posts_empty():
    assert helpers.deduplicate_posts([]) == []

def test_fmt_date():
    assert helpers.fmt_date(_utc(2026, 2, 14, 0, 0)) == "2026-02-14 (W7)"

def test_html_escape():
    assert helpers.html_escape("a < b & c > d") == "a &lt; b &amp; c &gt; d"

def test_posts_str():
    assert helpers.posts_str(1) == "1 post"
    assert helpers.posts_str(0) == "0 posts"
    assert helpers.posts_str(5) == "5 posts"

def test_display_name():
    assert helpers.display_name("Alice") == "Alice"
    assert helpers.display_name("Alice", last_name="B") == "Alice B"
    assert helpers.display_name("Alice", "alice_b", "B") == "Alice B (@alice_b)"

def test_player_mention():
    p = {"first_name": "Bob", "last_name": "S", "username": "bobs"}
    assert helpers.player_mention(p) == "Bob S (@bobs)"
    assert helpers.player_mention({}) == "Unknown"

def test_player_full_name():
    p = {"first_name": "Bob", "last_name": "S", "username": "bobs"}
    assert helpers.player_full_name(p) == "Bob S"
    assert helpers.player_full_name({"first_name": "Bob"}) == "Bob"
    assert helpers.player_full_name({}) == "Unknown"

def test_rank_icon():
    assert helpers.rank_icon(0) == "🥇"
    assert helpers.rank_icon(2) == "🥉"
    assert helpers.rank_icon(3) == "4."
    assert helpers.rank_icon(9) == "10."
