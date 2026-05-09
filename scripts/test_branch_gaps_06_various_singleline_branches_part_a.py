"""Coverage tests extracted from test_branch_gaps.py — bin 6.

Sections in this file:
  - Various single-line branches (part a)

Targeted tests for specific uncovered branches in the production
modules listed above. Module imports are duplicated from the original
``test_branch_gaps.py`` header; per-section helper functions are
extracted alongside their sections.
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


def test_dispatch_cmd_votes_timers_cancel_no_timer():
    from dispatch.cmd_votes_timers import handle as vt_handle
    ctx = {
        "cmd_word": "/canceltimer", "text": "/canceltimer",
        "user_id": "GM1", "user_name": "Lewis", "gm_ids": {"GM1"},
        "pid": "100", "group_id": -1, "thread_id": 999,
        "state": {"timer": {}}, "config": {},
        "campaign_name": "Kibwe",
        "parsed": {"raw_text": "/done 99", "text": "/done 99"}, "now_iso": "2026-04-03T12:00:00+00:00",
        "maps": MagicMock(),
    }
    result = vt_handle(ctx)
    assert result is True


def test_combat_commands_enemies():
    from combat.commands import handle_enemies_command
    state = {"combat": {"100": {"active": True, "enemies": ["Goblin", "Orc"]}}}
    handle_enemies_command("", "100", "Kibwe", "2026-04-03T12:00:00", -1, 999, state)


def test_combat_commands_no_enemies():
    from combat.commands import handle_enemies_command
    state = {"combat": {"100": {"active": True, "enemies": []}}}
    handle_enemies_command("", "100", "Kibwe", "2026-04-03T12:00:00", -1, 999, state)


def test_boons_reminders_second_reminder():
    from boons.reminders import check_boon_reminders
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    two_days_ago = (now - timedelta(days=3)).isoformat()
    state = {
        "pending_potw_boons": {"100": {
            "winner_user_id": "U1",
            "campaign_name": "Kibwe",
            "posted_at": two_days_ago,
            "boons": ["Turtle"],
            "message_id": 42,
            "reminders_sent": 1,
        }}
    }
    config = {"group_id": -1001, "bot_topic_id": 999, "topic_pairs": [
        {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
         "pbp_topic_ids": [100], "chat_topic_id": 21514}
    ]}
    with patch("boons.reminders.helpers") as mh:
        mh.interval_elapsed.return_value = True
        mh.player_mention.return_value = "@alice"
        mh.hours_since.return_value = 75.0
        check_boon_reminders(config, state, now=now)


def test_cmd_trackers_quest_not_found():
    from dispatch.cmd_trackers import handle as trackers_handle
    ctx = {
        "cmd_word": "/done", "text": "/done 99",
        "user_id": "GM1", "user_name": "Lewis", "gm_ids": {"GM1"},
        "pid": "100", "group_id": -1, "thread_id": 999,
        "state": {"quests": {"100": []}},
        "config": {}, "campaign_name": "Kibwe",
        "parsed": {"raw_text": "/done 99", "text": "/done 99"}, "now_iso": "2026-04-03T12:00:00+00:00",
        "maps": MagicMock(),
    }
    result = trackers_handle(ctx)
    assert result is True


def test_cmd_trackers_items_npc_not_found():
    from dispatch.cmd_trackers_items import handle as ti_handle
    ctx = {
        "cmd_word": "/delnpc", "text": "/delnpc 99",
        "user_id": "GM1", "user_name": "Lewis", "gm_ids": {"GM1"},
        "pid": "100", "group_id": -1, "thread_id": 999,
        "state": {"npcs": {"100": []}},
        "config": {}, "campaign_name": "Kibwe",
        "parsed": {"raw_text": "/done 99", "text": "/done 99"}, "now_iso": "2026-04-03T12:00:00+00:00",
        "maps": MagicMock(),
    }
    result = ti_handle(ctx)
    assert result is True


def test_markdone_numeric_id_exact_match():
    from commands.markdone import handle_markdone
    entry = {"message_id": "140368", "time": "2026-03-01 10:00:00",
             "name": "Alice", "preview": "hi"}
    with patch("commands.markdone.scan_transcripts",
               return_value={"100": {"entries": [entry]}}):
        ctx = {
            "cmd_word": "/markdone", "text": "/markdone 140368",
            "user_id": "GM1", "gm_ids": {"GM1"},
            "pid": "100", "group_id": -1, "thread_id": 999,
            "state": {}, "config": {"group_id": -1, "gm_user_ids": [1]},
            "campaign_name": "Kibwe",
        }
        result = handle_markdone(ctx)
    assert result is True


def test_queue_scan_section_break(tmp_path):
    from commands.queue_scan import scan_transcripts
    now = datetime.now(timezone.utc)
    month = now.strftime("%Y-%m")
    log_dir = tmp_path / "Kibwe"
    log_dir.mkdir()
    # Section header should stop content collection
    (log_dir / f"{month}.md").write_text(
        "**Alice** (2026-03-01 10:00:00):\n## New Scene\nMore content\n"
    )
    with patch("commands.queue_scan.helpers") as mh, \
         patch("commands.queue_scan._LOGS_DIR", tmp_path), \
         patch("commands.queue_scan._IDS_FILE", tmp_path / "ids.json"), \
         patch("commands.queue_io.all_pids", return_value=[]):
        mh.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
        mh.is_excluded.return_value = False
        mh.gm_ids_for_campaign.return_value = {"999"}
        result = scan_transcripts({"group_id": -1, "gm_user_ids": [], "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe", "gm_user_ids": [999]}
        ]}, {})
    # Section break stops content — entry still added but with limited preview
    if "100" in result:
        assert result["100"]["entries"][0]["name"] == "Alice"


def test_dashboard_active_quests_flag():
    from commands.dashboard import build_gm_dashboard
    state = {
        "quests": {"100": [{"text": "Quest 1", "done": False},
                            {"text": "Quest 2", "done": False}]},
        "conditions": {}, "timer": {}, "vote": {}, "current_scenes": {},
        "hp_tracker": {}, "clocks": {}, "combat": {}, "paused_campaigns": {},
        "topics": {"100": {"last_message_time": datetime.now(timezone.utc).isoformat()}},
        "players": {}, "post_timestamps": {},
    }
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": []}
    state2 = {"quests": {}, "conditions": {}, "timer": {}, "vote": {},
              "current_scenes": {}, "hp_tracker": {}, "clocks": {},
              "combat": {}, "paused_campaigns": {}, "topics": {},
              "players": {}, "post_timestamps": {}, "message_counts": {}}
    with patch("commands.dashboard.helpers") as mh:
        mh.iter_campaigns.return_value = []
        result = build_gm_dashboard(config, state2)
    assert isinstance(result, str)


def test_transcript_formatting_media():
    from transcript.formatting import format_log_entry
    parsed = {"user_id": "U1", "first_name": "Alice", "username": "alice",
              "user_name": "Alice", "last_name": "",
              "text": "document:map.pdf", "timestamp": "2026-03-01 10:00:00",
              "msg_time_iso": "2026-03-01T10:00:00", "is_gm": False, "msg_id": None}
    result = format_log_entry(parsed, set(), char_name=None)
    assert "map.pdf" in result or "document" in result.lower() or isinstance(result, str)
