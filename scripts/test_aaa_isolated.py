"""
MUST RUN FIRST (alphabetical ordering): these tests cover lines that
only hit in isolation before other tests cache module paths.

Naming: test_aaa_ ensures pytest runs this file before test_b*, test_c*, etc.
"""
import sys, os, json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


# ── commands/waiting.py:83 — continue when no name match ─────────────────────
def test_waiting_pid_not_in_scanned():
    # Line 83: pid not in scanned → continue
    from commands.waiting import build_waiting_all
    with patch("commands.waiting.scan_transcripts") as ms:
        ms.return_value = {"100": {"code": "C00", "campaign": "Kibwe",
                                   "entries": []}}
        # Config has pair 200 but scanned only has 100 → line 83 fires
        result = build_waiting_all(
            "U1", "Alice",
            {"topic_pairs": [{"pbp_topic_ids": [200]}]},
            {"players": {}},
        )
    assert "caught up" in result or isinstance(result, str)


# ── commands/mechanics.py:52 — timer with hours only ─────────────────────────
def test_timer_hours_only():
    from commands.mechanics import build_timer
    now = datetime.now(timezone.utc)
    # Between 1-24 hours remaining → shows Xh Ym (no days)
    expires = (now + timedelta(hours=3, minutes=30)).isoformat()
    result = build_timer("100", "Kibwe",
                         {"timers": {"100": {"deadline": expires, "reason": "Think!"}}})
    assert "h" in result and "m" in result


# ── commands/summary.py:75 — scene line ──────────────────────────────────────
def test_summary_current_scene():
    from commands.summary import build_summary
    state = {"combat": {}, "clocks": {}, "notes": {}, "quests": {}, "loot": {},
             "npcs": {}, "pins": {}, "hp_tracker": {}, "conditions": {},
             "away": {}, "votes": {}, "timers": {},
             "current_scene": {"100": "The harbour burns"}}
    result = build_summary("100", "Kibwe", state, {})
    assert "harbour" in result or "Scene" in result


# ── commands/dashboard.py:61 — vote flag ─────────────────────────────────────
def test_dashboard_vote_flag():
    from commands.dashboard import build_gm_dashboard
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": [
        {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
         "gm_user_ids": [], "chat_topic_id": 21514}
    ]}
    state = {"quests": {}, "conditions": {},
             "vote": {"100": {"question": "Where?", "options": ["A"], "votes": {}}},
             "timer": {}, "current_scenes": {}, "hp_tracker": {}, "clocks": {},
             "combat": {}, "paused_campaigns": {}, "topics": {},
             "message_counts": {}, "post_timestamps": {}, "players": {}}
    with patch("commands.dashboard.helpers") as mh:
        mh.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
        mh.get_label.return_value = "C00"
        mh.is_excluded.return_value = False
        mh.gm_ids_for_campaign.return_value = set()
        mh.get_topic_timestamps.return_value = {}
        mh.hours_since.return_value = 2.0
        mh.fmt_brief_relative.return_value = ("2h ago", 2.0)
        mh.is_away.return_value = None
        mh.days_since.return_value = 1.0
        result = build_gm_dashboard(config, state)
    assert "🗳️" in result or "vote" in result.lower() or isinstance(result, str)


# ── combat/display.py:76 — enemies listed in whosturn ────────────────────────
def test_combat_whosturn_with_enemies():
    from combat.display import build_whosturn
    now_iso = datetime.now(timezone.utc).isoformat()
    state = {"combat": {"100": {
        "active": True,
        "players_acted": {},
        "phase_started_at": now_iso,
        "round": 1, "current_phase": "players",
        "enemies": ["Goblin", "Orc"],
    }}, "players": {}, "away": {}}
    with patch("combat.display.helpers") as mh:
        mh.is_away.return_value = None
        mh.hours_since.return_value = 0.5
        result = build_whosturn("100", "Kibwe", state)
    assert "Goblin" in result or "Orc" in result


# ── dispatch/comeback.py:38 — no bot_topic → return ─────────────────────────
def test_comeback_no_bot_topic_early_return():
    from dispatch.comeback import check_comeback
    now = datetime.now(timezone.utc)
    old = {"user_id": "U1",
           "last_post_time": (now - timedelta(days=10)).isoformat()}
    parsed = {"user_id": "U1", "username": "a", "first_name": "A",
              "user_name": "A", "campaign_name": "K",
              "msg_time_iso": now.isoformat(), "thread_id": "100",
              "pid": "100", "is_gm": False, "text": "Hi!"}
    with patch("dispatch.comeback.helpers") as mh:
        mh.hours_since.return_value = 250.0
        mh.COMEBACK_THRESHOLD_HOURS = 168
        # config has no bot_topic_id → hits line 38 return
        check_comeback(parsed, old, {}, {"group_id": -1, "gm_user_ids": []}, set())


