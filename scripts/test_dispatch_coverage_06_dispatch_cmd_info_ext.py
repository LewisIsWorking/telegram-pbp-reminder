"""Tests extracted from test_dispatch_coverage.py — bin 6.

Sections in this file:
  - dispatch/cmd_info_ext.py
  - dispatch/poll_notify.py
  - dispatch/poll_notify.py
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
# dispatch/cmd_info_ext.py

# ═══════════════════════════════════════════════════════════════════════════════

from dispatch.cmd_info_ext import handle as handle_ext


def _ext_ctx(cmd):
    return {
        "cmd_word": cmd, "text": cmd, "group_id": -1, "reply_topic": 999,
        "pid": "100", "campaign_name": "Kibwe", "user_id": "U1",
        "user_name": "Alice", "state": {}, "config": {}, "gm_ids": set(),
    }


def test_handle_ext_waiting():
    ctx = _ext_ctx("/waiting")
    with patch("dispatch.cmd_info_ext.tg.send_message") as ms:
        with patch("commands.waiting.scan_transcripts", return_value={}):
            result = handle_ext(ctx)
    assert result is True


def test_handle_ext_session():
    ctx = _ext_ctx("/session")
    with patch("dispatch.cmd_info_ext.tg.send_message"):
        with patch("commands.session.build_session", return_value="S5"):
            result = handle_ext(ctx)
    assert result is True


def test_handle_ext_health():
    ctx = _ext_ctx("/health")
    with patch("dispatch.cmd_info_ext.tg.send_message"):
        with patch("commands.health.build_health", return_value="ok"):
            result = handle_ext(ctx)
    assert result is True


def test_handle_ext_queuestats():
    ctx = _ext_ctx("/queuestats")
    with patch("dispatch.cmd_info_ext.tg.send_message"):
        with patch("commands.queue_stats.build_queue_stats", return_value="stats"):
            result = handle_ext(ctx)
    assert result is True


def test_handle_ext_reactions():
    ctx = _ext_ctx("/reactions")
    with patch("dispatch.cmd_info_ext.tg.send_message"):
        with patch("commands.reactions.build_reactions", return_value="r"):
            result = handle_ext(ctx)
    assert result is True


def test_handle_ext_timeline():
    ctx = _ext_ctx("/timeline")
    with patch("dispatch.cmd_info_ext.tg.send_message"):
        with patch("commands.timeline.build_timeline", return_value="t"):
            result = handle_ext(ctx)
    assert result is True


def test_handle_ext_search():
    ctx = {**_ext_ctx("/search"), "text": "/search fire giant"}
    with patch("dispatch.cmd_search.handle_search") as ms:
        result = handle_ext(ctx)
    assert result is True
    ms.assert_called_once()


def test_handle_ext_registry():
    ctx = _ext_ctx("/registry")
    with patch("dispatch.cmd_info_ext.tg.send_message"):
        with patch("commands.player_registry.build_registry", return_value="r"):
            result = handle_ext(ctx)
    assert result is True


def test_handle_ext_unknown():
    ctx = _ext_ctx("/unknowncmd")
    result = handle_ext(ctx)
    assert result is False



# ═══════════════════════════════════════════════════════════════════════════════
# dispatch/poll_notify.py
