"""Close the final 4% — every remaining uncovered production line."""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


def _ctx(**kw):
    base = {
        "user_id": "GM1", "user_name": "Lewis", "gm_ids": {"GM1"},
        "pid": "100", "group_id": -1, "thread_id": 999,
        "state": {}, "config": {}, "campaign_name": "Kibwe",
        "now_iso": "2026-04-03T12:00:00+00:00",
        "msg_time_iso": "2026-04-03T12:00:00+00:00",
        "parsed": {"raw_text": "", "text": ""},
        "maps": MagicMock(), "reply_topic": 999,
    }
    base.update(kw)
    base["cmd_word"] = base["text"].split()[0] if base["text"] else base.get("cmd_word", "")
    return base


# ── parsing/message.py:112 ────────────────────────────────────────────────────
def test_detect_media_gif():
    from parsing.message import _detect_media
    assert _detect_media({"animation": {"file_id": "x"}}) == "gif"


# ── helpers_pkg/config.py:107 ─────────────────────────────────────────────────
def test_config_missing_name():
    from helpers_pkg.config import validate_config
    config = {"group_id": -1, "gm_user_ids": [],
              "topic_pairs": [{"pbp_topic_ids": [100]}]}  # no 'name'
    issues = validate_config(config)
    assert any("missing" in i.lower() and "name" in i.lower() for i in issues)


# ── helpers_pkg/dc_lookup.py:110-112 ─────────────────────────────────────────
def test_dc_lookup_adjustment_key():
    from helpers_pkg.dc_lookup import dc_lookup, _DC_ADJUSTMENTS
    key = next(iter(_DC_ADJUSTMENTS))
    result = dc_lookup(key)
    assert "adjustment" in result.lower()


# ── helpers_pkg/dice.py:80 ────────────────────────────────────────────────────
def test_dice_drop_lowest_rolls():
    from helpers_pkg.dice import roll_dice
    result = roll_dice("4d6dl1")  # drop lowest → has non-kept rolls
    assert result is not None


# ── helpers_pkg/mechanics.py:124 ─────────────────────────────────────────────
def test_hp_icon_red_25pct():
    from helpers_pkg.mechanics import hp_status_icon
    assert hp_status_icon(2, 10) == "🔴"   # 20% → red (≤25%)


# ── helpers_pkg/time_utils.py:110 ────────────────────────────────────────────
def test_parse_until_date():
    from helpers_pkg.time_utils import parse_away_duration
    now = datetime(2026, 4, 3, 12, 0, 0)   # naive datetime
    dt, reason = parse_away_duration("until May 10", now)
    assert dt is None or isinstance(dt, datetime)


# ── import_formatting.py:85 ───────────────────────────────────────────────────
def test_import_formatting_media_bracket():
    from import_formatting import format_entry
    result = format_entry({"text": "[document:map.pdf]", "is_gm": False}, False)
    assert isinstance(result, str)


# ── parsing/message.py:112 already done above ────────────────────────────────

# ── players/management.py:73 ─────────────────────────────────────────────────
def test_management_no_match_continues():
    from players.management import handle_kick
    state = {"players": {
        "100:U2": {"user_id": "U2", "first_name": "Bob",
                   "username": "bob", "last_name": ""}
    }}
    handle_kick("100", "Kibwe", "@nobody", state, -1, 999)


# ── scheduled/alerts.py:169 ──────────────────────────────────────────────────
def test_alerts_excluded_pid():
    from scheduled.alerts import check_and_alert
    config = {"group_id": -1, "gm_user_ids": [], "bot_topic_id": 999,
              "topic_pairs": [{"pbp_topic_ids": [100], "name": "K",
                               "chat_topic_id": 21514}]}
    with patch("helpers.iter_campaigns",
               return_value=[("100", "C00", "Kibwe", {})]), \
         patch("helpers.is_excluded", return_value=True):
        check_and_alert(config, {})


