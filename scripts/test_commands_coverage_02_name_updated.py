"""Tests extracted from test_commands_coverage.py — bin 2.

Sections in this file:
  - Name updated
  - scheduled/poll_result.py
"""
"""
Coverage tests for:
  commands/queue_io.py
  commands/player_registry.py
  scheduled/poll_result.py
  scheduled/diagnostic.py
  scheduled/reports.py  (partial — tg-calling functions mocked)
"""
import sys, os, json, pytest, tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

@pytest.fixture
def tmp_queues(tmp_path, monkeypatch):
    """Redirect queue_io file operations to a temp directory."""
    monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path)
    return tmp_path

def _pr_config():
    return {
        "group_id": -1001,
        "topic_pairs": [{
            "pbp_topic_ids": [100], "code": "C01",
            "name": "DF", "hybrid_live": True,
            "chat_topic_id": 21514,
            "poll_options": ["Friday", "Saturday", "Either", "Both", "Can't make it"],
            "allows_multiple_answers": False,
        }]
    }

def _rpt_config():
    return {
        "group_id": -1001,
        "bot_topic_id": 999,
        "gm_user_ids": [999],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C00", "name": "R",
             "gm_user_ids": [999], "chat_topic_id": 21514}
        ]
    }

# ═══════════════════════════════════════════════════════════════════════════════

from commands.player_registry import (
    get_or_assign_id, get_player_id, format_id, build_registry
)


def test_get_or_assign_id_gm():
    state = {}
    pid = get_or_assign_id("100", "GM1", "Lewis", True, state)
    assert pid == 0


def test_get_or_assign_id_player():
    state = {}
    pid = get_or_assign_id("100", "U1", "Alice", False, state)
    assert pid == 1


def test_get_or_assign_id_sequential():
    state = {}
    get_or_assign_id("100", "U1", "Alice", False, state)
    pid2 = get_or_assign_id("100", "U2", "Bob", False, state)
    assert pid2 == 2


def test_get_or_assign_id_existing():
    state = {}
    pid1 = get_or_assign_id("100", "U1", "Alice", False, state)
    pid2 = get_or_assign_id("100", "U1", "Alice Updated", False, state)
    assert pid1 == pid2
    # Name updated
    assert state["player_registry"]["100"]["U1"]["name"] == "Alice Updated"


def test_get_player_id_found():
    state = {"player_registry": {"100": {"U1": {"id": 3, "name": "Alice"}}}}
    assert get_player_id("100", "U1", state) == 3


def test_get_player_id_not_found():
    assert get_player_id("100", "U99", {}) is None


def test_format_id():
    assert format_id(0) == "#00"
    assert format_id(1) == "#01"
    assert format_id(10) == "#10"


def test_build_registry_empty():
    result = build_registry("100", "Kibwe", {}, {})
    assert "No players" in result


@patch("commands.player_registry.helpers")
def test_build_registry_with_players(mock_helpers):
    mock_helpers.get_label.return_value = "C06: Kibwe"
    state = {
        "player_registry": {"100": {
            "U1": {"id": 1, "name": "Alice", "joined": "2026-01-01"},
            "U2": {"id": 2, "name": "Bob", "joined": "2026-01-02"},
        }},
        "players": {"100:U1": {}},
        "removed_players": {"100:U2": {}},
    }
    result = build_registry("100", "Kibwe", {}, state)
    assert "Alice" in result
    assert "Bob" in result
    assert "[removed]" in result
    assert "[inactive]" not in result or "Alice" not in result.split("[inactive]")[0]



# ═══════════════════════════════════════════════════════════════════════════════
# scheduled/poll_result.py
