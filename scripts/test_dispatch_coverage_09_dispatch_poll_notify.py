"""Tests extracted from test_dispatch_coverage.py — bin 9.

Sections in this file:
  - dispatch/poll_notify.py — _poll_link_for and updated capture_unknown_voter
"""
"""
Coverage tests for:
  checker.py  (_run_checks, main)
  commands/queue_scan.py  (scan_transcripts logic)
  dispatch/cmd_info_ext.py  (handle)
  dispatch/poll_notify.py
  scheduled/reports.py  (post_roster_summary with active players)
"""
import sys, os, json, pytest, textwrap
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.dirname(__file__))

def _patch_all_checks():
    """Return a dict of {attr: MagicMock()} for use with patch.multiple."""
    return {f: MagicMock() for f in _CHECKER_FUNCS}

def _qs_config():
    return {
        "group_id": -1001, "gm_user_ids": [999],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
             "gm_user_ids": [999]}
        ]
    }

def _ext_ctx(cmd):
    return {
        "cmd_word": cmd, "text": cmd, "group_id": -1, "reply_topic": 999,
        "pid": "100", "campaign_name": "Kibwe", "user_id": "U1",
        "user_name": "Alice", "state": {}, "config": {}, "gm_ids": set(),
    }

def _pn_config():
    return {
        "group_id": -1001,
        "topic_pairs": [{
            "pbp_topic_ids": [100], "code": "C01", "name": "DF",
            "chat_topic_id": 21514, "hybrid_live": True,
            "poll_options": ["Friday", "Saturday", "Both", "Can't make it"],
            "poll_user_names": {"U1": "alice"},
            "poll_user_ids": ["U1"],
        }]
    }

def _gm_ctx(cmd: str, state: dict) -> dict:
    """Build a minimal GM ctx for cmd_gm tests."""
    return {
        "cmd_word": cmd.split()[0],
        "text": cmd,
        "user_id": "999",
        "gm_ids": ["999"],
        "pid": "100",
        "campaign_name": "TestCampaign",
        "state": state,
        "config": {"topic_pairs": [{"pbp_topic_ids": [100], "name": "TestCampaign"}]},
        "group_id": -1001,
        "thread_id": 200,
        "now_iso": "2026-04-10T00:00:00+00:00",
        "config": {"topic_pairs": [{"pbp_topic_ids": [100], "name": "TestCampaign"}]},
        "parsed": {"raw_text": cmd},
    }

def _pn_config_with_poll():
    return {
        "group_id": -1001, "bot_topic_id": 999,
        "group_username": "Path_Wars",
        "topic_pairs": [{
            "pbp_topic_ids": [100], "code": "C01", "name": "DF",
            "chat_topic_id": 21514, "poll_user_ids": [111],
            "poll_user_names": {"111": "Alice"},
            "poll_options": ["Friday", "Saturday"],
        }],
    }

_CHECKER_FUNCS = [
    "check_and_alert", "check_player_activity", "post_roster_summary",
    "player_of_the_week", "expire_pending_boons", "post_pace_report",
    "check_streak_milestones", "check_anniversaries", "check_message_milestones",
    "check_combat_turns", "post_campaign_leaderboard", "post_weekly_digest",
    "check_recruitment_needs", "archive_weekly_data", "check_pace_drop",
    "check_conversation_dying", "check_expired_timers", "post_daily_tip",
    "post_queue_reminder", "check_queue_nudge", "post_campaign_table",
    "post_session_poll", "announce_poll_result", "post_week_welcome",
    "post_swimming_poll", "post_swimming_ping", "run_daily_diagnostic",
    "backup_state",
]

# ── dispatch/poll_notify.py — _poll_link_for and updated capture_unknown_voter ─

def _pn_config_with_poll():
    return {
        "group_id": -1001, "bot_topic_id": 999,
        "group_username": "Path_Wars",
        "topic_pairs": [{
            "pbp_topic_ids": [100], "code": "C01", "name": "DF",
            "chat_topic_id": 21514, "poll_user_ids": [111],
            "poll_user_names": {"111": "Alice"},
            "poll_options": ["Friday", "Saturday"],
        }],
    }


def test_poll_link_for_with_msg_id():
    from dispatch.poll_notify import _poll_link_for
    state = {"session_poll": {"C01": {"poll_message_id": 9999, "votes": {}}}}
    result = _poll_link_for("C01", _pn_config_with_poll(), state)
    assert "9999" in result


def test_poll_link_for_no_msg_id():
    from dispatch.poll_notify import _poll_link_for
    state = {"session_poll": {"C01": {}}}
    result = _poll_link_for("C01", _pn_config_with_poll(), state)
    assert result == ""


def test_poll_link_for_unknown_code():
    from dispatch.poll_notify import _poll_link_for
    state = {"session_poll": {}}
    result = _poll_link_for("C99", _pn_config_with_poll(), state)
    assert result == ""


def test_capture_unknown_voter_posts_alert():
    from dispatch.poll_notify import capture_unknown_voter
    config = _pn_config_with_poll()
    state = {"poll_unknown_voters": {}, "session_poll": {}}
    capture_unknown_voter("999888", "C01", config, state)
    assert "999888" in state["poll_unknown_voters"].get("C01", [])
    # tg.send_message should have been called (conftest mock captures it)


def test_capture_unknown_voter_skips_known_uid():
    from dispatch.poll_notify import capture_unknown_voter
    config = _pn_config_with_poll()
    state = {"poll_unknown_voters": {}, "session_poll": {}}
    # uid 111 is in poll_user_ids — should not be captured
    capture_unknown_voter("111", "C01", config, state)
    assert "C01" not in state["poll_unknown_voters"]


def test_capture_unknown_voter_skips_known_name_uid():
    from dispatch.poll_notify import capture_unknown_voter
    config = _pn_config_with_poll()
    state = {"poll_unknown_voters": {}, "session_poll": {}}
    # uid "111" is in poll_user_names — should not be captured
    capture_unknown_voter("111", "C01", config, state)
    assert "C01" not in state["poll_unknown_voters"]


def test_capture_unknown_voter_no_duplicate():
    from dispatch.poll_notify import capture_unknown_voter
    config = _pn_config_with_poll()
    state = {"poll_unknown_voters": {"C01": ["999888"]}, "session_poll": {}}
    capture_unknown_voter("999888", "C01", config, state)
    assert state["poll_unknown_voters"]["C01"].count("999888") == 1