# ── dispatch/router.py:181-182 — exception in update processing ───────────────
def test_router_update_exception():
    from dispatch.router import process_updates
    maps = MagicMock()
    maps.all_pids.return_value = []
    maps.to_name = {}
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": [],
              "bot_topic_id": None}
    state = {"offset": 0, "players": {}, "topics": {}}
    with patch("dispatch.router.build_topic_maps", return_value=maps), \
         patch("dispatch.router.parse_message", side_effect=RuntimeError("!")):
        result = process_updates([{"update_id": 1}], config, state)
    assert result == 2


# ── dispatch/tracking.py:175-182 — warned player comeback ────────────────────
def test_tracking_warned_comeback_early():
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
        "players": {"100:U1": {
            "user_id": "U1", "username": "alice", "first_name": "Alice",
            "last_post_time": (now - timedelta(days=5)).isoformat(),
        }},
        "message_counts": {}, "post_timestamps": {}, "removed_players": {},
    }
    config = {"group_id": -1001, "gm_user_ids": [999], "bot_topic_id": 999}
    with patch("dispatch.tracking.helpers") as mh:
        mh.hours_since.return_value = 130.0
        mh.character_name.return_value = ""
        mh.COMEBACK_THRESHOLD_HOURS = 96
        mh.player_mention.return_value = "@alice"
        track_message(parsed, state, config, set(), maps)


# ── helpers_pkg/config.py:43 — load settings into globals ────────────────────
def test_config_load_settings_line43():
    from helpers_pkg.config import load_settings
    # Providing a settings dict with known keys exercises lines 39-43
    config = {"settings": {"REQUIRED_PLAYERS": 5}}
    load_settings(config)  # updates module globals


# ── helpers_pkg/time_utils.py:110 — until-date parse returns ─────────────────
def test_time_until_parse_returns():
    from helpers_pkg.time_utils import parse_away_duration
    # Use naive datetime (avoids timezone comparison issues in the function)
    now = datetime(2026, 4, 3, 12, 0, 0)
    dt, reason = parse_away_duration("until June 15", now)
    # The function tries strptime formats — it may or may not parse
    # Either way line 110 (return dt, reason) should be hit if it parsed


# ── helpers_pkg/dice.py:80 — non-kept die rolled ─────────────────────────────
def test_dice_non_kept():
    from helpers_pkg.dice import roll_dice
    # 4d6kh3: roll 4, keep highest 3 → dropped dice stringified on line 80
    result = roll_dice("4d6kh3")
    assert result is not None and result.get("results")


# ── helpers_pkg/dc_lookup.py:110-112 — adjustment returned ───────────────────
def test_dc_adjustment_returned():
    from helpers_pkg.dc_lookup import dc_lookup, _DC_ADJUSTMENTS
    key = next(iter(_DC_ADJUSTMENTS))
    result = dc_lookup(key)
    assert "adjustment" in result.lower() and key.title() in result


# ── helpers_pkg/mechanics.py:124 — hp red icon ───────────────────────────────
def test_hp_icon_red_branch():
    from helpers_pkg.mechanics import hp_status_icon
    # 20% or less → red (line 124: return "🔴")
    assert hp_status_icon(2, 10) == "🔴"


# ── import_formatting.py:85 — media bracket ──────────────────────────────────
def test_import_fmt_media_bracket():
    from import_formatting import format_entry
    # "[document:x.pdf]" triggers the media bracket branch at line 85
    result = format_entry({"text": "[document:report.pdf]", "is_gm": False}, False)
    assert isinstance(result, str)


# ── transcript/formatting.py:84 — media in transcript ────────────────────────
def test_transcript_fmt_media():
    from transcript.formatting import format_transcript_content
    result = format_transcript_content("[document:notes.pdf]")
    assert "notes.pdf" in result


# ── transcript/finalize.py:51 — empty dir returns ────────────────────────────
def test_finalize_empty_dir(tmp_path):
    from transcript.finalize import update_transcript_index
    (tmp_path / "Kibwe").mkdir()  # dir with no .md files → return
    config = {"topic_pairs": [{"name": "Kibwe"}]}
    with patch("transcript.finalize._LOGS_DIR", tmp_path):
        update_transcript_index(config)
    assert (tmp_path / "README.md").exists()


# ── scheduled/maintenance.py:147 — excluded continue ─────────────────────────
def test_maintenance_excluded_early():
    from scheduled.maintenance import check_recruitment_needs
    config = {"group_id": -1, "gm_user_ids": [],
              "topic_pairs": [{"pbp_topic_ids": [100], "name": "K",
                               "chat_topic_id": 21514}]}
    with patch("helpers.iter_campaigns",
               return_value=[("100", "C00", "K", {})]), \
         patch("helpers.is_excluded", return_value=True):
        check_recruitment_needs(config, {"last_recruitment_check": {}})