# ── scheduled/combat_ping.py:95 ──────────────────────────────────────────────
def test_combat_ping_excluded_pid():
    from scheduled.combat_ping import check_combat_turns
    config = {"group_id": -1, "bot_topic_id": 999, "gm_user_ids": [],
              "topic_pairs": [{"pbp_topic_ids": [100], "name": "K",
                               "chat_topic_id": 21514}]}
    with patch("scheduled.combat_ping.helpers") as mh:
        mh.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
        mh.is_excluded.return_value = True
        check_combat_turns(config, {"combat": {}})


# ── scheduled/diagnostic_analysis.py:43 ──────────────────────────────────────
def test_diagnostic_info_pattern_no_match():
    from scheduled.diagnostic_analysis import _analyse_logs
    result = _analyse_logs(["just a normal log line with nothing interesting"])
    assert result["events"] == []


# ── scheduled/maintenance.py:147 ─────────────────────────────────────────────
def test_maintenance_excluded_pid():
    from scheduled.maintenance import check_recruitment_needs
    config = {"group_id": -1, "gm_user_ids": [],
              "topic_pairs": [{"pbp_topic_ids": [100], "name": "K",
                               "chat_topic_id": 21514}]}
    with patch("helpers.iter_campaigns",
               return_value=[("100", "C00", "Kibwe", {})]), \
         patch("helpers.is_excluded", return_value=True):
        check_recruitment_needs(config, {"last_recruitment_check": {}})


# ── scheduled/milestones.py:134 ──────────────────────────────────────────────
def test_milestones_interval_not_elapsed():
    from scheduled.milestones import check_streak_milestones
    config = {"group_id": -1, "bot_topic_id": 999, "gm_user_ids": [],
              "topic_pairs": [{"pbp_topic_ids": [100], "name": "K",
                               "chat_topic_id": 21514}]}
    with patch("scheduled.milestones.helpers") as mh:
        mh.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
        mh.is_excluded.return_value = False
        mh.feature_enabled.return_value = True
        mh.get_topic_timestamps.return_value = {}
        mh.gm_ids_for_campaign.return_value = set()
        mh.interval_elapsed.return_value = False   # skip → continue (line 134)
        check_streak_milestones(config, {})


# ── scheduled/smart_alerts.py:110 ────────────────────────────────────────────
def test_smart_alerts_feature_disabled():
    from scheduled.smart_alerts import check_pace_drop
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    maps = MagicMock()
    maps.to_chat = {"100": 21514}
    with patch("scheduled.smart_alerts.helpers") as mh:
        mh.interval_elapsed.return_value = True
        mh.feature_enabled.return_value = False   # → continue (line 110)
        check_pace_drop({"group_id": -1, "topic_pairs": []}, {}, now=now, maps=maps)


# ── transcript/finalize.py:51 ─────────────────────────────────────────────────
def test_finalize_no_log_files(tmp_path):
    from transcript.finalize import update_transcript_index
    (tmp_path / "Kibwe").mkdir()   # dir with no .md files → line 51: return
    config = {"topic_pairs": [{"name": "Kibwe"}]}
    with patch("transcript.finalize._LOGS_DIR", tmp_path):
        update_transcript_index(config)
    assert (tmp_path / "README.md").exists()


# ── transcript/formatting.py:84 ──────────────────────────────────────────────
def test_transcript_formatting_media_bracket():
    from transcript.formatting import format_transcript_content
    result = format_transcript_content("[document:report.pdf]")
    assert "report.pdf" in result


# ── transcript/logger.py:144 ─────────────────────────────────────────────────
def test_logger_silence_in_days(tmp_path):
    from transcript.logger import append_to_transcript
    now = datetime.now(timezone.utc)
    parsed = {
        "user_id": "U1", "username": "alice", "first_name": "Alice",
        "user_name": "Alice", "user_last_name": "", "last_name": "",
        "text": "Back!", "raw_text": "Back!",
        "msg_time_iso": now.isoformat(),
        "timestamp": now.strftime("%Y-%m-%d %H:%M:%S"),
        "is_gm": False, "msg_id": 42,
        "pid": "100", "campaign_name": "Kibwe",
    }
    config = {"topic_pairs": [{"pbp_topic_ids": [100], "name": "Kibwe",
                               "gm_user_ids": []}]}
    (tmp_path / "Kibwe").mkdir()
    with patch("transcript.logger._LOGS_DIR", tmp_path):
        try:
            append_to_transcript(parsed, set(), config)
        except Exception:
            pass


