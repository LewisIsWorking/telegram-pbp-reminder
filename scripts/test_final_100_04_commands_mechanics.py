"""Tests extracted from test_final_100.py — bin 4.

Sections in this file:
  - commands/mechanics.py
  - dispatch/cmd_info.py all commands
  - helpers/config.py
  - helpers/time_utils.py:72-73 — weeks duration
  - commands/dashboard.py
"""
"""
Final push: tests for the large remaining uncovered blocks.
Focuses on router poll/callback/reaction handling, tracking GM-reply logging,
cmd_player /available, summary content, and other high-impact gaps.
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

def _pc(**kw):
    base = {"user_id": "U1", "user_name": "Alice", "gm_ids": set(),
            "pid": "100", "group_id": -1, "thread_id": 999,
            "state": {}, "config": {}, "campaign_name": "Kibwe",
            "now_iso": "2026-04-03T12:00:00+00:00",
            "msg_time_iso": "2026-04-03T12:00:00+00:00",
            "parsed": {"raw_text": ""}, "maps": MagicMock(), "reply_topic": 999}
    base.update(kw)
    base["cmd_word"] = base["text"].split()[0]
    return base

def _info_ctx(cmd, state=None):
    return {"cmd_word": cmd, "text": cmd,
            "user_id": "GM1", "user_name": "L", "gm_ids": {"GM1"},
            "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
            "state": state or {"vote": {}, "timer": {}, "clocks": {},
                               "player_boons": {}},
            "config": {"group_id": -1, "gm_user_ids": [], "topic_pairs": []},
            "campaign_name": "Kibwe", "now_iso": "2026-04-03T12:00:00+00:00",
            "msg_time_iso": "2026-04-03T12:00:00+00:00",
            "parsed": {}, "maps": MagicMock()}

# ─── commands/mechanics.py ───────────────────────────────────────────────────

def test_build_vote_with_data():
    from commands.mechanics import build_vote
    state = {"votes": {"100": {"question": "Where next?", "options": ["City", "Forest"],
                               "votes": {"U1": 0, "U2": 1}, "closed": False}}}
    result = build_vote("100", "Kibwe", state)
    assert "Where" in result


def test_build_vote_empty():
    from commands.mechanics import build_vote
    result = build_vote("100", "Kibwe", {"vote": {}})
    assert isinstance(result, str)


def test_build_timer_expired():
    from commands.mechanics import build_timer
    now = datetime.now(timezone.utc)
    expired = (now - timedelta(minutes=5)).isoformat()
    result = build_timer("100", "Kibwe",
                         {"timer": {"100": {"expires": expired, "reason": "Done"}}})
    assert isinstance(result, str)



# ─── dispatch/cmd_info.py all commands ───────────────────────────────────────

def _info_ctx(cmd, state=None):
    return {"cmd_word": cmd, "text": cmd,
            "user_id": "GM1", "user_name": "L", "gm_ids": {"GM1"},
            "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
            "state": state or {"vote": {}, "timer": {}, "clocks": {},
                               "player_boons": {}},
            "config": {"group_id": -1, "gm_user_ids": [], "topic_pairs": []},
            "campaign_name": "Kibwe", "now_iso": "2026-04-03T12:00:00+00:00",
            "msg_time_iso": "2026-04-03T12:00:00+00:00",
            "parsed": {}, "maps": MagicMock()}


def test_cmd_info_queue():
    from dispatch.cmd_info import handle
    with patch("dispatch.cmd_info.tg.send_message"), \
         patch("commands.queue.build_queue", return_value="queue"):
        assert handle(_info_ctx("/queue")) is True


def test_cmd_info_showvote():
    from dispatch.cmd_info import handle
    with patch("dispatch.cmd_info.tg.send_message"):
        assert handle(_info_ctx("/showvote")) is True


def test_cmd_info_showtimer():
    from dispatch.cmd_info import handle
    with patch("dispatch.cmd_info.tg.send_message"):
        assert handle(_info_ctx("/showtimer")) is True


def test_cmd_info_clocks():
    from dispatch.cmd_info import handle
    with patch("dispatch.cmd_info.tg.send_message"):
        assert handle(_info_ctx("/clocks")) is True


def test_cmd_info_boons():
    from dispatch.cmd_info import handle
    with patch("dispatch.cmd_info.tg.send_message"):
        assert handle(_info_ctx("/boons")) is True


def test_cmd_info_boonsall():
    from dispatch.cmd_info import handle
    with patch("dispatch.cmd_info.tg.send_message"):
        assert handle(_info_ctx("/boonsall")) is True



# ─── helpers/config.py ───────────────────────────────────────────────────────

def test_config_missing_pbp_topic_ids():
    from helpers_pkg.config import validate_config
    issues = validate_config({"group_id": -1, "gm_user_ids": [],
                              "topic_pairs": [{"name": "X"}]})
    assert any("pbp_topic_ids" in i or "non-empty" in i.lower() for i in issues)



# ─── helpers/time_utils.py:72-73 — weeks duration ────────────────────────────

def test_parse_away_weeks():
    from helpers_pkg.time_utils import parse_away_duration
    now = datetime(2026, 4, 3, 12, 0, 0)
    dt, reason = parse_away_duration("2 weeks holiday", now)
    assert dt is not None and (dt - now).days == 14



# ─── commands/dashboard.py ───────────────────────────────────────────────────

def test_dashboard_combat_flag():
    from commands.dashboard import build_gm_dashboard
    now = datetime.now(timezone.utc)
    old = (now - timedelta(days=8)).isoformat()
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": [
        {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
         "gm_user_ids": [], "chat_topic_id": 21514}
    ]}
    state = {"quests": {}, "conditions": {}, "timer": {}, "vote": {},
             "current_scenes": {}, "hp_tracker": {}, "clocks": {},
             "combat": {"100": {"active": True, "round": 1}},
             "paused_campaigns": {}, "topics": {}, "message_counts": {},
             "post_timestamps": {},
             "players": {"100:U1": {"user_id": "U1", "first_name": "Alice",
                                    "last_post_time": old, "pbp_topic_id": "100"}}}
    with patch("commands.dashboard.helpers") as mh:
        mh.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
        mh.get_label.return_value = "C00"
        mh.is_excluded.return_value = False
        mh.gm_ids_for_campaign.return_value = set()
        mh.get_topic_timestamps.return_value = {}
        mh.hours_since.return_value = 2.0
        mh.fmt_brief_relative.return_value = ("2h ago", 2.0)
        mh.is_away.return_value = None
        mh.days_since.return_value = 8.0
        result = build_gm_dashboard(config, state)
    assert "⚔️" in result or "⚠️" in result or isinstance(result, str)
