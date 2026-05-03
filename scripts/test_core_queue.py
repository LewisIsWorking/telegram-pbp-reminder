"""Coverage tests for commands/queue.py."""
import sys, os, json, pytest, tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.dirname(__file__))

# ═══════════════════════════════════════════════════════════════════════════════
# commands/queue.py
# ═══════════════════════════════════════════════════════════════════════════════

from commands.queue import build_queue


def _q_config(priority_pid=None):
    pairs = [{"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe", "gm_user_ids": [999]}]
    if priority_pid:
        pairs[0]["queue_priority"] = True
    return {"group_id": -1, "gm_user_ids": [999], "topic_pairs": pairs}


@patch("commands.queue.scan_transcripts", return_value={})
def test_build_queue_empty(mock_scan):
    result = build_queue(_q_config(), {})
    assert "All caught up" in result


@patch("commands.queue.scan_transcripts")
def test_build_queue_with_entries(mock_scan):
    now = datetime.now(timezone.utc)
    t = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    mock_scan.return_value = {"100": {
        "campaign": "Kibwe", "code": "C00",
        "entries": [{"name": "Alice", "time": t, "preview": "Hello", "link": ""}]
    }}
    result = build_queue(_q_config(), {})
    assert "Alice" in result
    assert "C00" in result


@patch("commands.queue.scan_transcripts")
def test_build_queue_with_link(mock_scan):
    now = datetime.now(timezone.utc)
    t = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    mock_scan.return_value = {"100": {
        "campaign": "Kibwe", "code": "C00",
        "entries": [{"name": "Alice", "time": t, "preview": "Hi",
                     "link": "https://t.me/x/100/99"}]
    }}
    result = build_queue(_q_config(), {})
    assert "t.me" in result


@patch("commands.queue.scan_transcripts")
def test_build_queue_priority_first(mock_scan):
    now = datetime.now(timezone.utc)
    t = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    mock_scan.return_value = {
        "100": {"campaign": "Kibwe", "code": "C00",
                "entries": [{"name": "Alice", "time": t, "preview": "x", "link": ""}]},
        "200": {"campaign": "Other", "code": "C01",
                "entries": [{"name": "Bob", "time": t, "preview": "y", "link": ""}]},
    }
    config = {
        "group_id": -1, "gm_user_ids": [999],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
             "gm_user_ids": [999], "queue_priority": True},
            {"pbp_topic_ids": [200], "code": "C01", "name": "Other", "gm_user_ids": [999]},
        ]
    }
    result = build_queue(config, {})
    # Kibwe (priority) should appear before Other
    assert result.index("Kibwe") < result.index("Other")


@patch("commands.queue.scan_transcripts")
def test_build_queue_numeric_priority_ordering(mock_scan):
    """Numeric queue_priority: lower number = higher position (0 > 1 > default 2)."""
    now = datetime.now(timezone.utc)
    t = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    mock_scan.return_value = {
        "100": {"campaign": "DarkPockets", "code": "C11",
                "entries": [{"name": "A", "time": t, "preview": "x", "link": ""}]},
        "200": {"campaign": "Kibwe",      "code": "C06",
                "entries": [{"name": "B", "time": t, "preview": "y", "link": ""}]},
        "300": {"campaign": "Other",      "code": "C00",
                "entries": [{"name": "C", "time": t, "preview": "z", "link": ""}]},
    }
    config = {
        "group_id": -1, "gm_user_ids": [999],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C11", "name": "DarkPockets",
             "gm_user_ids": [999], "queue_priority": 0},
            {"pbp_topic_ids": [200], "code": "C06", "name": "Kibwe",
             "gm_user_ids": [999], "queue_priority": 1},
            {"pbp_topic_ids": [300], "code": "C00", "name": "Other", "gm_user_ids": [999]},
        ]
    }
    result = build_queue(config, {})
    assert result.index("DarkPockets") < result.index("Kibwe")
    assert result.index("Kibwe") < result.index("Other")


@patch("commands.queue.scan_transcripts")
def test_build_queue_with_scene(mock_scan):
    now = datetime.now(timezone.utc)
    t = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    mock_scan.return_value = {"100": {
        "campaign": "Kibwe", "code": "C00",
        "entries": [{"name": "Alice", "time": t, "preview": "Hi", "link": ""}]
    }}
    state = {"current_scenes": {"100": "The Tower"}}
    result = build_queue(_q_config(), state)
    assert "The Tower" in result


@patch("commands.queue.scan_transcripts")
def test_build_queue_invalid_time(mock_scan):
    mock_scan.return_value = {"100": {
        "campaign": "Kibwe", "code": "C00",
        "entries": [{"name": "Alice", "time": "bad-time", "preview": "Hi", "link": ""}]
    }}
    result = build_queue(_q_config(), {})
    assert "Alice" in result  # should not crash
