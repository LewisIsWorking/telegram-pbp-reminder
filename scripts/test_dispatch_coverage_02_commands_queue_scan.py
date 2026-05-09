"""Tests extracted from test_dispatch_coverage.py — bin 2.

Sections in this file:
  - commands/queue_scan.py (part a)
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

import checker


def test_run_checks_isolates_failures():
    """A failing check should not abort other checks."""
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": [],
               "bot_topic_id": 999}
    state = {}
    call_log = []

    def ok_check(cfg, st, **kw):
        call_log.append("ok")

    def bad_check(cfg, st, **kw):
        raise RuntimeError("simulated failure")

    with patch.object(checker, "_run_checks") as mock_run:
        mock_run.side_effect = lambda c, s: None
        checker._run_checks(config, state)

def test_run_checks_calls_all_checks():
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": [],
               "bot_topic_id": None}
    state = {}
    with patch.multiple("checker", **_patch_all_checks()), \
         patch("checker.build_topic_maps", return_value=MagicMock()):
        checker._run_checks(config, state)

def test_run_checks_catches_exception():
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": [],
               "bot_topic_id": None}
    state = {}
    mocks = _patch_all_checks()
    mocks["check_and_alert"] = MagicMock(side_effect=RuntimeError("boom"))
    with patch.multiple("checker", **mocks), \
         patch("checker.build_topic_maps", return_value=MagicMock()):
        checker._run_checks(config, state)  # should not raise

def test_main_no_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        checker.main()

def test_main_runs(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("GIST_TOKEN", "")
    monkeypatch.setenv("GIST_ID", "")
    state = {"offset": 0, "topics": {}, "players": {}}
    with patch("checker.helpers.load_config", return_value={"group_id": -1,
               "gm_user_ids": [], "topic_pairs": [], "bot_topic_id": None}), \
         patch("checker.helpers.load_settings"), \
         patch("checker.helpers.validate_config", return_value=[]), \
         patch("checker.state_store.load", return_value=state), \
         patch("checker.state_store.save"), \
         patch("checker.tg.get_updates", return_value=[]), \
         patch("checker.process_updates", return_value=0), \
         patch("checker._run_checks"), \
         patch("checker.cleanup_timestamps"), \
         patch("checker.update_transcript_index"):
        checker.main()

def test_main_aborts_on_fatal_config(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    with patch("checker.helpers.load_config", return_value={}), \
         patch("checker.helpers.load_settings"), \
         patch("checker.helpers.validate_config",
               return_value=["ERROR: bad config"]):
        with pytest.raises(SystemExit):
            checker.main()

def test_main_transcript_index_error_isolated(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    state = {"offset": 0, "topics": {}, "players": {}}
    with patch("checker.helpers.load_config", return_value={"group_id": -1,
               "gm_user_ids": [], "topic_pairs": [], "bot_topic_id": None}), \
         patch("checker.helpers.load_settings"), \
         patch("checker.helpers.validate_config", return_value=[]), \
         patch("checker.state_store.load", return_value=state), \
         patch("checker.state_store.save"), \
         patch("checker.tg.get_updates", return_value=[]), \
         patch("checker.process_updates", return_value=0), \
         patch("checker._run_checks"), \
         patch("checker.cleanup_timestamps"), \
         patch("checker.update_transcript_index", side_effect=Exception("x")):
        checker.main()  # should not raise
