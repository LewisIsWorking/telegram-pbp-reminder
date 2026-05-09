"""Coverage tests extracted from test_final_gaps.py — bin 1.

Tests grouped by the first production module they import. This bin
covers branches in:
  - scheduled.alerts+combat_ping+maintenance+milestones+reports+tracking+management+campaign+reactions
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
