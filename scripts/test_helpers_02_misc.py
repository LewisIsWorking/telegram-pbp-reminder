"""test_helpers.py — bin 2.

  - misc (part b)
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

def test_trend_icon():
    assert helpers.trend_icon(0, 0) == "💤"
    assert helpers.trend_icon(10, 0) == "🆕"
    assert helpers.trend_icon(20, 10) == "📈"
    assert helpers.trend_icon(5, 10) == "📉"
    assert helpers.trend_icon(10, 10) == "➡️"

def test_fmt_relative_date():
    now = _utc(2026, 1, 10, 12, 0)
    assert "today" in helpers.fmt_relative_date(now, now - timedelta(hours=5))
    assert "yesterday" in helpers.fmt_relative_date(now, now - timedelta(hours=30))
    assert "3d ago" in helpers.fmt_relative_date(now, now - timedelta(days=3))

def test_fmt_brief_relative():
    now = _utc(2026, 1, 10, 12, 0)
    s, d = helpers.fmt_brief_relative(now, None)
    assert s == "never" and d == 999.0

    s, _ = helpers.fmt_brief_relative(now, now - timedelta(minutes=30))
    assert s == "today"

    s, _ = helpers.fmt_brief_relative(now, now - timedelta(hours=5))
    assert "h ago" in s

    s, _ = helpers.fmt_brief_relative(now, now - timedelta(hours=30))
    assert s == "yesterday"

    s, _ = helpers.fmt_brief_relative(now, now - timedelta(days=5))
    assert "5d ago" == s

def test_gm_id_set():
    config = {"gm_user_ids": [123, 456]}
    result = helpers.gm_id_set(config)
    assert result == {"123", "456"}
    assert helpers.gm_id_set({}) == set()

def test_gm_ids_for_campaign_global_fallback():
    config = {
        "gm_user_ids": [111],
        "topic_pairs": [
            {"name": "A", "chat_topic_id": 10, "pbp_topic_ids": [100]},
        ],
    }
    # No per-campaign override, falls back to global
    assert helpers.gm_ids_for_campaign(config, "100") == {"111"}

def test_gm_ids_for_campaign_per_campaign_override():
    config = {
        "gm_user_ids": [111],
        "topic_pairs": [
            {"name": "A", "chat_topic_id": 10, "pbp_topic_ids": [100]},
            {"name": "B", "chat_topic_id": 20, "pbp_topic_ids": [200], "gm_user_ids": [222]},
        ],
    }
    # Campaign A uses global
    assert helpers.gm_ids_for_campaign(config, "100") == {"111"}
    # Campaign B uses its own override
    assert helpers.gm_ids_for_campaign(config, "200") == {"222"}
    # Global GM NOT in campaign B's set
    assert "111" not in helpers.gm_ids_for_campaign(config, "200")

def test_gm_ids_for_campaign_unknown_pid():
    config = {
        "gm_user_ids": [111],
        "topic_pairs": [
            {"name": "A", "chat_topic_id": 10, "pbp_topic_ids": [100]},
        ],
    }
    # Unknown pid falls back to global
    assert helpers.gm_ids_for_campaign(config, "999") == {"111"}

def test_players_by_campaign():
    state = {"players": {
        "A:1": {"pbp_topic_id": "A", "name": "p1"},
        "A:2": {"pbp_topic_id": "A", "name": "p2"},
        "B:3": {"pbp_topic_id": "B", "name": "p3"},
    }}
    result = helpers.players_by_campaign(state)
    assert len(result["A"]) == 2
    assert len(result["B"]) == 1

def test_get_topic_timestamps():
    state = {"post_timestamps": {"A": {"1": ["ts1", "ts2"]}}}
    assert helpers.get_topic_timestamps(state, "A") == {"1": ["ts1", "ts2"]}
    assert helpers.get_topic_timestamps(state, "Z") == {}
    assert helpers.get_topic_timestamps({}, "A") == {}

def test_get_player():
    state = {"players": {"A:1": {"first_name": "Test"}}}
    assert helpers.get_player(state, "A", "1")["first_name"] == "Test"
    assert helpers.get_player(state, "A", "9") == {}
    assert helpers.get_player({}, "A", "1") == {}

def test_build_topic_maps_basic():
    config = {"topic_pairs": [
        {"pbp_topic_ids": [100, 101], "chat_topic_id": 200, "name": "Campaign A"},
        {"pbp_topic_ids": [300], "chat_topic_id": 400, "name": "Campaign B"},
    ]}
    maps = helpers.build_topic_maps(config)
    assert maps.to_canonical["100"] == "100"
    assert maps.to_canonical["101"] == "100"
    assert maps.to_canonical["300"] == "300"
    assert maps.to_chat["100"] == 200
    assert maps.to_name["100"] == "Campaign A"
    assert "101" in maps.all_pbp_ids
    assert "300" in maps.all_pbp_ids

def test_build_topic_maps_caching():
    config = {"topic_pairs": [
        {"pbp_topic_ids": [1], "chat_topic_id": 2, "name": "Test"},
    ]}
    m1 = helpers.build_topic_maps(config)
    m2 = helpers.build_topic_maps(config)
    assert m1 is m2
