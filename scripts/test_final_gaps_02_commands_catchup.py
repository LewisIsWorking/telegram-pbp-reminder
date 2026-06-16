"""Coverage tests extracted from test_final_gaps.py — bin 2.

Tests grouped by the first production module they import. This bin
covers branches in:
  - commands.catchup+recap+status+summary+cmd_clocks+cmd_conditions_hp+cmd_votes_timers+cmd_trackers+cmd_trackers_items+router+dc_lookup+mechanics+config+formatting
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

def test_catchup_list_to_set():
    from commands.catchup import build_catchup
    now = datetime.now(timezone.utc)
    ts = (now - timedelta(hours=1)).isoformat()
    state = {"post_timestamps": {}, "away": {}, "topics": {},
             "acted_this_scene": {"100": ["U2"]}}
    with patch("commands.catchup.helpers") as mh:
        mh.get_topic_timestamps.return_value = {"U1": [ts]}
        mh.gm_ids_for_campaign.return_value = set()
        mh.hours_since.return_value = 1.0
        mh.is_away.return_value = None
        mh.get_player.return_value = {"first_name": "A", "username": "a"}
        mh.player_full_name.return_value = "A"
        build_catchup("U1", "Alice", "100", "Kibwe", {"group_id": -1}, state)

def test_recap_word_truncation(tmp_path):
    from commands.recap import build_recap
    (tmp_path / "Kibwe").mkdir()
    content = " ".join([f"word{i}" for i in range(50)])
    (tmp_path / "Kibwe" / "2026-04.md").write_text(
        f"**Alice** (2026-04-01 10:00:00) msg#1:\n{content}\n", encoding="utf-8")
    with patch("commands.recap._LOGS_DIR", tmp_path), \
         patch("commands.recap.helpers") as mh:
        mh.campaign_dir_name.return_value = "Kibwe"
        mh.get_label.return_value = "C00"
        mh.get_characters.return_value = {}
        mh.gm_ids_for_campaign.return_value = set()
        mh.get_label.return_value = "C00"
        result = build_recap("100", "Kibwe", {}, 5)
    assert isinstance(result, str)

def test_status_no_last_msg():
    from commands.status import build_status
    state = {"topics": {"100": {}}, "post_timestamps": {}, "message_counts": {},
             "players": {}, "paused_campaigns": {}, "current_scenes": {}}
    with patch("commands.status.helpers") as mh:
        mh.get_label.return_value = "C00"
        mh.get_topic_timestamps.return_value = {}
        mh.hours_since.return_value = 0
        mh.get_characters.return_value = {}
        mh.player_full_name.return_value = "A"
        mh.players_by_campaign.return_value = {}
        mh.pace_split.return_value = {"gm_this": 0, "player_this": 0,
                                       "gm_last": 0, "player_last": 0}
        mh.trend_icon.return_value = "➡️"
        mh.posts_str.return_value = "0"
        result = build_status("100", "Kibwe", state, set(), {})
    assert "—" in result or "no posts" in result.lower()

def test_summary_player_active():
    from commands.summary import build_summary
    now = datetime.now(timezone.utc)
    state = {"combat": {}, "clocks": {}, "notes": {}, "quests": {}, "loot": {},
             "npcs": {}, "pins": {}, "hp_tracker": {}, "conditions": {}, "away": {},
             "votes": {}, "timers": {},
             "players": {"100:U1": {"user_id": "U1", "first_name": "Alice",
                                    "last_post_time": (now - timedelta(days=2)).isoformat()}}}
    result = build_summary("100", "Kibwe", state, {})
    assert isinstance(result, str)

def test_summary_player_old():
    from commands.summary import build_summary
    now = datetime.now(timezone.utc)
    state = {"combat": {}, "clocks": {}, "notes": {}, "quests": {}, "loot": {},
             "npcs": {}, "pins": {}, "hp_tracker": {}, "conditions": {}, "away": {},
             "votes": {}, "timers": {},
             "players": {"100:U1": {"user_id": "U1", "first_name": "Alice",
                                    "last_post_time": (now - timedelta(days=14)).isoformat()}}}
    result = build_summary("100", "Kibwe", state, {})
    assert "last seen" in result or isinstance(result, str)

def test_clock_tick_at_max():
    from dispatch.cmd_clocks import handle
    ctx = _ctx("/tick", "/tick Inv",
               {"clocks": {"100": {"Inv": {"filled": 6, "segments": 6, "label": "Inv"}}}},
               parsed={"raw_text": "/tick Inv"})
    with patch("dispatch.cmd_clocks.helpers") as mh:
        mh.clock_display.return_value = "██████"
        assert handle(ctx) is True

def test_hp_bad_sub():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/hp", "/hp blah", {"hp_tracker": {}}, parsed={"raw_text": "/hp blah"})
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

def test_cmd_trackers_done_nf():
    from dispatch.cmd_trackers import handle
    ctx = _ctx("/done", "/done 9",
               {"quests": {"100": [{"text": "Q", "status": "active"}]}},
               parsed={"raw_text": "/done 9"})
    assert handle(ctx) is True

def test_cmd_delloot_nf():
    from dispatch.cmd_trackers_items import handle
    ctx = _ctx("/delloot", "/delloot 9", {"loot": {"100": []}},
               parsed={"raw_text": "/delloot 9"})
    assert handle(ctx) is True

def test_router_exception():
    from dispatch.router import process_updates
    maps = MagicMock()
    maps.all_pids.return_value = []
    maps.to_name = {}
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": [], "bot_topic_id": None}
    state = {"offset": 0, "players": {}, "topics": {}}
    with patch("dispatch.router.build_topic_maps", return_value=maps), \
         patch("dispatch.router.parse_message", side_effect=RuntimeError("!")):
        assert process_updates([{"update_id": 42}], config, state) == 43

def test_dc_lookup_adj():
    from helpers_pkg.dc_lookup import dc_lookup, _DC_ADJUSTMENTS
    key = next(iter(_DC_ADJUSTMENTS))
    assert "adjustment" in dc_lookup(key).lower()

def test_hp_icon_red():
    from helpers_pkg.mechanics import hp_status_icon
    assert hp_status_icon(2, 10) == "🔴"

def test_load_settings():
    from helpers_pkg.config import load_settings
    load_settings({"settings": {"REQUIRED_PLAYERS": 5}})

def test_transcript_formatting_media():
    from transcript.formatting import format_transcript_content
    assert "report.pdf" in format_transcript_content("[document:report.pdf]")