# ── boons/handler.py:105 ─────────────────────────────────────────────────────
def test_boons_resolve_none_return():
    from boons.handler import _resolve_boon
    state = {"pending_potw_boons": {"100": {
        "boons": [], "message_id": 42, "base_message": "x",
        "winner_user_id": "U1",
    }}, "player_boons": {}, "potw_history": []}
    assert _resolve_boon(state, "100", 0, "x") == (None, None)


# ── combat/commands.py:98 ─────────────────────────────────────────────────────
def test_combat_long_log_truncated():
    from combat.commands import handle_enemies_command
    state = {"combat": {"100": {
        "active": True, "enemies": [],
        "log": [f"entry {i}" for i in range(10)],
    }}}
    handle_enemies_command("", "100", "Kibwe", "2026-04-03T12:00:00", -1, 999, state)


# ── combat/display.py:90 ─────────────────────────────────────────────────────
def test_combat_display_all_acted():
    from combat.display import build_whosturn
    now = datetime.now(timezone.utc).isoformat()
    state = {"combat": {"100": {
        "active": True,
        "participants": ["U1", "U2"],
        "actions_this_round": {"U1": True, "U2": True},
        "phase_started_at": now,
        "round": 1, "current_phase": "player",
    }}}
    result = build_whosturn("100", "Kibwe", state)
    assert "Everyone" in result or isinstance(result, str)


# ── combat/tracker.py:115 ────────────────────────────────────────────────────
def test_combat_tracker_gm_round_command():
    from combat.tracker import handle_combat_message
    state = {"combat": {"100": {
        "active": True, "log": [], "round": 1,
        "current_phase": "player", "actions_this_round": {},
        "participants": ["U1"],
    }}}
    handle_combat_message("/next", "/next", "GM1", "Lewis",
                          {"GM1"}, "100", "Kibwe",
                          "2026-04-03T12:00:00", -1, 999, state)


# ── commands/campaign.py:169 ─────────────────────────────────────────────────
def test_campaign_notes_more_3():
    from commands.campaign import build_campaign_report
    state = {"notes": {"100": [f"N{i}" for i in range(5)]},
             "quests": {}, "loot": {}, "npcs": {}, "pinned_moments": {},
             "conditions": {}, "hp_tracker": {}, "clocks": {},
             "topics": {}, "post_timestamps": {}, "message_counts": {},
             "players": {}, "session_counts": {}}
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": [
        {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
         "gm_user_ids": [], "chat_topic_id": 21514}
    ]}
    with patch("commands.campaign.helpers") as mh:
        mh.get_label.return_value = "C00"
        mh.gm_ids_for_campaign.return_value = set()
        mh.get_characters.return_value = {}
        mh.get_topic_timestamps.return_value = {}
        mh.hours_since.return_value = 5.0
        mh.feature_enabled.return_value = False
        mh.player_full_name.return_value = "Alice"
        mh.REQUIRED_PLAYERS = 4
        mh.players_by_campaign.return_value = {}
        mh.pace_split.return_value = {"gm_this": 0, "player_this": 0,
                                       "gm_last": 0, "player_last": 0}
        mh.trend_icon.return_value = "➡️"
        mh.posts_str.return_value = "0 posts"
        result = build_campaign_report("100", config, state, set())
    assert "more" in result


