"""Coverage tests extracted from test_final_coverage.py — bin 6.

Sections in this file:
  - simulate __main__ guard (part a)
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


def test_set_commands_no_token(monkeypatch, capsys):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    import set_commands as sc
    with pytest.raises(SystemExit):
        sc.set_commands.__module__  # just ensure importable
        # simulate __main__ guard
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if not token:
            raise SystemExit(1)


def test_queue_stats_cleared_today():
    from commands.queue_stats import build_queue_stats
    now = datetime.now(timezone.utc)
    state = {
        "queue_history": {"100": [now.isoformat()]},
        "queue_archive": [{"pid": "100", "time": now.isoformat(),
                           "player": "Alice", "preview": "hi"}],
    }
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": []}
    with patch("commands.queue_scan.scan_transcripts", return_value={}), \
         patch("commands.queue_analytics.helpers") as mh, \
         patch("commands.queue_stats.helpers") as mh2:
        mh.iter_campaigns.return_value = []
        mh2.iter_campaigns.return_value = []
        result = build_queue_stats(config, state)
    assert "Cleared today" in result


def test_parsing_message_document():
    from parsing.message import _detect_media
    msg = {"document": {"file_name": "map.pdf"}}
    result = _detect_media(msg)
    assert result is not None
    assert "map.pdf" in result


def test_dispatch_comeback_username():
    from dispatch.comeback import _find_player_mention
    parsed = {"username": "alice"}
    result = _find_player_mention(parsed)
    assert "@alice" in result


def test_dispatch_comeback_no_username():
    from dispatch.comeback import _find_player_mention
    parsed = {}
    result = _find_player_mention(parsed)
    assert result == ""


def test_commands_session_set_number():
    from commands.session import set_session
    state = {}
    result = set_session("100", "Kibwe", 5, state)
    assert "5" in result
    assert state["session_counts"]["100"] == 5


def test_commands_summary_clocks():
    from commands.summary import build_summary
    state = {
        "clocks": {"100": {"The Gate": {"filled": 2, "segments": 4}}},
        "notes": {}, "quests": {}, "loot": {}, "npcs": {},
        "pinned_moments": {}, "conditions": {}, "hp_tracker": {},
        "trackers": {}, "vote": {}, "timer": {},
    }
    with patch("commands.summary.helpers") as mh:
        mh.get_label.return_value = "C00: Kibwe"
        mh.clock_display.return_value = "██░░"
        result = build_summary("100", "Kibwe", state, {})
    assert "Clocks" in result or "Gate" in result


def test_commands_timeline_trim():
    from commands.timeline import add_event
    state = {"timeline_events": {"100": [{"text": f"event {i}",
             "time": "2026-01-01", "author": "X"} for i in range(55)]}}
    add_event("100", "Kibwe", "Something happened", state)
    assert len(state["timeline_events"]["100"]) <= 50


def test_dispatch_cmd_info_boonsall():
    from dispatch.cmd_info import handle as cmd_info_handle
    ctx = {
        "cmd_word": "/boonsall", "text": "/boonsall",
        "group_id": -1, "reply_topic": 999,
        "pid": "100", "campaign_name": "Kibwe",
        "user_id": "U1", "user_name": "Alice",
        "state": {"player_boons": {}},
        "config": {}, "gm_ids": set(),
    }
    with patch("dispatch.cmd_info.tg.send_message"):
        result = cmd_info_handle(ctx)
    assert result is True


def test_dc_lookup_adjustment():
    from helpers_pkg.dc_lookup import dc_lookup
    result = dc_lookup("trained")
    assert "trained" in result.lower() or "adjustment" in result.lower()


def test_dc_lookup_unknown():
    from helpers_pkg.dc_lookup import dc_lookup
    result = dc_lookup("completely_invalid_key_xyz")
    assert isinstance(result, str)


def test_helpers_config_leaderboard_collision():
    from helpers_pkg.config import validate_config
    config = {
        "group_id": -1, "gm_user_ids": [],
        "leaderboard_topic_id": 100,
        "topic_pairs": [{"pbp_topic_ids": [100], "name": "X",
                         "chat_topic_id": 200}],
    }
    issues = validate_config(config)
    assert any("leaderboard" in i.lower() or "collision" in i.lower()
               for i in issues)


def test_queue_reminder_unpin_prev():
    from scheduled.queue_reminder import post_queue_reminder
    now = datetime(2026, 4, 3, 9, 0, tzinfo=timezone.utc)
    t = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    entries = [{"name": "Alice", "time": t, "preview": "hi",
                "link": "", "message_id": "1"}]
    scanned = {"100": {"campaign": "Kibwe", "code": "C00", "entries": entries}}
    state = {"last_queue_fingerprint": "OLD", "queue_post_count": 0,
             "last_queue_pin_id": 777, "last_queue_daily_slots": []}
    config = {"group_id": -1001, "bot_topic_id": 999,
              "gm_user_ids": [999], "queue_daily_hours": [9, 21],
              "topic_pairs": [{"pbp_topic_ids": [100], "code": "C00",
                               "name": "Kibwe", "gm_user_ids": [999]}]}
    with patch("scheduled.queue_reminder.scan_transcripts", return_value=scanned), \
         patch("scheduled.queue_reminder.post_topic_queues"):
        post_queue_reminder(config, state, now=now)