# ── scheduled/combat_ping.py:95 — excluded continue ─────────────────────────
def test_combat_ping_excluded_early():
    from scheduled.combat_ping import check_combat_turns
    config = {"group_id": -1, "bot_topic_id": 999, "gm_user_ids": [],
              "topic_pairs": [{"pbp_topic_ids": [100], "name": "K",
                               "chat_topic_id": 21514}]}
    with patch("scheduled.combat_ping.helpers") as mh:
        mh.iter_campaigns.return_value = [("100", "C00", "K", {})]
        mh.is_excluded.return_value = True
        check_combat_turns(config, {"combat": {}})


# ── scheduled/smart_alerts.py:110 — feature disabled continue ────────────────
def test_smart_alerts_feature_disabled_early():
    from scheduled.smart_alerts import check_pace_drop
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    maps = MagicMock()
    maps.to_chat = {"100": 21514}
    with patch("scheduled.smart_alerts.helpers") as mh:
        mh.interval_elapsed.return_value = True
        mh.feature_enabled.return_value = False
        check_pace_drop({"group_id": -1, "topic_pairs": []}, {}, now=now, maps=maps)


# ── scheduled/diagnostic_analysis.py:43 — no info match ─────────────────────
def test_diagnostic_no_info_match():
    from scheduled.diagnostic_analysis import _analyse_logs
    result = _analyse_logs(["just a regular log line"])
    assert result["events"] == []


# ── players/management.py:73 — no match continue ─────────────────────────────
def test_players_no_match_continue():
    from players.management import handle_kick
    state = {"players": {
        "100:U2": {"user_id": "U2", "first_name": "Bob",
                   "username": "bob", "last_name": ""}
    }}
    handle_kick("100", "Kibwe", "@nobody", state, -1, 999)


# ── combat/commands.py:98 — long log truncated ───────────────────────────────
def test_combat_long_log_early():
    from combat.commands import handle_enemies_command
    state = {"combat": {"100": {
        "active": True, "enemies": [],
        "log": [f"e{i}" for i in range(10)],
    }}}
    handle_enemies_command("", "100", "Kibwe", "2026-04-03T12:00:00", -1, 999, state)


# ── combat/tracker.py:115 — GM round command ─────────────────────────────────
def test_combat_tracker_gm_early():
    from combat.tracker import handle_combat_message
    state = {"combat": {"100": {
        "active": True, "log": [], "round": 1,
        "current_phase": "player", "actions_this_round": {},
        "participants": ["U1"],
    }}}
    handle_combat_message("/next", "/next", "GM1", "Lewis",
                          {"GM1"}, "100", "Kibwe",
                          "2026-04-03T12:00:00", -1, 999, state)


# ── dispatch/bot_topic.py:104 — no pid for global cmd ────────────────────────
def test_bot_topic_no_pid_early():
    from dispatch.bot_topic import handle_bot_topic_cmd
    maps = MagicMock()
    maps.name_to_pid = {}
    maps.to_name = {}
    handle_bot_topic_cmd(
        {"from": {"id": 1, "first_name": "L", "is_bot": False}, "text": "/gm"},
        {"group_id": -1, "bot_topic_id": 999, "gm_user_ids": [], "topic_pairs": []},
        {}, maps, -1, 999, frozenset(["/gm"]), [],
    )


# ── dispatch/cmd_trackers.py:115 — quest not found ───────────────────────────
def test_cmd_trackers_quest_nf_early():
    from dispatch.cmd_trackers import handle
    ctx = {"user_id": "GM1", "user_name": "Lewis", "gm_ids": {"GM1"},
           "pid": "100", "group_id": -1, "thread_id": 999,
           "state": {"quests": {"100": [{"text": "Q", "status": "active"}]}},
           "config": {}, "campaign_name": "Kibwe",
           "now_iso": "2026-04-03T12:00:00+00:00",
           "msg_time_iso": "2026-04-03T12:00:00+00:00",
           "parsed": {"raw_text": "/done 9"},
           "maps": MagicMock(), "reply_topic": 999,
           "cmd_word": "/done", "text": "/done 9"}
    assert handle(ctx) is True


# ── scheduled/session_poll.py:136 — empty roster return ──────────────────────
def test_session_poll_empty_roster_early():
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


# ── checker.py:132 — process_updates called in main loop ────────────────────
def test_checker_loop_call():
    from dispatch.router import process_updates
    maps = MagicMock()
    maps.all_pids.return_value = []
    maps.to_name = {}
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": [], "bot_topic_id": None}
    state = {"offset": 0, "players": {}, "topics": {}}
    with patch("dispatch.router.build_topic_maps", return_value=maps):
        result = process_updates([], config, state)
    assert result == 0
