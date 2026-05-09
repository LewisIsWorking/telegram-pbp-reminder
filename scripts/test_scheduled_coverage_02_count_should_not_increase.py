"""Coverage tests extracted from test_scheduled_coverage.py — bin 2.

Sections in this file:
  - Count should not increase
  - scheduled/swimming_poll.py
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


# ═══════════════════════════════════════════════════════════════════════════════

from scheduled.queue_nudge import check_queue_nudge, _gm_mentions


def _qn_config():
    return {
        "group_id": -1001, "bot_topic_id": 999,
        "gm_user_ids": [999],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
             "gm_user_ids": [999]}
        ]
    }


def test_gm_mentions_with_username():
    state = {"players": {"x": {"user_id": "999", "username": "pathwars"}}}
    result = _gm_mentions(_qn_config(), state, "100")
    assert "@pathwars" in result


def test_gm_mentions_with_first_name_only():
    state = {"players": {"x": {"user_id": "999", "first_name": "Lewis", "username": ""}}}
    result = _gm_mentions(_qn_config(), state, "100")
    assert "Lewis" in result


def test_gm_mentions_fallback():
    state = {"players": {}}
    result = _gm_mentions(_qn_config(), state, "100")
    assert "@PathWars" in result


def test_gm_mentions_no_gm_ids():
    config = {"group_id": -1, "topic_pairs": [{"pbp_topic_ids": [100], "gm_user_ids": []}]}
    result = _gm_mentions(config, {}, "100")
    assert "@PathWars" in result


def test_queue_nudge_no_bot_topic():
    config = {"group_id": -1001}
    state = {}
    check_queue_nudge(config, state)
    assert "queue_nudged" not in state


@patch("scheduled.queue_nudge.scan_transcripts", return_value={})
def test_queue_nudge_no_entries(mock_scan):
    state = {}
    check_queue_nudge(_qn_config(), state)
    assert state.get("queue_nudged", {}) == {}


@patch("scheduled.queue_nudge.scan_transcripts")
def test_queue_nudge_fresh_entry_not_nudged(mock_scan):
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=10)).strftime("%Y-%m-%d %H:%M:%S")
    mock_scan.return_value = {"100": {
        "campaign": "Kibwe", "code": "C00",
        "entries": [{"name": "Alice", "time": fresh, "link": ""}]
    }}
    state = {}
    check_queue_nudge(_qn_config(), state, now=now)
    assert not state.get("queue_nudged")


@patch("scheduled.queue_nudge.scan_transcripts")
def test_queue_nudge_stale_entry_nudged(mock_scan):
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=55)).strftime("%Y-%m-%d %H:%M:%S")
    mock_scan.return_value = {"100": {
        "campaign": "Kibwe", "code": "C00",
        "entries": [{"name": "Alice", "time": stale, "link": "https://t.me/x"}]
    }}
    state = {}
    check_queue_nudge(_qn_config(), state, now=now)
    assert len(state.get("queue_nudged", {})) == 1


@patch("scheduled.queue_nudge.scan_transcripts")
def test_queue_nudge_already_nudged_skipped(mock_scan):
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=55)).strftime("%Y-%m-%d %H:%M:%S")
    mock_scan.return_value = {"100": {
        "campaign": "Kibwe", "code": "C00",
        "entries": [{"name": "Alice", "time": stale, "link": ""}]
    }}
    state = {"queue_nudged": {"100:Alice": now.isoformat()}}
    check_queue_nudge(_qn_config(), state, now=now)
    # Count should not increase
    assert len(state["queue_nudged"]) == 1


@patch("scheduled.queue_nudge.scan_transcripts")
def test_queue_nudge_invalid_time_skipped(mock_scan):
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    mock_scan.return_value = {"100": {
        "campaign": "Kibwe", "code": "C00",
        "entries": [{"name": "Alice", "time": "not-a-date", "link": ""}]
    }}
    state = {}
    check_queue_nudge(_qn_config(), state, now=now)
    assert not state.get("queue_nudged")


@patch("scheduled.queue_nudge.scan_transcripts")
def test_queue_nudge_trims_old_entries(mock_scan):
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=55)).strftime("%Y-%m-%d %H:%M:%S")
    # 205 pre-existing entries + 1 new stale entry triggers the trim
    mock_scan.return_value = {"100": {
        "campaign": "Kibwe", "code": "C00",
        "entries": [{"name": "Zara", "time": stale, "link": ""}]
    }}
    state = {"queue_nudged": {f"k{i}": now.isoformat() for i in range(205)}}
    check_queue_nudge(_qn_config(), state, now=now)
    assert len(state["queue_nudged"]) <= 201  # trimmed to 200 + possibly 1 new



# ═══════════════════════════════════════════════════════════════════════════════
# scheduled/swimming_poll.py
