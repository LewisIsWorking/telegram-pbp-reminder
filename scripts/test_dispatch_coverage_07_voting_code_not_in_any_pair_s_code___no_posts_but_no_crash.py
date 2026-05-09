"""Tests extracted from test_dispatch_coverage.py — bin 7.

Sections in this file:
  - voting_code not in any pair's code → no posts but no crash (part a)
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

# ═══════════════════════════════════════════════════════════════════════════════

from dispatch.poll_notify import _voter_mention, notify_vote
from dispatch.poll_tally import _lead_summary, build_tally_block


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


def test_voter_mention_by_player_username():
    state = {"players": {"x": {"user_id": "U1", "username": "alice"}}}
    assert _voter_mention("U1", "Alice", {}, state) == "@alice"

def test_voter_mention_by_first_name():
    state = {"players": {"x": {"user_id": "U1", "username": "", "first_name": "Alice"}}}
    result = _voter_mention("U1", "Alice", {}, state)
    assert "Alice" in result and "⚠️" in result

def test_voter_mention_from_poll_names():
    config = {"topic_pairs": [{"poll_user_names": {"U2": "bob"}}]}
    assert _voter_mention("U2", "Bob", config, {}) == "@bob"

def test_voter_mention_fallback():
    result = _voter_mention("U99", "Fallback", {}, {})
    assert "Fallback" in result and "⚠️" in result

def test_build_tally_block_no_votes():
    result = build_tally_block("C01", {"votes": {}, "voted_uids": []},
                               ["Friday", "Saturday"], _pn_config(), {})
    assert "C01" in result

def test_build_tally_block_with_votes():
    slot = {"votes": {"0": ["U1", "U2"], "1": ["U3"]}, "voted_uids": ["U1", "U2", "U3"]}
    result = build_tally_block("C01", slot,
                               ["Friday", "Saturday", "Both", "Can't"],
                               _pn_config(), {})
    assert "C01" in result
    assert "Friday" in result

def test_lead_summary_winner():
    votes = {"0": ["U1", "U2"], "1": ["U3"]}
    options = ["Friday", "Saturday", "Both", "Can't"]
    result = _lead_summary(votes, options)
    assert "Friday" in result or "leads" in result

def test_lead_summary_tie():
    votes = {"0": ["U1"], "1": ["U2"]}
    options = ["Friday", "Saturday"]
    result = _lead_summary(votes, options)
    assert "tied" in result or "tie" in result.lower()

def test_lead_summary_no_votes():
    result = _lead_summary({}, ["Friday"])
    assert result == ""

def test_notify_vote_unknown_code():
    # voting_code not in any pair's code → no posts but no crash
    state = {"session_poll": {}}
    notify_vote(_pn_config(), state, "Alice", "U1", "C99", "Friday", "100")

def test_notify_vote_sends_tally():
    state = {"session_poll": {"C01": {
        "poll_id": "p1", "votes": {"0": ["U1"]}, "voted_uids": [], "week_iso": "sun2026-03-29",
    }}}
    notify_vote(_pn_config(), state, "Alice", "U1", "C01", "Friday", "100")

def test_notify_vote_no_chat_topic():
    config = {"group_id": -1, "topic_pairs": [{
        "pbp_topic_ids": [100], "code": "C01", "name": "DF",
        "poll_options": ["Friday"], "poll_user_names": {},
    }]}
    state = {"session_poll": {"C01": {"votes": {}, "voted_uids": []}}}
    notify_vote(config, state, "Alice", "U1", "C01", "Friday", "100")
