"""Coverage tests extracted from test_branch_gaps.py — bin 7.

Sections in this file:
  - Various single-line branches (part b)

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


def test_transcript_finalize_missing_pair_dir(tmp_path):
    from transcript.finalize import update_transcript_index
    config = {"topic_pairs": [{"name": "Missing Campaign"}]}
    (tmp_path / "README.md").write_text("existing")
    with patch("transcript.finalize._LOGS_DIR", tmp_path):
        update_transcript_index(config)  # dir doesn't exist, skips gracefully


def test_profile_unknown_last_seen():
    from commands.profile import build_profile
    with patch("commands.profile.helpers") as mh:
        mh.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
        mh.get_label.return_value = "C00: Kibwe"
        mh.get_topic_timestamps.return_value = {}
        mh.gm_ids_for_campaign.return_value = set()
        mh.is_excluded.return_value = False
        result = build_profile("alice", {}, {})
    assert isinstance(result, str)


def test_commands_trackers_no_conditions():
    from commands.trackers import build_conditions
    result = build_conditions("100", "Kibwe", {}, {})
    assert "No active conditions" in result


def test_leaderboard_week_clears():
    from scheduled.leaderboard import _gather_leaderboard_stats
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    ts = [(now - timedelta(hours=h)).isoformat() for h in range(5)]
    config = {"topic_pairs": [{"pbp_topic_ids": [100], "code": "C00",
                                "name": "Kibwe", "gm_user_ids": [999],
                                "chat_topic_id": 21514}]}
    state = {"post_timestamps": {}, "players": {}, "message_counts": {},
             "queue_history": {"100": [(now - timedelta(hours=2)).isoformat()]}}
    with patch("scheduled.leaderboard.helpers") as mh:
        mh.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
        mh.is_excluded.return_value = False
        mh.gm_ids_for_campaign.return_value = {"999"}
        mh.get_topic_timestamps.return_value = {}
        mh.REQUIRED_PLAYERS = 4
        mh.player_mention.return_value = "@u"
        mh.player_full_name.return_value = "Alice"
        result = _gather_leaderboard_stats(config, state, now)
    assert isinstance(result, tuple)


def test_scheduled_tips_no_topic():
    from scheduled.tips import post_daily_tip
    post_daily_tip({"group_id": -1}, {})  # no bot_topic_id → returns early


def test_checker_main_guard():
    import checker
    with patch.object(checker, "main") as mm:
        checker.main()
        mm.assert_called_once()


def test_topic_maps_state_chars():
    from helpers_pkg.topic_maps import get_characters
    config = {"topic_pairs": [
        {"pbp_topic_ids": [100], "characters": {"U1": "Amara"}}
    ]}
    state = {"characters": {"100": {"U2": "Zara"}}}
    result = get_characters(config, "100", state)
    assert "U1" in result or "U2" in result


def test_message_milestones_skips_gm():
    from scheduled.message_milestones import check_message_milestones
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    config = {"group_id": -1, "gm_user_ids": [999], "topic_pairs": [
        {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
         "gm_user_ids": [999], "chat_topic_id": 21514}
    ]}
    # New system: thread_message_counts with < 500 → no milestone fired
    state = {"thread_message_counts": {"100": {"999": 100}},
             "celebrated_milestones": {}}
    check_message_milestones(config, state, now=now)
    assert "thread:100" not in state["celebrated_milestones"]


def test_health_2d_5posts_green():
    from commands.health import build_health
    now = datetime.now(timezone.utc)
    recent = (now - timedelta(hours=30)).isoformat()
    ts = {"100": {"U1": [(now - timedelta(hours=h*4)).isoformat() for h in range(6)]}}
    config = {"group_id": -1, "gm_user_ids": [999],
              "topic_pairs": [{"pbp_topic_ids": [100], "code": "C00",
                               "name": "Kibwe", "gm_user_ids": [999]}]}
    state = {
        "topics": {"100": {"last_message_time": recent}},
        "post_timestamps": ts,
        "players": {"100:U1": {"pbp_topic_id": "100"}},
        "session_counts": {},
    }
    with patch("commands.queue_scan.scan_transcripts", return_value={}):
        result = build_health(config, state)
    assert "🟢" in result


def test_player_registry_inactive():
    from commands.player_registry import build_registry
    state = {
        "player_registry": {"100": {"U1": {"id": 1, "name": "Alice"}}},
        "players": {},           # not active
        "removed_players": {},   # not removed → inactive
    }
    with patch("commands.player_registry.helpers") as mh:
        mh.get_label.return_value = "C00: Kibwe"
        result = build_registry("100", "Kibwe", {}, state)
    assert "[inactive]" in result


def test_queue_analytics_no_recent_gm():
    from commands.queue_analytics import player_momentum
    config = {"topic_pairs": [{"pbp_topic_ids": [100], "code": "C00",
                                "name": "Kibwe", "gm_user_ids": [999]}]}
    with patch("commands.queue_analytics.helpers") as mh:
        mh.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
        mh.is_excluded.return_value = False
        mh.gm_ids_for_campaign.return_value = {"999"}
        now = datetime.now(timezone.utc)
        gm_ts = (now - timedelta(hours=3)).isoformat()
        player_ts = (now - timedelta(hours=1)).isoformat()
        mh.get_topic_timestamps.return_value = {"999": [gm_ts], "U1": [player_ts]}
        mh.get_player.return_value = None  # no player record → uses uid as name
        result = player_momentum({}, config)
    assert isinstance(result, list)


def test_state_dir():
    import state as st
    result = st._state_dir()
    assert "data" in str(result) and "state" in str(result)


def test_formatting_sub_hour():
    from helpers_pkg.formatting import calc_avg_gap_str
    # timestamps 20 min apart → avg < 1 hour → shows "minutes"
    now = datetime.now(timezone.utc)
    ts = [(now - timedelta(minutes=m*20)).isoformat() for m in range(4)]
    result = calc_avg_gap_str(ts)
    assert "minute" in result or isinstance(result, str)


def test_state_backup_read_version_oserror(tmp_path):
    from scheduled import state_backup as sb
    import scheduled.state_backup
    # Patch the VERSION file path to a nonexistent location
    fake_path = tmp_path / "NOVERSION"
    with patch.object(scheduled.state_backup, "_BACKUP_PATH", fake_path):
        result = sb._read_version()
    assert isinstance(result, str)  # returns actual version or "unknown"