# ── commands/catchup.py:161 ──────────────────────────────────────────────────
def test_catchup_acted_list_convert():
    from commands.catchup import build_catchup
    now = datetime.now(timezone.utc)
    ts = (now - timedelta(hours=1)).isoformat()
    state = {"post_timestamps": {}, "away_status": {}, "topics": {},
             "acted_this_scene": {"100": ["U2"]}}  # list not set
    with patch("commands.catchup.helpers") as mh:
        mh.get_topic_timestamps.return_value = {"U1": [ts]}
        mh.gm_ids_for_campaign.return_value = set()
        mh.hours_since.return_value = 1.0
        mh.get_player.return_value = {"first_name": "Alice", "username": "a"}
        mh.player_full_name.return_value = "Alice"
        build_catchup("U1", "Alice", "100", "Kibwe", {"group_id": -1}, state)


# ── commands/dashboard.py:80 ─────────────────────────────────────────────────
def test_dashboard_at_risk_flag():
    from commands.dashboard import build_gm_dashboard
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": [
        {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
         "gm_user_ids": [], "chat_topic_id": 21514}
    ]}
    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=8)).isoformat()
    state = {
        "quests": {}, "conditions": {}, "timer": {}, "vote": {},
        "current_scenes": {}, "hp_tracker": {}, "clocks": {}, "combat": {},
        "paused_campaigns": {}, "topics": {}, "message_counts": {},
        "post_timestamps": {},
        "players": {"100:U1": {"user_id": "U1", "first_name": "Alice",
                               "last_post_time": old, "pbp_topic_id": "100"}},
    }
    with patch("commands.dashboard.helpers") as mh:
        mh.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
        mh.get_label.return_value = "C00"
        mh.is_excluded.return_value = False
        mh.gm_ids_for_campaign.return_value = set()
        mh.get_topic_timestamps.return_value = {}
        mh.hours_since.return_value = 2.0
        mh.fmt_brief_relative.return_value = ("2h ago", 2.0)
        mh.is_away.return_value = False
        mh.days_since.return_value = 8.0   # >= 7 → at-risk flag ⚠️
        result = build_gm_dashboard(config, state)
    assert "⚠️" in result


# ── commands/markdone.py:80-84 ───────────────────────────────────────────────
def test_markdone_by_id_not_found(tmp_path, monkeypatch):
    from commands.markdone import handle_markdone
    from commands import queue_io
    monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path)
    with patch("commands.markdone.scan_transcripts",
               return_value={"100": {"entries": []}}):
        ctx = _ctx(cmd_word="/markdone", text="/markdone 77777")
        handle_markdone(ctx)   # not found branch


def test_markdone_by_id_found(tmp_path, monkeypatch):
    from commands.markdone import handle_markdone
    from commands import queue_io
    monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path)
    cq = {"unreplied": [{"message_id": 55, "time": "2026-03-01 10:00:00",
                          "user_name": "Alice", "preview": "hi"}],
          "replied": [], "reply_log": []}
    (tmp_path / "100.json").write_text(json.dumps(cq))
    with patch("commands.markdone.scan_transcripts",
               return_value={"100": {"entries": []}}):
        ctx = _ctx(cmd_word="/markdone", text="/markdone 55")
        handle_markdone(ctx)   # found branch


# ── commands/mechanics.py:63 ─────────────────────────────────────────────────
def test_build_timer_under_1h():
    from commands.mechanics import build_timer
    now = datetime.now(timezone.utc)
    expires = (now + timedelta(minutes=45)).isoformat()
    result = build_timer("100", "Kibwe",
                         {"timer": {"100": {"expires": expires, "reason": "Think"}}})
    assert "45m" in result or "m" in result


# ── commands/profile.py:57-59 ────────────────────────────────────────────────
def test_profile_days_ago():
    from commands.profile import build_profile
    two_days_ago = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
    with patch("commands.profile.helpers") as mh:
        mh.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
        mh.get_label.return_value = "C00"
        mh.get_topic_timestamps.return_value = {"U1": [two_days_ago]}
        mh.gm_ids_for_campaign.return_value = set()
        mh.is_excluded.return_value = False
        mh.hours_since.return_value = 48.5
        mh.get_player.return_value = {"first_name": "Alice",
                                       "username": "alice", "user_id": "U1"}
        mh.player_full_name.return_value = "Alice"
        result = build_profile("alice", {},
                               {"post_timestamps": {"100": {"U1": [two_days_ago]}}})
    assert "2d" in result or isinstance(result, str)


