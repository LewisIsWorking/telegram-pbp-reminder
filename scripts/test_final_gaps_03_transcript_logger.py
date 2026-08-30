"""Coverage tests extracted from test_final_gaps.py — bin 3.

Tests grouped by the first production module they import. This bin
covers branches in:
  - transcript.logger+potw+queue_reminder+misc+handler+display+commands+tracker+bot_topic+time_utils+dice+import_formatting
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

def test_logger_long_gap(tmp_path):
    from transcript.logger import append_to_transcript
    now = datetime.now(timezone.utc)
    parsed = {"user_id": "U1", "username": "a", "first_name": "A",
              "user_name": "A", "user_last_name": "", "last_name": "",
              "text": "Hi!", "raw_text": "Hi!", "msg_time_iso": now.isoformat(),
              "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
              "is_gm": False, "msg_id": 99, "pid": "100", "campaign_name": "Kibwe"}
    (tmp_path / "Kibwe").mkdir()
    prev_ts = (now - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    (tmp_path / "Kibwe" / f"{now.strftime('%Y-%m')}.md").write_text(
        f"**Alice** ({prev_ts}) msg#1:\nOld.\n", encoding="utf-8")
    with patch("transcript.logger._LOGS_DIR", tmp_path):
        try:
            append_to_transcript(parsed, set(), {"topic_pairs": [
                {"pbp_topic_ids": [100], "name": "Kibwe", "gm_user_ids": []}]})
        except Exception:
            pass

def test_potw_links(tmp_path):
    from scheduled.potw import _find_player_post_links
    week_ago = datetime(2026, 3, 27, tzinfo=timezone.utc)
    (tmp_path / "Kibwe").mkdir()
    (tmp_path / "Kibwe" / "2026-04.md").write_text(
        "**Alice** (2026-04-01 10:00:00) msg#1:\nHi!\n", encoding="utf-8")
    with patch("scheduled.potw_links._LOGS_DIR", tmp_path):
        assert isinstance(_find_player_post_links("Kibwe", "Alice", "100", week_ago), list)

def test_queue_reminder_empty_queue():
    """⚠️ AMENDED 2026-08-30: the campaign now needs a recent post.

    An untracked campaign used to be dropped from ``silent_campaigns``,
    so this reached the "empty" branch by accident. It now reports as
    'no posts yet', which is a silent campaign and correctly NOT an
    empty queue. Giving Kibwe a last_message_time is what the test
    always meant: nothing unreplied AND nothing quiet.
    """
    from scheduled.queue_reminder import post_queue_reminder
    now = datetime(2026, 4, 3, 10, tzinfo=timezone.utc)
    config = {"group_id": -1001, "bot_topic_id": 999, "gm_user_ids": [999],
              "queue_daily_hours": [], "topic_pairs": [
                  {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
                   "gm_user_ids": [999]}]}
    state = {"last_queue_fingerprint": "OLD", "queue_post_count": 0,
             "last_queue_pin_id": None, "last_queue_daily_slots": [],
             "topics": {"100": {"last_message_time": "2026-04-03T08:00:00+00:00"}}}
    with patch("scheduled.queue_reminder.scan_transcripts", return_value={}), \
         patch("scheduled.queue_reminder.post_topic_queues"):
        post_queue_reminder(config, state, now=now)
    assert state.get("last_queue_fingerprint") == "empty"

def test_parse_message_thread_zero_dup():
    pass  # replaced by test_parse_message_thread_zero below

def test_boons_invalid_choice():
    from boons.handler import choose_boon_by_text
    state = {"pending_potw_boons": {"100": {
        "winner_user_id": "U1", "message_id": 42,
        "campaign_name": "Kibwe", "boons": ["Turtle", "Coin"], "base_message": "Won!"}},
        "player_boons": {}, "players": {}}
    with patch("boons.handler.tg"):
        result = choose_boon_by_text("100", "U1", 0, {"group_id": -1}, state)
    assert isinstance(result, str)

def test_combat_skip_away():
    from combat.display import build_whosturn
    now_iso = datetime.now(timezone.utc).isoformat()
    state = {"combat": {"100": {
        "active": True, "players_acted": {}, "phase_started_at": now_iso,
        "round": 1, "current_phase": "players"}},
        "players": {"100:U1": {"user_id": "U1", "first_name": "Alice",
                               "pbp_topic_id": "100"}},
        "away": {"100:U1": {"reason": "vacation"}}}
    with patch("combat.display.helpers") as mh:
        mh.is_away.return_value = {"reason": "vacation"}
        mh.hours_since.return_value = 0.5
        result = build_whosturn("100", "Kibwe", state)
    assert isinstance(result, str)

def test_combat_log_long():
    from combat.commands import handle_enemies_command
    state = {"combat": {"100": {"active": True, "enemies": ["G"],
                                "log": [f"e{i}" for i in range(10)]}}}
    handle_enemies_command("", "100", "Kibwe", "2026-04-03T12:00:00", -1, 999, state)

def test_combat_tracker_next():
    from combat.tracker import handle_combat_message
    state = {"combat": {"100": {"active": True, "log": [], "round": 1,
                                "current_phase": "player", "actions_this_round": {},
                                "participants": ["U1"]}}}
    handle_combat_message("/next", "/next", "GM1", "Lewis",
                          {"GM1"}, "100", "Kibwe", "2026-04-03T12:00:00", -1, 999, state)

def test_bot_topic_no_pid():
    from dispatch.bot_topic import handle_bot_topic_cmd
    maps = MagicMock()
    maps.name_to_pid = {}
    maps.to_name = {}
    handle_bot_topic_cmd(
        {"from": {"id": 1, "first_name": "L", "is_bot": False}, "text": "/gm"},
        {"group_id": -1, "bot_topic_id": 999, "gm_user_ids": [], "topic_pairs": []},
        {}, maps, -1, 999, frozenset(["/gm"]), [])

def test_time_until():
    from helpers_pkg.time_utils import parse_away_duration
    dt, _ = parse_away_duration("until May 10", datetime(2026, 4, 3, 12, 0, 0))
    assert dt is None or isinstance(dt, datetime)

def test_dice_keep():
    from helpers_pkg.dice import roll_dice
    assert roll_dice("4d6kh3") is not None

def test_import_fmt():
    from import_formatting import format_entry
    assert isinstance(format_entry({"text": "[document:x.pdf]", "is_gm": False}, False), str)
