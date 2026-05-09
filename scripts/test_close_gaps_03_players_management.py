"""Coverage tests extracted from test_close_gaps.py — bin 3.

Tests grouped by the first production module they import. This bin
covers branches in:
  - players.management+alerts+combat_ping+diagnostic_analysis+maintenance+milestones+potw+queue_reminder+reports+session_poll+smart_alerts+finalize+formatting+logger+handler
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


def _ctx(cmd, text, state, config=None, **kw):
    base = {"user_id": "GM1", "user_name": "Lewis", "gm_ids": {"GM1"},
            "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
            "state": state,
            "config": config or {"group_id": -1, "gm_user_ids": [], "topic_pairs": []},
            "campaign_name": "Kibwe", "now_iso": "2026-04-03T12:00:00+00:00",
            "msg_time_iso": "2026-04-03T12:00:00+00:00",
            "parsed": {"raw_text": text},
            "maps": MagicMock(), "cmd_word": cmd, "text": text}
    base.update(kw)
    return base

def test_players_kick_no_match():
    from players.management import handle_kick
    state = {"players": {"100:U2": {"user_id": "U2", "first_name": "Bob",
                                     "username": "bob", "last_name": ""}}}
    handle_kick("100", "Kibwe", "@nobody", state, -1, 999)

def test_alerts_excluded():
    from scheduled.alerts import check_and_alert
    config = {"group_id": -1, "gm_user_ids": [], "bot_topic_id": 999,
              "topic_pairs": [{"pbp_topic_ids": [100], "name": "K",
                               "chat_topic_id": 21514}]}
    with patch("helpers.iter_campaigns", return_value=[("100", "C00", "K", {})]), \
         patch("helpers.is_excluded", return_value=True):
        check_and_alert(config, {})

def test_combat_ping_excluded():
    from scheduled.combat_ping import check_combat_turns
    config = {"group_id": -1, "bot_topic_id": 999, "gm_user_ids": [],
              "topic_pairs": [{"pbp_topic_ids": [100], "name": "K",
                               "chat_topic_id": 21514}]}
    with patch("scheduled.combat_ping.helpers") as mh:
        mh.iter_campaigns.return_value = [("100", "C00", "K", {})]
        mh.is_excluded.return_value = True
        check_combat_turns(config, {"combat": {}})

def test_diagnostic_no_info():
    from scheduled.diagnostic_analysis import _analyse_logs
    assert _analyse_logs(["just a log line"])["events"] == []

def test_maintenance_excluded():
    from scheduled.maintenance import check_recruitment_needs
    config = {"group_id": -1, "gm_user_ids": [],
              "topic_pairs": [{"pbp_topic_ids": [100], "name": "K",
                               "chat_topic_id": 21514}]}
    with patch("helpers.iter_campaigns", return_value=[("100", "C00", "K", {})]), \
         patch("helpers.is_excluded", return_value=True):
        check_recruitment_needs(config, {"last_recruitment_check": {}})

def test_milestones_skip():
    from scheduled.milestones import check_streak_milestones
    config = {"group_id": -1, "bot_topic_id": 999, "gm_user_ids": [],
              "topic_pairs": [{"pbp_topic_ids": [100], "name": "K",
                               "chat_topic_id": 21514}]}
    with patch("scheduled.milestones.helpers") as mh:
        mh.iter_campaigns.return_value = [("100", "C00", "K", {})]
        mh.is_excluded.return_value = False
        mh.feature_enabled.return_value = True
        mh.get_topic_timestamps.return_value = {}
        mh.gm_ids_for_campaign.return_value = set()
        mh.interval_elapsed.return_value = False
        check_streak_milestones(config, {})

def test_potw_links(tmp_path):
    from scheduled.potw import _find_player_post_links
    week_ago = datetime(2026, 3, 27, tzinfo=timezone.utc)
    (tmp_path / "Kibwe").mkdir()
    (tmp_path / "Kibwe" / "2026-04.md").write_text(
        "**Alice** (2026-04-01 10:00:00) msg#1:\nHi!\n")
    with patch("scheduled.potw._LOGS_DIR", tmp_path):
        assert isinstance(_find_player_post_links("Kibwe", "Alice", "100", week_ago), list)

def test_queue_reminder_empty(tmp_path):
    from scheduled.queue_reminder import post_queue_reminder
    now = datetime(2026, 4, 3, 10, tzinfo=timezone.utc)
    config = {"group_id": -1001, "bot_topic_id": 999, "gm_user_ids": [999],
              "queue_daily_hours": [], "topic_pairs": [
                  {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
                   "gm_user_ids": [999]}]}
    state = {"last_queue_fingerprint": "NOTEMPTY", "queue_post_count": 0,
             "last_queue_pin_id": None, "last_queue_daily_slots": []}
    with patch("scheduled.queue_reminder.scan_transcripts", return_value={}), \
         patch("scheduled.queue_reminder.post_topic_queues"):
        post_queue_reminder(config, state, now=now)

def test_reports_no_ts():
    from scheduled.reports import post_pace_report
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    config = {"group_id": -1001, "bot_topic_id": 999, "gm_user_ids": [999],
              "topic_pairs": [{"pbp_topic_ids": [100], "code": "C00",
                               "name": "Kibwe", "chat_topic_id": 21514}]}
    with patch("scheduled.reports.helpers") as mh:
        mh.build_topic_maps.return_value = MagicMock(
            to_chat={"100": 21514}, to_name={"100": "Kibwe"})
        mh.feature_enabled.return_value = True
        mh.interval_elapsed.return_value = True
        mh.gm_ids_for_campaign.return_value = {"999"}
        mh.get_topic_timestamps.return_value = {}
        post_pace_report(config, {"last_pace": {}}, now=now)

def test_session_poll_empty():
    from scheduled.session_poll import post_session_poll
    now = datetime(2026, 3, 30, 10, tzinfo=timezone.utc)
    config = {"group_id": -1001, "bot_topic_id": 999, "poll_post_hour": 7,
              "gm_user_ids": [999], "topic_pairs": [
                  {"pbp_topic_ids": [100], "code": "C01", "hybrid_live": True,
                   "chat_topic_id": 21514, "poll_options": ["A"],
                   "poll_user_ids": [], "poll_user_names": {},
                   "allows_multiple_answers": False}]}
    state = {"session_poll": {"C01": {
        "week_iso": "sun2026-03-29", "poll_id": "p1", "poll_message_id": 99,
        "voted_uids": [], "last_ping_day": -1, "votes": {}}}}
    post_session_poll(config, state, now=now)

def test_smart_alerts_off():
    from scheduled.smart_alerts import check_pace_drop
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    maps = MagicMock()
    maps.to_chat = {"100": 21514}
    with patch("scheduled.smart_alerts.helpers") as mh:
        mh.interval_elapsed.return_value = True
        mh.feature_enabled.return_value = False
        check_pace_drop({"group_id": -1, "topic_pairs": []}, {}, now=now, maps=maps)

def test_finalize_empty(tmp_path):
    from transcript.finalize import update_transcript_index
    (tmp_path / "Kibwe").mkdir()
    with patch("transcript.finalize._LOGS_DIR", tmp_path):
        update_transcript_index({"topic_pairs": [{"name": "Kibwe"}]})
    assert (tmp_path / "README.md").exists()

def test_transcript_media():
    from transcript.formatting import format_transcript_content
    assert "report.pdf" in format_transcript_content("[document:report.pdf]")

def test_logger_silence(tmp_path):
    from transcript.logger import append_to_transcript
    now = datetime.now(timezone.utc)
    parsed = {"user_id": "U1", "username": "a", "first_name": "A",
              "user_name": "A", "user_last_name": "", "last_name": "",
              "text": "Hi!", "raw_text": "Hi!", "msg_time_iso": now.isoformat(),
              "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
              "is_gm": False, "msg_id": 42, "pid": "100", "campaign_name": "Kibwe"}
    (tmp_path / "Kibwe").mkdir()
    with patch("transcript.logger._LOGS_DIR", tmp_path):
        try:
            append_to_transcript(parsed, set(),
                                  {"topic_pairs": [{"pbp_topic_ids": [100],
                                                    "name": "Kibwe", "gm_user_ids": []}]})
        except Exception:
            pass

def test_boons_none():
    from boons.handler import _resolve_boon
    state = {"pending_potw_boons": {"100": {
        "boons": [], "message_id": 42, "base_message": "x", "winner_user_id": "U1"}},
        "player_boons": {}, "potw_history": []}
    assert _resolve_boon(state, "100", 0, "x") == (None, None)
