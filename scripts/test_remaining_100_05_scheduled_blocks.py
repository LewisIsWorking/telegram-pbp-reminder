"""Tests extracted from test_remaining_100.py — bin 5.

Sections in this file:
  - scheduled blocks — all verified to hit their continue/return lines
"""
"""
Definitive final coverage push — verified state for every remaining gap.
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


def _ctx(**kw):
    base = {"user_id": "GM1", "user_name": "Lewis", "gm_ids": {"GM1"},
            "pid": "100", "group_id": -1, "thread_id": 999,
            "state": {}, "config": {}, "campaign_name": "Kibwe",
            "now_iso": "2026-04-03T12:00:00+00:00",
            "msg_time_iso": "2026-04-03T12:00:00+00:00",
            "parsed": {"raw_text": "", "text": ""},
            "maps": MagicMock(), "reply_topic": 999}
    base.update(kw)
    base["cmd_word"] = base["text"].split()[0] if base["text"] else base.get("cmd_word", "")
    return base



# ── scheduled blocks — all verified to hit their continue/return lines ────────
def test_alerts_excl():
    from scheduled.alerts import check_and_alert
    config = {"group_id": -1, "gm_user_ids": [], "bot_topic_id": 999,
              "topic_pairs": [{"pbp_topic_ids": [100], "name": "K", "chat_topic_id": 21514}]}
    with patch("helpers.iter_campaigns", return_value=[("100", "C00", "K", {})]), \
         patch("helpers.is_excluded", return_value=True):
        check_and_alert(config, {})


def test_combat_ping_excl():
    from scheduled.combat_ping import check_combat_turns
    config = {"group_id": -1, "bot_topic_id": 999, "gm_user_ids": [],
              "topic_pairs": [{"pbp_topic_ids": [100], "name": "K", "chat_topic_id": 21514}]}
    with patch("scheduled.combat_ping.helpers") as mh:
        mh.iter_campaigns.return_value = [("100", "C00", "K", {})]
        mh.is_excluded.return_value = True
        check_combat_turns(config, {"combat": {}})


def test_maintenance_excl():
    from scheduled.maintenance import check_recruitment_needs
    config = {"group_id": -1, "gm_user_ids": [],
              "topic_pairs": [{"pbp_topic_ids": [100], "name": "K", "chat_topic_id": 21514}]}
    with patch("helpers.iter_campaigns", return_value=[("100", "C00", "K", {})]), \
         patch("helpers.is_excluded", return_value=True):
        check_recruitment_needs(config, {"last_recruitment_check": {}})


def test_milestones_skip():
    from scheduled.milestones import check_streak_milestones
    config = {"group_id": -1, "bot_topic_id": 999, "gm_user_ids": [],
              "topic_pairs": [{"pbp_topic_ids": [100], "name": "K", "chat_topic_id": 21514}]}
    with patch("scheduled.milestones.helpers") as mh:
        mh.iter_campaigns.return_value = [("100", "C00", "K", {})]
        mh.is_excluded.return_value = False
        mh.feature_enabled.return_value = True
        mh.get_topic_timestamps.return_value = {}
        mh.gm_ids_for_campaign.return_value = set()
        mh.interval_elapsed.return_value = False
        check_streak_milestones(config, {})


def test_smart_alerts_off():
    from scheduled.smart_alerts import check_pace_drop
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    maps = MagicMock()
    maps.to_chat = {"100": 21514}
    with patch("scheduled.smart_alerts.helpers") as mh:
        mh.interval_elapsed.return_value = True
        mh.feature_enabled.return_value = False
        check_pace_drop({"group_id": -1, "topic_pairs": []}, {}, now=now, maps=maps)


def test_reports_no_ts():
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
        mh.get_topic_timestamps.return_value = {}
        post_pace_report(config, {"last_pace": {}}, now=now)


def test_session_poll_empty_roster():
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


def test_potw_links(tmp_path):
    from scheduled.potw import _find_player_post_links
    week_ago = datetime(2026, 3, 27, tzinfo=timezone.utc)
    (tmp_path / "Kibwe").mkdir()
    (tmp_path / "Kibwe" / "2026-04.md").write_text(
        "**Alice** (2026-04-01 10:00:00) msg#1:\nHi!\n", encoding="utf-8")
    with patch("scheduled.potw._LOGS_DIR", tmp_path):
        links = _find_player_post_links("Kibwe", "Alice", "100", week_ago)
    assert isinstance(links, list)


def test_diagnostic_no_info():
    from scheduled.diagnostic_analysis import _analyse_logs
    assert _analyse_logs(["just a log line"])["events"] == []


def test_helpers_time_utils_weeks():
    from helpers_pkg.time_utils import parse_away_duration
    dt, reason = parse_away_duration("2 weeks holiday", datetime(2026, 4, 3, 12, 0, 0))
    assert dt is not None and (dt - datetime(2026, 4, 3, 12, 0, 0)).days == 14
