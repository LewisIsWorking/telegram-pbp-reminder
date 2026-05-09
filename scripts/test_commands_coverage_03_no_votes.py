"""Tests extracted from test_commands_coverage.py — bin 3.

Sections in this file:
  - No votes — tally is "No votes"
  - scheduled/diagnostic.py
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

from scheduled.poll_result import announce_poll_result

_FRIDAY_3PM = datetime(2026, 4, 3, 15, 0, tzinfo=timezone.utc)  # Friday 15:00
_THURSDAY   = datetime(2026, 4, 2, 15, 0, tzinfo=timezone.utc)


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


def test_poll_result_skips_non_friday():
    state = {}
    announce_poll_result(_pr_config(), state, now=_THURSDAY)
    assert "poll_history" not in state


def test_poll_result_skips_before_3pm():
    morning = datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc)
    state = {}
    announce_poll_result(_pr_config(), state, now=morning)
    assert "poll_history" not in state


def test_poll_result_skips_non_hybrid():
    config = {"group_id": -1, "topic_pairs": [{
        "pbp_topic_ids": [100], "code": "C00", "name": "R",
        "chat_topic_id": 100,
    }]}
    state = {}
    announce_poll_result(config, state, now=_FRIDAY_3PM)
    assert "poll_history" not in state


def test_poll_result_skips_already_announced():
    state = {"session_poll": {"C01": {"result_announced": True, "votes": {}}}}
    announce_poll_result(_pr_config(), state, now=_FRIDAY_3PM)
    assert not state.get("poll_history", {}).get("C01")


def test_poll_result_skips_no_chat_topic():
    config = {"group_id": -1, "topic_pairs": [{
        "pbp_topic_ids": [100], "code": "C01",
        "hybrid_live": True, "poll_options": ["A"],
    }]}
    state = {"session_poll": {"C01": {"votes": {}}}}
    announce_poll_result(config, state, now=_FRIDAY_3PM)
    assert not state.get("poll_history", {}).get("C01")


def test_poll_result_winner():
    state = {"session_poll": {"C01": {
        "votes": {"0": ["U1", "U2"], "1": ["U3"]},
    }}}
    announce_poll_result(_pr_config(), state, now=_FRIDAY_3PM)
    assert state["session_poll"]["C01"].get("result_announced") is True
    assert "poll_history" in state


def test_poll_result_tie():
    state = {"session_poll": {"C01": {
        "votes": {"0": ["U1"], "1": ["U2"]},
    }}}
    announce_poll_result(_pr_config(), state, now=_FRIDAY_3PM)
    assert "poll_results" in state


def test_poll_result_no_votes():
    state = {"session_poll": {"C01": {"votes": {}}}}
    announce_poll_result(_pr_config(), state, now=_FRIDAY_3PM)
    # No votes — tally is "No votes"
    assert "poll_results" in state


def test_poll_result_with_history():
    state = {
        "session_poll": {"C01": {"votes": {"0": ["U1", "U2"]}}},
        "poll_history": {"C01": {"wins": {"0": 3}}},
    }
    announce_poll_result(_pr_config(), state, now=_FRIDAY_3PM)
    # All-time history should be shown (wins accumulated)
    assert state["poll_history"]["C01"]["wins"].get("0", 0) >= 3



# ═══════════════════════════════════════════════════════════════════════════════
# scheduled/diagnostic.py