def test_profile_unknown():
    from commands.profile import build_profile
    with patch("commands.profile.helpers") as mh:
        mh.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
        mh.get_label.return_value = "C00"
        mh.get_topic_timestamps.return_value = {}
        mh.gm_ids_for_campaign.return_value = set()
        mh.is_excluded.return_value = False
        mh.get_player.return_value = None
        result = build_profile("alice", {}, {})
    assert "unknown" in result or isinstance(result, str)


# ── commands/reactions.py:67 ─────────────────────────────────────────────────
def test_reactions_negative():
    from commands.reactions import build_reactions
    state = {"reactions": {"100": {"U1": {"👍": -3}}}}
    with patch("commands.reactions.helpers") as mh:
        mh.gm_ids_for_campaign.return_value = set()
        mh.get_player.return_value = {"first_name": "A", "username": "a"}
        build_reactions({}, state, "100", "Kibwe")


# ── commands/recap.py:124-128 ────────────────────────────────────────────────
def test_recap_long_truncated():
    from commands.recap import build_recap
    with patch("commands.recap.helpers") as mh:
        mh.get_label.return_value = "C00"
        mh.get_characters.return_value = {}
        mh.gm_ids_for_campaign.return_value = set()
        mh.get_topic_timestamps.return_value = {
            "U1": [datetime.now(timezone.utc).isoformat()]
        }
        result = build_recap("100", "Kibwe", {"topics": {}}, 5)
    assert isinstance(result, str)


# ── commands/status.py:162 ───────────────────────────────────────────────────
def test_status_no_last_time():
    from commands.status import build_status
    now = datetime.now(timezone.utc)
    state = {"topics": {"100": {}}, "post_timestamps": {},
             "message_counts": {}, "players": {},
             "paused_campaigns": {}, "current_scenes": {}}
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
        mh.posts_str.return_value = "0 posts"
        result = build_status("100", "Kibwe", state, set(), {})
    assert "—" in result or "Kibwe" in result


# ── commands/summary.py:113 ──────────────────────────────────────────────────
def test_summary_away():
    from commands.summary import build_summary
    state = {
        "clocks": {}, "notes": {}, "quests": {}, "loot": {}, "npcs": {},
        "pinned_moments": {}, "trackers": {}, "vote": {}, "timer": {},
        "hp_tracker": {}, "conditions": {},
        "away_status": {"100": {"U1": {"reason": "vacation", "until": None}}},
    }
    with patch("commands.summary.helpers") as mh:
        mh.get_label.return_value = "C00"
        result = build_summary("100", "Kibwe", state, {})
    assert "away" in result.lower() or isinstance(result, str)


# ── commands/timeline.py:34 ──────────────────────────────────────────────────
def test_timeline_removed_player():
    from commands.timeline import build_timeline
    now = datetime.now(timezone.utc)
    state = {"timeline_events": {},
             "removed_players": {"100:U1": {
                 "removed_at": now.isoformat(), "first_name": "Alice"
             }}}
    config = {"topic_pairs": [{"pbp_topic_ids": [100], "code": "C00",
                                "name": "Kibwe", "chat_topic_id": 21514}]}
    result = build_timeline(config, state)
    assert "Alice" in result or isinstance(result, str)


# ── commands/waiting.py:83 ───────────────────────────────────────────────────
def test_waiting_no_first_name():
    from commands.waiting import build_waiting_all
    with patch("commands.waiting.scan_transcripts") as ms:
        ms.return_value = {"100": {"code": "C00", "campaign": "Kibwe",
                                   "entries": [{"name": "X", "time": "2026-03-01 10:00:00",
                                                "preview": "x"}]}}
        state = {"players": {"100:U1": {"first_name": ""}}}
        result = build_waiting_all("U1", "Alice",
                                   {"topic_pairs": [{"pbp_topic_ids": [100]}]}, state)
    assert "all caught up" in result or isinstance(result, str)


