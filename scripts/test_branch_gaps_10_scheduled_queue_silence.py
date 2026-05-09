"""Coverage tests extracted from test_branch_gaps.py — bin 10.

Sections in this file:
  - scheduled/queue_silence.py

Targeted tests for specific uncovered branches in the production
modules listed above. Module imports are duplicated from the original
``test_branch_gaps.py`` header; per-section helper functions are
extracted alongside their sections.
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


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


