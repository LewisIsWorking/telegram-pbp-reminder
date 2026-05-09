"""Coverage tests extracted from test_commands_coverage.py — bin 2.

Sections in this file:
  - Name updated
  - scheduled/poll_result.py
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


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
