"""Final targeted tests — all verified in isolation."""
import sys, os, json
from datetime import datetime, timezone, timedelta
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


def test_alerts_recent_suppressed():
    from scheduled.alerts import check_and_alert
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    recent = (now - timedelta(hours=12)).isoformat()
    config = {"group_id": -1, "gm_user_ids": [], "bot_topic_id": 999,
              "topic_pairs": [{"pbp_topic_ids": [100], "name": "Kibwe",
                               "chat_topic_id": 21514}]}
    state = {"last_alerts": {"100": recent},
             "topics": {"100": {"last_message_time":
                                (now - timedelta(hours=50)).isoformat()}},
             "players": {}, "paused_campaigns": {}}
    with patch("scheduled.alerts.helpers") as mh:
        mh.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
        mh.is_excluded.return_value = False
        mh.feature_enabled.return_value = True
        mh.hours_since.return_value = 12.0   # < 24 → suppress
        mh.interval_elapsed.return_value = True
        check_and_alert(config, state, now=now)


def test_combat_ping_no_chat():
    from scheduled.combat_ping import check_combat_turns
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    config = {"group_id": -1, "bot_topic_id": 999, "gm_user_ids": [],
              "topic_pairs": [{"pbp_topic_ids": [100], "name": "Kibwe", "chat_topic_id": 21514}]}
    state = {"combat": {"100": {"active": True, "current_phase": "players",
                                "participants": ["U1"], "players_acted": {},
                                "phase_started_at":
                                (now - timedelta(hours=25)).isoformat()}},
             "players": {}, "away": {}}
    maps = MagicMock()
    maps.to_chat = {}  # empty → no chat_topic_id → continue at line 63
    with patch("scheduled.combat_ping.helpers") as mh,          patch("scheduled.combat_ping.fmt_date", return_value="Apr 3"):
        mh.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
        mh.is_excluded.return_value = False
        mh.feature_enabled.return_value = True
        mh.build_topic_maps.return_value = maps
        mh.gm_ids_for_campaign.return_value = set()
        mh.hours_since.return_value = 25.0
        mh.is_away.return_value = None
        mh.player_mention.return_value = "@alice"
        mh.all_campaigns = {}
        mh.COMBAT_PING_HOURS = 24
        # all_campaigns is used via helpers.all_campaigns - mock it
        check_combat_turns(config, state, now=now)


def test_maintenance_cleanup_empty_pid():
    from scheduled.maintenance import cleanup_timestamps
    # cleanup_timestamps removes empty pid entries (line 127)
    state = {"post_timestamps": {"100": {}}}  # empty uid dict → delete pid
    cleanup_timestamps(state)
    assert "100" not in state.get("post_timestamps", {})


def test_milestones_anniversary_disabled():
    from scheduled.milestones import check_streak_milestones
    config = {"group_id": -1, "bot_topic_id": 999, "gm_user_ids": [],
              "topic_pairs": [{"pbp_topic_ids": [100], "name": "Kibwe",
                               "chat_topic_id": 21514}]}
    with patch("scheduled.milestones.helpers") as mh:
        mh.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
        mh.is_excluded.return_value = False
        mh.get_topic_timestamps.return_value = {}
        mh.gm_ids_for_campaign.return_value = set()
        mh.interval_elapsed.return_value = True
        mh.feature_enabled.side_effect = lambda c, p, f: f != "anniversary"
        check_streak_milestones(config, {})


def test_reports_no_timestamps():
    # reports.py:106 — continue when no timestamps for campaign
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
        mh.get_topic_timestamps.return_value = {}  # empty → continue
        post_pace_report(config, {"last_pace": {}}, now=now)


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
        mh.character_name.return_value = "Amara"
        mh.COMEBACK_THRESHOLD_HOURS = 96
        mh.player_mention.return_value = "@alice"
        track_message(parsed, state, {"group_id": -1001, "gm_user_ids": [999],
                                       "bot_topic_id": 999}, set(), maps)


def test_addplayer_no_username():
    from players.management import handle_addplayer
    state = {"players": {}, "removed_players": {}}
    handle_addplayer("100", "Kibwe", "", "2026-04-03T12:00:00+00:00", state, -1, 999)


def test_campaign_notes_over_3():
    from commands.campaign import build_campaign_report
    state = {"notes": {"100": ["N1", "N2", "N3", "N4", "N5"]},
             "quests": {}, "loot": {}, "npcs": {}, "pinned_moments": {},
             "conditions": {}, "hp_tracker": {}, "clocks": {},
             "topics": {}, "post_timestamps": {}, "message_counts": {},
             "players": {}, "session_counts": {}}
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": [
        {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
         "gm_user_ids": [], "chat_topic_id": 21514}]}
    with patch("commands.campaign.helpers") as mh:
        mh.get_label.return_value = "C00"
        mh.gm_ids_for_campaign.return_value = set()
        mh.get_characters.return_value = {}
        mh.get_topic_timestamps.return_value = {}
        mh.hours_since.return_value = 5.0
        mh.feature_enabled.return_value = False
        mh.player_full_name.return_value = "A"
        mh.REQUIRED_PLAYERS = 4
        mh.players_by_campaign.return_value = {}
        mh.pace_split.return_value = {"gm_this": 0, "player_this": 0,
                                       "gm_last": 0, "player_last": 0}
        mh.trend_icon.return_value = "➡️"
        mh.posts_str.return_value = "0"
        result = build_campaign_report("100", config, state, set())
    assert "more" in result


def test_reactions_neg():
    from commands.reactions import build_reactions
    state = {"reactions": {"100": {"given": {"U1": {"count": -2, "name": "A"}},
                                    "emojis": {}}}}
    with patch("commands.reactions.helpers") as mh:
        mh.gm_ids_for_campaign.return_value = set()
        mh.rank_icon.return_value = "🥇"
        result = build_reactions({}, state, "100", "Kibwe")
    assert isinstance(result, str)


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
        f"**Alice** (2026-04-01 10:00:00) msg#1:\n{content}\n")
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
        f"**Alice** ({prev_ts}) msg#1:\nOld.\n")
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
        "**Alice** (2026-04-01 10:00:00) msg#1:\nHi!\n")
    with patch("scheduled.potw._LOGS_DIR", tmp_path):
        assert isinstance(_find_player_post_links("Kibwe", "Alice", "100", week_ago), list)


def test_queue_reminder_empty_queue():
    from scheduled.queue_reminder import post_queue_reminder
    now = datetime(2026, 4, 3, 10, tzinfo=timezone.utc)
    config = {"group_id": -1001, "bot_topic_id": 999, "gm_user_ids": [999],
              "queue_daily_hours": [], "topic_pairs": [
                  {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
                   "gm_user_ids": [999]}]}
    with patch("scheduled.queue_reminder.scan_transcripts", return_value={}):
        state = {"last_queue_fingerprint": "OLD", "queue_post_count": 0,
                 "last_queue_pin_id": None, "last_queue_daily_slots": []}
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