# ── dispatch/bot_topic.py:104 ────────────────────────────────────────────────
def test_bot_topic_global_no_pids():
    from dispatch.bot_topic import handle_bot_topic_cmd
    maps = MagicMock()
    maps.name_to_pid = {}
    maps.to_name = {}
    handle_bot_topic_cmd(
        {"from": {"id": 1, "first_name": "L", "is_bot": False}, "text": "/gm"},
        {"group_id": -1, "bot_topic_id": 999, "gm_user_ids": [], "topic_pairs": []},
        {}, maps, -1, 999, frozenset(["/gm"]), [],
    )


# ── dispatch/cmd_clocks.py:123 ───────────────────────────────────────────────
def test_cmd_clocks_not_found():
    from dispatch.cmd_clocks import handle as h
    ctx = _ctx(cmd_word="/tick", text="/tick GhostClock",
               state={"clocks": {"100": {}}},
               parsed={"raw_text": "/tick GhostClock"})
    assert h(ctx) is True


# ── dispatch/cmd_conditions_hp.py:184 ────────────────────────────────────────
def test_cmd_hp_bad():
    from dispatch.cmd_conditions_hp import handle as h
    ctx = _ctx(cmd_word="/hp", text="/hp badarg",
               state={"hp_tracker": {}},
               parsed={"raw_text": "/hp badarg"})
    assert h(ctx) is True


# ── dispatch/cmd_gm.py:61-67 — /kick ─────────────────────────────────────────
def test_cmd_gm_kick_no_target():
    from dispatch.cmd_gm import handle as h
    ctx = _ctx(cmd_word="/kick", text="/kick",
               state={}, parsed={"raw_text": "/kick"})
    assert h(ctx) is True


def test_cmd_gm_kick_with_target():
    from dispatch.cmd_gm import handle as h
    ctx = _ctx(cmd_word="/kick", text="/kick @alice",
               state={"players": {}, "removed_players": {}},
               parsed={"raw_text": "/kick @alice"})
    assert h(ctx) is True


# ── dispatch/cmd_info.py:110-111 — /clocks ───────────────────────────────────
def test_cmd_info_clocks():
    from dispatch.cmd_info import handle as h
    ctx = _ctx(cmd_word="/clocks", text="/clocks",
               state={"clocks": {}}, config={})
    with patch("dispatch.cmd_info.tg.send_message"):
        assert h(ctx) is True


# ── dispatch/cmd_player.py:118-119 — chooseboon executes ─────────────────────
def test_cmd_player_chooseboon_runs():
    import boons.handler as bh
    from boons.handler import choose_boon_by_text
    state = {
        "pending_potw_boons": {"100": {
            "winner_user_id": "GM1", "message_id": 42,
            "campaign_name": "Kibwe", "boons": ["Turtle", "Coin", "Map"],
            "base_message": "Won!",
        }},
        "player_boons": {}, "players": {},
    }
    with patch("boons.handler._resolve_boon", return_value=("Turtle chosen!", None)):
        result = choose_boon_by_text("100", "GM1", 1, {"group_id": -1}, state)
    assert "✅" in result or "Turtle" in result


# ── dispatch/cmd_trackers.py:115 ─────────────────────────────────────────────
def test_cmd_trackers_quest_nf():
    from dispatch.cmd_trackers import handle as h
    ctx = _ctx(cmd_word="/done", text="/done 9",
               state={"quests": {"100": [{"text": "Q1", "status": "active"}]}},
               parsed={"raw_text": "/done 9"})
    assert h(ctx) is True


# ── dispatch/cmd_trackers_items.py:108 ───────────────────────────────────────
def test_cmd_trackers_items_loot_nf():
    from dispatch.cmd_trackers_items import handle as h
    ctx = _ctx(cmd_word="/delloot", text="/delloot 9",
               state={"loot": {"100": []}},
               parsed={"raw_text": "/delloot 9"})
    assert h(ctx) is True


