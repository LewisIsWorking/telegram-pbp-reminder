"""Tests extracted from test_branch_gaps.py — bin 15.

Sections in this file:
  - dispatch/cmd_gm.py: _canonical_pid and kick from chat topic
  - dispatch/poll_notify.py: _voter_mention
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

# ─── dispatch/cmd_gm.py: _canonical_pid and kick from chat topic ──────────────

def _gm_config():
    return {"topic_pairs": [
        {"code": "C00", "name": "Riddleport",
         "pbp_topic_ids": [66154, 133428],
         "chat_topic_id": 91008},
    ]}


def test_canonical_pid_from_pbp_topic():
    from dispatch.cmd_gm import _canonical_pid
    assert _canonical_pid("66154", _gm_config()) == "66154"


def test_canonical_pid_from_chat_topic():
    from dispatch.cmd_gm import _canonical_pid
    assert _canonical_pid("91008", _gm_config()) == "66154"


def test_canonical_pid_from_combat_topic():
    from dispatch.cmd_gm import _canonical_pid
    assert _canonical_pid("133428", _gm_config()) == "66154"


def test_canonical_pid_unknown_returns_self():
    from dispatch.cmd_gm import _canonical_pid
    assert _canonical_pid("99999", _gm_config()) == "99999"


def test_campaign_name_found():
    from dispatch.cmd_gm import _campaign_name
    assert _campaign_name("66154", _gm_config()) == "Riddleport"


def test_campaign_name_not_found():
    from dispatch.cmd_gm import _campaign_name
    assert _campaign_name("99999", _gm_config()) == ""


# ─── dispatch/poll_notify.py: _voter_mention ─────────────────────────────────

def _mention_config():
    return {"topic_pairs": [
        {"code": "C01", "pbp_topic_ids": [100],
         "poll_user_names": {"8787": "Sestina_The_Banner_Witch"}},
    ]}


def test_voter_mention_from_players_state():
    """Returns @username when player is in state with username set."""
    from dispatch.poll_notify import _voter_mention
    state = {"players": {"100:U1": {"user_id": "U1", "username": "alice", "first_name": "Alice"}}}
    assert _voter_mention("U1", "Alice", _mention_config(), state) == "@alice"


def test_voter_mention_from_poll_user_names():
    """Falls back to poll_user_names when not in state."""
    from dispatch.poll_notify import _voter_mention
    state = {"players": {}}
    result = _voter_mention("8787", "Chris", _mention_config(), state)
    assert result == "@Sestina_The_Banner_Witch"


def test_voter_mention_flags_missing_username_in_state():
    """Flags visibly when player is in state but has no username."""
    from dispatch.poll_notify import _voter_mention
    state = {"players": {"100:U1": {"user_id": "U1", "username": "", "first_name": "Chris"}}}
    result = _voter_mention("U1", "Chris", _mention_config(), state)
    assert "⚠️" in result
    assert "username unknown" in result
    assert "U1" in result


def test_voter_mention_flags_missing_username_not_in_state():
    """Flags visibly when uid not found in state or poll_user_names."""
    from dispatch.poll_notify import _voter_mention
    state = {"players": {}}
    result = _voter_mention("UNKNOWN", "Ghost", _mention_config(), state)
    assert "⚠️" in result
    assert "username unknown" in result
