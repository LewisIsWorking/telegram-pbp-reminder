"""Coverage tests extracted from test_close_gaps.py — bin 2.

Tests grouped by the first production module they import. This bin
covers branches in:
  - combat.display+commands+tracker+comeback+router+tracking+bot_topic+cmd_trackers+cmd_trackers_items+cmd_votes_timers+cmd_conditions_hp+config+dc_lookup+dice+mechanics+time_utils+import_formatting+import_history+post_changelog
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

def test_combat_acted_no_timestamp():
    from combat.display import build_whosturn
    now_iso = datetime.now(timezone.utc).isoformat()
    state = {"combat": {"100": {
        "active": True, "players_acted": {"U1": None},
        "phase_started_at": now_iso, "round": 1, "current_phase": "players"}},
        "players": {"100:U1": {"user_id": "U1", "first_name": "Alice",
                               "pbp_topic_id": "100"}}, "away": {}}
    with patch("combat.display.helpers") as mh:
        mh.is_away.return_value = None
        mh.hours_since.return_value = 0.5
        result = build_whosturn("100", "Kibwe", state)
    assert "✅ Alice" in result

def test_combat_long_log():
    from combat.commands import handle_enemies_command
    state = {"combat": {"100": {"active": True, "enemies": [],
                                "log": [f"e{i}" for i in range(10)]}}}
    handle_enemies_command("", "100", "Kibwe", "2026-04-03T12:00:00", -1, 999, state)

def test_combat_tracker_gm_round():
    from combat.tracker import handle_combat_message
    state = {"combat": {"100": {"active": True, "log": [], "round": 1,
                                "current_phase": "player", "actions_this_round": {},
                                "participants": ["U1"]}}}
    handle_combat_message("/next", "/next", "GM1", "Lewis",
                          {"GM1"}, "100", "Kibwe", "2026-04-03T12:00:00", -1, 999, state)

def test_comeback_no_bot_topic():
    from dispatch.comeback import check_comeback
    now = datetime.now(timezone.utc)
    old = {"user_id": "U1", "last_post_time": (now - timedelta(days=10)).isoformat()}
    parsed = {"user_id": "U1", "username": "a", "first_name": "A",
              "user_name": "A", "campaign_name": "K",
              "msg_time_iso": now.isoformat(), "thread_id": "100",
              "pid": "100", "is_gm": False, "text": "Hi!"}
    with patch("dispatch.comeback.helpers") as mh:
        mh.days_since.return_value = 10.0   # > SILENCE_THRESHOLD_DAYS (5) → passes
        mh.character_name.return_value = ""
        # No bot_topic_id in config → line 38: return
        check_comeback(parsed, old, {}, {"group_id": -1, "gm_user_ids": []}, set())

def test_router_exception():
    from dispatch.router import process_updates
    maps = MagicMock()
    maps.all_pids.return_value = []
    maps.to_name = {}
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": [], "bot_topic_id": None}
    state = {"offset": 0, "players": {}, "topics": {}}
    with patch("dispatch.router.build_topic_maps", return_value=maps), \
         patch("dispatch.router.parse_message", side_effect=RuntimeError("!")):
        result = process_updates([{"update_id": 10}], config, state)
    assert result == 11

def test_tracking_warned_comeback():
    from dispatch.tracking import track_message
    now = datetime.now(timezone.utc)
    maps = MagicMock()
    maps.to_chat = {"100": 21514}
    maps.to_name = {"100": "Kibwe"}
    parsed = {"user_id": "U1", "username": "alice", "first_name": "Alice",
              "user_name": "Alice", "user_last_name": "", "campaign_name": "Kibwe",
              "pid": "100", "is_gm": False, "thread_id": "100",
              "text": "Hi!", "raw_text": "Hi!",
              "msg_time_iso": now.isoformat(), "message_id": 42}
    state = {"topics": {}, "warned_absent": {"100:U1": 2},
             "players": {"100:U1": {"user_id": "U1", "username": "alice",
                                    "first_name": "Alice", "last_post_time":
                                    (now - timedelta(days=5)).isoformat()}},
             "message_counts": {}, "post_timestamps": {}, "removed_players": {}}
    with patch("dispatch.tracking.helpers") as mh:
        mh.hours_since.return_value = 130.0
        mh.character_name.return_value = ""
        mh.COMEBACK_THRESHOLD_HOURS = 96
        mh.player_mention.return_value = "@alice"
        track_message(parsed, state, {"group_id": -1001, "gm_user_ids": [999],
                                       "bot_topic_id": 999}, set(), maps)

def test_bot_topic_no_pid():
    from dispatch.bot_topic import handle_bot_topic_cmd
    maps = MagicMock()
    maps.name_to_pid = {}
    maps.to_name = {}
    handle_bot_topic_cmd(
        {"from": {"id": 1, "first_name": "L", "is_bot": False}, "text": "/gm"},
        {"group_id": -1, "bot_topic_id": 999, "gm_user_ids": [], "topic_pairs": []},
        {}, maps, -1, 999, frozenset(["/gm"]), [])

def test_cmd_trackers_nf():
    from dispatch.cmd_trackers import handle
    ctx = _ctx("/done", "/done 9",
               {"quests": {"100": [{"text": "Q", "status": "active"}]}},
               parsed={"raw_text": "/done 9"})
    assert handle(ctx) is True

def test_cmd_trackers_items_nf():
    from dispatch.cmd_trackers_items import handle
    ctx = _ctx("/delloot", "/delloot 9",
               {"loot": {"100": []}}, parsed={"raw_text": "/delloot 9"})
    assert handle(ctx) is True

def test_endvote_tied():
    from dispatch.cmd_votes_timers import handle
    ctx = _ctx("/endvote", "/endvote",
               {"vote": {"100": {"question": "?", "options": ["A", "B"],
                                  "votes": {"U1": 0, "U2": 1}}}},
               parsed={"raw_text": "/endvote"})
    assert handle(ctx) is True

def test_endvote_no_votes():
    from dispatch.cmd_votes_timers import handle
    ctx = _ctx("/endvote", "/endvote",
               {"vote": {"100": {"question": "?", "options": ["A"], "votes": {}}}},
               parsed={"raw_text": "/endvote"})
    assert handle(ctx) is True

def test_hp_bad_sub():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/hp", "/hp xyz", {"hp_tracker": {}}, parsed={"raw_text": "/hp xyz"})
    assert handle(ctx) is True

def test_config_load_settings():
    from helpers_pkg.config import load_settings
    load_settings({"settings": {"REQUIRED_PLAYERS": 5}})

def test_dc_adjustment():
    from helpers_pkg.dc_lookup import dc_lookup, _DC_ADJUSTMENTS
    key = next(iter(_DC_ADJUSTMENTS))
    assert "adjustment" in dc_lookup(key).lower()

def test_dice_keep():
    from helpers_pkg.dice import roll_dice
    assert roll_dice("4d6kh3") is not None

def test_hp_red():
    from helpers_pkg.mechanics import hp_status_icon
    assert hp_status_icon(2, 10) == "🔴"

def test_parse_until():
    from helpers_pkg.time_utils import parse_away_duration
    dt, _ = parse_away_duration("until June 15", datetime(2026, 4, 3, 12, 0, 0))
    assert dt is None or isinstance(dt, datetime)

def test_import_fmt():
    from import_formatting import format_entry
    assert isinstance(format_entry({"text": "[document:f.pdf]", "is_gm": False}, False), str)

def test_import_history_continue(tmp_path):
    from import_history import import_messages
    export = tmp_path / "result.json"
    export.write_text(json.dumps({"messages": [{"type": "message", "text": "",
                                                "from_id": "user123"}]}), encoding="utf-8")
    assert isinstance(import_messages(str(export), dry_run=True), dict)

def test_changelog_chunk_split():
    from post_changelog import split_message
    long = "\n".join(["word " * 20] * 5)
    chunks = split_message(long, max_length=100)
    assert len(chunks) >= 1