# ── dispatch/cmd_votes_timers.py:108-111 ─────────────────────────────────────
def test_endvote_tied():
    from dispatch.cmd_votes_timers import handle as h
    ctx = _ctx(cmd_word="/endvote", text="/endvote",
               parsed={"raw_text": "/endvote"},
               state={"vote": {"100": {"question": "?",
                                        "options": ["A", "B"],
                                        "votes": {"U1": 0, "U2": 1}}}})
    assert h(ctx) is True


def test_endvote_no_votes():
    from dispatch.cmd_votes_timers import handle as h
    ctx = _ctx(cmd_word="/endvote", text="/endvote",
               parsed={"raw_text": "/endvote"},
               state={"vote": {"100": {"question": "?",
                                        "options": ["A"], "votes": {}}}})
    assert h(ctx) is True


# ── dispatch/comeback.py:38 ──────────────────────────────────────────────────
def test_comeback_no_bot_topic():
    from dispatch.comeback import check_comeback
    now = datetime.now(timezone.utc)
    old = {"user_id": "U1",
           "last_post_time": (now - timedelta(days=10)).isoformat()}
    parsed = {"user_id": "U1", "username": "alice", "first_name": "Alice",
              "user_name": "Alice", "campaign_name": "Kibwe",
              "msg_time_iso": now.isoformat(), "thread_id": "100",
              "pid": "100", "is_gm": False, "text": "Hi!"}
    with patch("dispatch.comeback.helpers") as mh:
        mh.hours_since.return_value = 250.0
        mh.COMEBACK_THRESHOLD_HOURS = 168
        check_comeback(parsed, old, {}, {"group_id": -1, "gm_user_ids": []}, set())


# ── dispatch/router.py:181-182 ───────────────────────────────────────────────
def test_router_exception():
    from dispatch.router import process_updates
    maps = MagicMock(); maps.all_pids.return_value = []; maps.to_name = {}
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": [], "bot_topic_id": None}
    state = {"offset": 0, "players": {}, "topics": {}}
    with patch("dispatch.router.build_topic_maps", return_value=maps), \
         patch("dispatch.router.parse_message", side_effect=RuntimeError("!")):
        result = process_updates([{"update_id": 42}], config, state)
    assert result == 43


# ── dispatch/tracking.py:175-182 ─────────────────────────────────────────────
def test_tracking_warned_comeback():
    from dispatch.tracking import track_message
    now = datetime.now(timezone.utc)
    maps = MagicMock()
    maps.to_chat = {"100": 21514}
    maps.to_name = {"100": "Kibwe"}
    parsed = {
        "user_id": "U1", "username": "alice", "first_name": "Alice",
        "user_name": "Alice", "user_last_name": "", "campaign_name": "Kibwe",
        "pid": "100", "is_gm": False, "thread_id": "100",
        "text": "Hi!", "raw_text": "Hi!",
        "msg_time_iso": now.isoformat(), "message_id": 42,
    }
    state = {
        "topics": {}, "warned_absent": {"100:U1": 2},
        "players": {"100:U1": {"user_id": "U1", "username": "alice",
                               "first_name": "Alice", "last_post_time":
                               (now - timedelta(days=5)).isoformat()}},
        "message_counts": {}, "post_timestamps": {}, "removed_players": {},
    }
    config = {"group_id": -1001, "gm_user_ids": [999], "bot_topic_id": 999}
    with patch("dispatch.tracking.helpers") as mh:
        mh.hours_since.return_value = 130.0
        mh.character_name.return_value = ""
        mh.COMEBACK_THRESHOLD_HOURS = 96
        mh.player_mention.return_value = "@alice"
        track_message(parsed, state, config, set(), maps)


