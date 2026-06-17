"""Tests extracted from test_branch_gaps.py — bin 11.

Sections in this file:
  - scheduled/queue_silence.py
"""
"""
Targeted tests for every remaining coverage gap.
Organised by file, hitting each uncovered branch.
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

def _gm_ctx(text, pid="100", uid="GM1"):
    return {
        "cmd_word": text.split()[0], "text": text,
        "user_id": uid, "gm_ids": {"GM1"},
        "pid": pid, "group_id": -1, "thread_id": 999,
        "state": {}, "config": {},
        "campaign_name": "Kibwe",
        "now_iso": "2026-04-03T12:00:00+00:00",
        "msg_time_iso": "2026-04-03T12:00:00+00:00",
        "user_name": "Lewis",
        "maps": MagicMock(), "parsed": {"raw_text": "/done 99", "text": "/done 99"},
    }

def _capture_config(placeholders=None):
    return {"group_id": -1, "bot_topic_id": 999, "topic_pairs": [
        {"code": "C01", "pbp_topic_ids": [100],
         "poll_user_ids": placeholders or [111, 222],
         "poll_user_names": {str(u): f"user{u}" for u in (placeholders or [111, 222])}}
    ]}

def _hp_config():
    return {
        "group_id": -1001, "bot_topic_id": 999,
        "leaderboard_topic_id": 888,
        "topic_pairs": [
            {"pbp_topic_ids": [100], "name": "Magni Watch"},
            {"pbp_topic_ids": [200], "name": "Kibwe"},
        ],
    }

def _hp_state(uid="U1"):
    return {
        "players": {
            f"100:{uid}": {"user_id": uid, "pbp_topic_id": 100, "first_name": "Chase"},
            f"200:{uid}": {"user_id": uid, "pbp_topic_id": 200, "first_name": "Chase"},
        }
    }

def _gm_config():
    return {"topic_pairs": [
        {"code": "C00", "name": "Riddleport",
         "pbp_topic_ids": [66154, 133428],
         "chat_topic_id": 91008},
    ]}

def _mention_config():
    return {"topic_pairs": [
        {"code": "C01", "pbp_topic_ids": [100],
         "poll_user_names": {"8787": "Sestina_The_Banner_Witch"}},
    ]}

# ─── scheduled/queue_silence.py ───────────────────────────────────────────────

def test_silent_campaigns_skips_when_has_entries():
    """Campaign with unreplied entries is not considered silent."""
    from scheduled.queue_silence import silent_campaigns
    now = datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc)
    config = {"topic_pairs": [{"pbp_topic_ids": [100], "code": "C00", "name": "Test"}]}
    state = {"topics": {"100": {"last_message_time": "2026-03-01T10:00:00+00:00"}}}
    scanned = {"100": {"entries": [{"name": "Player", "time": "2026-03-01 10:00:00"}]}}
    assert silent_campaigns(config, state, scanned, now) == []


def test_silent_campaigns_skips_when_recent():
    """Campaign last posted 3 days ago is not silent (under 5-day threshold)."""
    from scheduled.queue_silence import silent_campaigns
    now = datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc)
    config = {"topic_pairs": [{"pbp_topic_ids": [100], "code": "C00", "name": "Test"}]}
    last = (now - timedelta(days=3)).isoformat()
    state = {"topics": {"100": {"last_message_time": last}}}
    assert silent_campaigns(config, state, {}, now) == []


def test_silent_campaigns_skips_when_no_topic_data():
    """Campaign with no tracked message time is skipped gracefully."""
    from scheduled.queue_silence import silent_campaigns
    now = datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc)
    config = {"topic_pairs": [{"pbp_topic_ids": [100], "code": "C00", "name": "Test"}]}
    assert silent_campaigns(config, {}, {}, now) == []


def test_silent_campaigns_skips_invalid_timestamp():
    """Invalid ISO timestamp is caught and skipped."""
    from scheduled.queue_silence import silent_campaigns
    now = datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc)
    config = {"topic_pairs": [{"pbp_topic_ids": [100], "code": "C00", "name": "Test"}]}
    state = {"topics": {"100": {"last_message_time": "not-a-date"}}}
    assert silent_campaigns(config, state, {}, now) == []


def test_silent_campaigns_returns_line_when_silent():
    """Campaign with empty queue and 15 days silence returns a formatted line."""
    from scheduled.queue_silence import silent_campaigns
    now = datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc)
    last = (now - timedelta(days=15)).isoformat()
    config = {"topic_pairs": [
        {"pbp_topic_ids": [100], "code": "C08", "name": "Theria", "emoji": "🦄"}
    ]}
    state = {"topics": {"100": {"last_message_time": last}}}
    lines = silent_campaigns(config, state, {}, now)
    assert len(lines) == 1
    assert "C08: Theria" in lines[0]
    assert "no posts for 15d" in lines[0]
    assert "🦄" in lines[0]


def test_silent_campaigns_mixed_active_and_silent():
    """Active campaign with entries is excluded; silent campaign is included."""
    from scheduled.queue_silence import silent_campaigns
    now = datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc)
    old = (now - timedelta(days=20)).isoformat()
    recent = (now - timedelta(days=2)).isoformat()
    config = {"topic_pairs": [
        {"pbp_topic_ids": [100], "code": "C00", "name": "Active", "emoji": "💰"},
        {"pbp_topic_ids": [200], "code": "C08", "name": "Silent", "emoji": "🦄"},
    ]}
    state = {"topics": {
        "100": {"last_message_time": recent},
        "200": {"last_message_time": old},
    }}
    scanned = {"100": {"entries": [{"name": "P"}]}}
    lines = silent_campaigns(config, state, scanned, now)
    assert len(lines) == 1
    assert "C08: Silent" in lines[0]
    assert "no posts for 20d" in lines[0]


def _cross_group_config():
    """Global Path_Wars group + C11 Dark Pockets in a separate group.

    Mirrors the real config: C11 carries a ``group_id`` override and an
    explicit ``group_username: null``.
    """
    return {
        "group_id": -1001661053273, "group_username": "Path_Wars",
        "topic_pairs": [{
            "pbp_topic_ids": [1242, 1825], "code": "C11", "name": "Dark Pockets",
            "group_id": -1003496373617, "group_username": None,
        }],
    }


def test_silent_campaigns_cross_group_link_not_path_wars():
    """Regression: a silent cross-group campaign (C11) must NOT inherit the
    global Path_Wars username — its link points at its own private group."""
    from scheduled.queue_silence import silent_campaigns
    now = datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc)
    last = (now - timedelta(days=9, hours=20)).isoformat()
    state = {"topics": {"1242": {"last_message_time": last}}}
    lines = silent_campaigns(_cross_group_config(), state, {}, now)
    assert len(lines) == 1
    assert "https://t.me/c/3496373617/1242" in lines[0]
    assert "t.me/Path_Wars" not in lines[0]
    assert "no posts for 9d 20h" in lines[0]


# ─── caught-up section ────────────────────────────────────────────────────────

def test_caught_up_campaigns_lists_recent():
    """Campaign with no unreplied entries that posted recently is caught up."""
    from scheduled.queue_silence import caught_up_campaigns
    now = datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc)
    last = (now - timedelta(hours=5)).isoformat()
    config = {"topic_pairs": [
        {"pbp_topic_ids": [100], "code": "C00", "name": "Riddleport", "emoji": "🎲"}
    ]}
    state = {"topics": {"100": {"last_message_time": last}}}
    lines = caught_up_campaigns(config, state, {}, now)
    assert len(lines) == 1
    assert "C00: Riddleport" in lines[0]
    assert "last post 5h ago" in lines[0]
    assert "🎲" in lines[0]


def test_caught_up_campaigns_excludes_silent():
    """A campaign past the silence threshold is NOT in the caught-up section."""
    from scheduled.queue_silence import caught_up_campaigns
    now = datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc)
    last = (now - timedelta(days=9)).isoformat()
    config = {"topic_pairs": [{"pbp_topic_ids": [100], "code": "C08", "name": "Theria"}]}
    state = {"topics": {"100": {"last_message_time": last}}}
    assert caught_up_campaigns(config, state, {}, now) == []


def test_caught_up_campaigns_excludes_unreplied():
    """A campaign with unreplied entries is in the body, not caught-up."""
    from scheduled.queue_silence import caught_up_campaigns
    now = datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc)
    last = (now - timedelta(hours=2)).isoformat()
    config = {"topic_pairs": [{"pbp_topic_ids": [100], "code": "C06", "name": "Kibwe"}]}
    state = {"topics": {"100": {"last_message_time": last}}}
    scanned = {"100": {"entries": [{"name": "P"}]}}
    assert caught_up_campaigns(config, state, scanned, now) == []


def test_caught_up_campaigns_uses_latest_topic():
    """Multi-topic campaign: caught-up uses the most recent topic, not pid[0].

    Riddleport's canonical topic may be quiet while a secondary topic is active;
    the campaign should still count as recently caught up.
    """
    from scheduled.queue_silence import caught_up_campaigns
    now = datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc)
    stale = (now - timedelta(days=9)).isoformat()
    fresh = (now - timedelta(hours=3)).isoformat()
    config = {"topic_pairs": [
        {"pbp_topic_ids": [66154, 133428], "code": "C00", "name": "Riddleport"}
    ]}
    state = {"topics": {
        "66154": {"last_message_time": stale},
        "133428": {"last_message_time": fresh},
    }}
    lines = caught_up_campaigns(config, state, {}, now)
    assert len(lines) == 1
    assert "last post 3h ago" in lines[0]


def test_caught_up_campaigns_cross_group_link():
    """A caught-up cross-group campaign (C11) links to its own group."""
    from scheduled.queue_silence import caught_up_campaigns
    now = datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc)
    last = (now - timedelta(hours=5)).isoformat()
    state = {"topics": {"1242": {"last_message_time": last}}}
    lines = caught_up_campaigns(_cross_group_config(), state, {}, now)
    assert len(lines) == 1
    assert "https://t.me/c/3496373617/1242" in lines[0]
    assert "t.me/Path_Wars" not in lines[0]


def test_caught_up_campaigns_skips_excluded():
    """Queue-excluded campaigns are not advertised as caught up."""
    from scheduled.queue_silence import caught_up_campaigns
    now = datetime(2026, 4, 15, 10, 0, tzinfo=timezone.utc)
    last = (now - timedelta(hours=5)).isoformat()
    config = {"topic_pairs": [
        {"pbp_topic_ids": [100], "code": "C00", "name": "X", "queue_exclude": True}
    ]}
    state = {"topics": {"100": {"last_message_time": last}}}
    assert caught_up_campaigns(config, state, {}, now) == []

