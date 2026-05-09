"""test_helpers.py — bin 3.

  - misc (part c)
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

def test_pace_split():
    now = datetime(2025, 3, 15, 12, 0, 0, tzinfo=timezone.utc)
    topic_ts = {
        "42": [  # Player
            (now - timedelta(hours=h)).isoformat()
            for h in [2, 24, 48, 200]  # 3 this week, 1 last week
        ],
        "999": [  # GM
            (now - timedelta(hours=h)).isoformat()
            for h in [1, 12, 168 + 12]  # 2 this week, 1 last week
        ],
    }
    result = helpers.pace_split(topic_ts, {"999"}, now)
    assert result["player_this"] == 3
    assert result["player_last"] == 1
    assert result["gm_this"] == 2
    assert result["gm_last"] == 1