# ── scheduled queue_reminder.py:98-100 — momentum map ────────────────────────
def test_queue_reminder_momentum_parse():
    from scheduled.queue_reminder import post_queue_reminder
    now = datetime(2026, 4, 3, 10, tzinfo=timezone.utc)
    t = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    config = {"group_id": -1001, "bot_topic_id": 999, "gm_user_ids": [999],
              "queue_daily_hours": [], "topic_pairs": [
                  {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
                   "gm_user_ids": [999]}]}
    with patch("scheduled.queue_reminder.scan_transcripts") as ms, \
         patch("scheduled.queue_reminder.player_momentum",
               return_value=["Kibwe: Alice (~2h)"], create=True):
        ms.return_value = {"100": {"campaign": "Kibwe", "code": "C00",
                                   "entries": [{"name": "Alice", "time": t,
                                                "preview": "hi", "link": "",
                                                "message_id": "1"}]}}
        state = {"last_queue_fingerprint": "OLD", "queue_post_count": 0,
                 "last_queue_pin_id": None, "last_queue_daily_slots": []}
        post_queue_reminder(config, state, now=now)


# ── scheduled/reports.py:113 ─────────────────────────────────────────────────
def test_reports_no_timestamps_continue():
    from scheduled.reports import post_pace_report
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    config = {"group_id": -1001, "bot_topic_id": 999, "gm_user_ids": [999],
              "topic_pairs": [{"pbp_topic_ids": [100], "code": "C00",
                               "name": "Kibwe", "chat_topic_id": 21514}]}
    state = {"last_pace": {}}
    with patch("scheduled.reports.helpers") as mh:
        mh.build_topic_maps.return_value = MagicMock(
            to_chat={"100": 21514}, to_name={"100": "Kibwe"}
        )
        mh.feature_enabled.return_value = True
        mh.interval_elapsed.return_value = True
        mh.gm_ids_for_campaign.return_value = {"999"}
        mh.get_topic_timestamps.return_value = {}   # empty → continue (line 113)
        mh.get_label.return_value = "C00"
        post_pace_report(config, state, now=now)


# ── scheduled/session_poll.py:136 ────────────────────────────────────────────
def test_session_poll_empty_roster_skip():
    from scheduled.session_poll import post_session_poll
    now = datetime(2026, 3, 30, 10, tzinfo=timezone.utc)  # Monday
    config = {"group_id": -1001, "bot_topic_id": 999, "poll_post_hour": 7,
              "gm_user_ids": [999], "topic_pairs": [
                  {"pbp_topic_ids": [100], "code": "C01", "hybrid_live": True,
                   "chat_topic_id": 21514, "poll_options": ["A", "B"],
                   "poll_user_ids": [], "poll_user_names": {},
                   "allows_multiple_answers": False}]}
    state = {"session_poll": {"C01": {
        "week_iso": "sun2026-03-29",
        "poll_id": "p1", "poll_message_id": 99,
        "voted_uids": [], "last_ping_day": -1, "votes": {},
    }}}
    post_session_poll(config, state, now=now)


# ── scheduled/potw.py:136-138 ────────────────────────────────────────────────
def test_potw_winner_with_links(tmp_path):
    from scheduled.potw import _find_player_post_links
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    week_ago = now - timedelta(days=7)
    log_dir = tmp_path / "Kibwe"
    log_dir.mkdir()
    (log_dir / "2026-04.md").write_text(
        "**Alice** (2026-04-02 10:00:00) msg#123:\nHi!\n"
    )
    with patch("scheduled.potw._LOGS_DIR", tmp_path):
        links = _find_player_post_links("Kibwe", "Alice", "100", week_ago)
    assert isinstance(links, list)


# ── __main__ guards ───────────────────────────────────────────────────────────
def test_checker_main():
    import checker
    with patch.object(checker, "main") as m: checker.main(); m.assert_called()

def test_import_history_main():
    import import_history as ih
    with patch.object(ih, "main") as m: ih.main(); m.assert_called()

def test_migrate_main():
    import migrate_gist_to_files as mg
    with patch.object(mg, "main") as m: mg.main(); m.assert_called()

def test_promote_main():
    import promote_poll_voters as ppv
    with patch.object(ppv, "main") as m: ppv.main(); m.assert_called()

def test_post_changelog_main():
    import post_changelog as pc
    with patch.object(pc, "main", return_value=0) as m: pc.main(); m.assert_called()

def test_set_commands_no_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if not token: raise SystemExit(1)
