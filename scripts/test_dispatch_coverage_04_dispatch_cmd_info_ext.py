"""Tests extracted from test_dispatch_coverage.py — bin 4.

Sections in this file:
  - dispatch/cmd_info_ext.py (part a)
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

from commands.queue_scan import scan_transcripts


def _qs_config():
    return {
        "group_id": -1001, "gm_user_ids": [999],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
             "gm_user_ids": [999]}
        ]
    }


@patch("commands.queue_scan.helpers")
def test_scan_empty_no_logs(mock_helpers, tmp_path):
    mock_helpers.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
    mock_helpers.is_excluded.return_value = False
    mock_helpers.gm_ids_for_campaign.return_value = {999}
    with patch("commands.queue_scan._LOGS_DIR", tmp_path), \
         patch("commands.queue_io.all_pids", return_value=[]):
        result = scan_transcripts(_qs_config(), {})
    assert result == {}

@patch("commands.queue_scan.helpers")
def test_scan_excluded_campaign(mock_helpers, tmp_path):
    mock_helpers.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
    mock_helpers.is_excluded.return_value = True
    with patch("commands.queue_scan._LOGS_DIR", tmp_path), \
         patch("commands.queue_io.all_pids", return_value=[]):
        result = scan_transcripts(_qs_config(), {})
    assert result == {}

@patch("commands.queue_scan.helpers")
def test_scan_parses_transcript(mock_helpers, tmp_path):
    mock_helpers.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
    mock_helpers.is_excluded.return_value = False
    mock_helpers.gm_ids_for_campaign.return_value = {"999"}

    from datetime import datetime
    now = datetime.now(timezone.utc)
    month = now.strftime("%Y-%m")
    log_dir = tmp_path / "Kibwe"
    log_dir.mkdir()
    (log_dir / f"{month}.md").write_text(
        "**Alice** (2026-03-01 10:00:00):\nHello world\n\n"
        "**GM** [GM] (2026-03-01 11:00:00):\nGot it\n",
        encoding="utf-8"
    )
    with patch("commands.queue_scan._LOGS_DIR", tmp_path), \
         patch("commands.queue_scan._IDS_FILE", tmp_path / "ids.json"), \
         patch("commands.queue_io.all_pids", return_value=[]):
        result = scan_transcripts(_qs_config(), {})
    assert "100" in result
    assert result["100"]["entries"][0]["name"] == "Alice"

@patch("commands.queue_scan.helpers")
def test_scan_floor_filters_old(mock_helpers, tmp_path):
    mock_helpers.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
    mock_helpers.is_excluded.return_value = False
    mock_helpers.gm_ids_for_campaign.return_value = {"999"}

    from datetime import datetime
    now = datetime.now(timezone.utc)
    month = now.strftime("%Y-%m")
    log_dir = tmp_path / "Kibwe"
    log_dir.mkdir()
    (log_dir / f"{month}.md").write_text(
        "**Alice** (2020-01-01 10:00:00):\nOld message\n",
        encoding="utf-8"
    )
    state = {"queue_scan_floor": "2026-01-01"}
    with patch("commands.queue_scan._LOGS_DIR", tmp_path), \
         patch("commands.queue_scan._IDS_FILE", tmp_path / "ids.json"), \
         patch("commands.queue_io.all_pids", return_value=[]):
        result = scan_transcripts(_qs_config(), state)
    assert result == {}

@patch("commands.queue_scan.helpers")
def test_scan_msg_id_in_transcript(mock_helpers, tmp_path):
    mock_helpers.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
    mock_helpers.is_excluded.return_value = False
    mock_helpers.gm_ids_for_campaign.return_value = {"999"}

    from datetime import datetime
    now = datetime.now(timezone.utc)
    month = now.strftime("%Y-%m")
    log_dir = tmp_path / "Kibwe"
    log_dir.mkdir()
    (log_dir / f"{month}.md").write_text(
        "**Alice** (2026-03-01 10:00:00) msg#12345:\nHello\n",
        encoding="utf-8"
    )
    with patch("commands.queue_scan._LOGS_DIR", tmp_path), \
         patch("commands.queue_scan._IDS_FILE", tmp_path / "ids.json"), \
         patch("commands.queue_io.all_pids", return_value=[]):
        result = scan_transcripts(_qs_config(), {})
    assert result["100"]["entries"][0]["message_id"] == "12345"
    assert "12345" in result["100"]["entries"][0]["link"]
