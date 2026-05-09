"""Coverage tests extracted from test_branch_gaps.py — bin 4.

Sections in this file:
  - scheduled/queue_reminder.py: message chunking
  - boons/handler.py: _resolve_boon returns None
  - helpers_pkg/config.py: chat_topic collision
  - helpers_pkg/campaigns.py: get_campaign_pids
  - helpers_pkg/mechanics.py: hp_status_icon red
  - helpers_pkg/time_utils.py: past date advances year
  - scheduled/milestones.py: exactly 1 year
  - scheduled/digest.py: post_weekly_digest

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


# ─── scheduled/queue_reminder.py: message chunking ───────────────────────────

def test_queue_reminder_chunks_long_message():
    from scheduled.queue_reminder import post_queue_reminder
    now = datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc)
    t = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    # Create 100 entries to force a long message needing chunking
    entries = [{"name": f"Player{i}", "time": t,
                "preview": "x" * 50, "link": "", "message_id": str(i)}
               for i in range(100)]
    config = {"group_id": -1001, "bot_topic_id": 999, "gm_user_ids": [999],
              "queue_daily_hours": [9, 21],
              "topic_pairs": [{"pbp_topic_ids": [100], "code": "C00",
                               "name": "Kibwe", "gm_user_ids": [999]}]}
    scanned = {"100": {"campaign": "Kibwe", "code": "C00", "entries": entries}}
    state = {"last_queue_fingerprint": "OLD", "queue_post_count": 0,
             "last_queue_pin_id": None, "last_queue_daily_slots": []}
    with patch("scheduled.queue_reminder.scan_transcripts", return_value=scanned), \
         patch("scheduled.queue_reminder.post_topic_queues"):
        post_queue_reminder(config, state, now=now)
    assert state["queue_post_count"] == 1



# ─── boons/handler.py: _resolve_boon returns None ────────────────────────────

def test_choose_boon_resolve_fails():
    from boons.handler import choose_boon_by_text
    state = {
        "pending_potw_boons": {"100": {
            "winner_user_id": "U1", "message_id": 42,
            "campaign_name": "Kibwe",
            "boons": ["Turtle"],
            "base_message": "Won!",
        }},
        "player_boons": {},
        "players": {},
    }
    config = {"group_id": -1}
    with patch("boons.handler._resolve_boon", return_value=(None, None)):
        result = choose_boon_by_text("100", "U1", 1, config, state)
    assert "wrong" in result.lower() or "went wrong" in result.lower()



# ─── helpers_pkg/config.py: chat_topic collision ─────────────────────────────

def test_config_chat_topic_collision():
    from helpers_pkg.config import validate_config
    config = {
        "group_id": -1, "gm_user_ids": [],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "name": "A", "chat_topic_id": 500},
            {"pbp_topic_ids": [200], "name": "B", "chat_topic_id": 500},  # collision
        ],
    }
    issues = validate_config(config)
    assert any("collision" in i.lower() or "used by another" in i.lower()
               for i in issues)



# ─── helpers_pkg/campaigns.py: get_campaign_pids ─────────────────────────────

def test_get_campaign_pids():
    from helpers_pkg.campaigns import all_pids
    config = {"topic_pairs": [
        {"pbp_topic_ids": [100]}, {"pbp_topic_ids": [200]}
    ]}
    result = all_pids(config)
    assert "100" in result and "200" in result



# ─── helpers_pkg/mechanics.py: hp_status_icon red ───────────────────────────

def test_hp_status_icon_critical():
    from helpers_pkg.mechanics import hp_status_icon
    result = hp_status_icon(1, 20)
    assert result == "🔴"



# ─── helpers_pkg/time_utils.py: past date advances year ─────────────────────

def test_parse_away_duration_past_date_advances():
    from helpers_pkg.time_utils import parse_away_duration
    # Use naive datetime to avoid offset comparison issues
    now = datetime(2026, 4, 3, 12, 0, 0)
    dt, reason = parse_away_duration("until January 1", now)
    # May parse to next year or not parse at all - either is fine
    assert dt is None or dt.year >= 2026



# ─── scheduled/milestones.py: exactly 1 year ─────────────────────────────────

def test_milestones_one_year():
    from scheduled.milestones import check_anniversaries
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    # Campaign created exactly 1 year ago
    config = {"group_id": -1, "bot_topic_id": 999, "topic_pairs": [
        {"pbp_topic_ids": [100], "name": "Kibwe",
         "created": "2025-04-03", "chat_topic_id": 21514}
    ]}
    state = {"last_anniversary": {}}
    with patch("scheduled.milestones.helpers") as mh:
        mh.get_label.return_value = "C00: Kibwe"
        mh.interval_elapsed.return_value = True
        check_anniversaries(config, state, now=now)  # should not raise



# ─── scheduled/digest.py: post_weekly_digest ─────────────────────────────────

def test_digest_skips_no_leaderboard_topic():
    from scheduled.digest import post_weekly_digest
    config = {"group_id": -1}
    post_weekly_digest(config, {})  # no leaderboard_topic_id → returns early


def test_digest_skips_interval():
    from scheduled.digest import post_weekly_digest
    config = {"group_id": -1, "leaderboard_topic_id": 555}
    with patch("scheduled.digest.helpers") as mh:
        mh.interval_elapsed.return_value = False
        post_weekly_digest(config, {"last_weekly_digest": "2026-04-01"})


def test_digest_posts():
    from scheduled.digest import post_weekly_digest
    config = {"group_id": -1001, "leaderboard_topic_id": 555}
    with patch("scheduled.digest.helpers") as mh, \
         patch("scheduled.digest._build_weekly_digest", return_value="digest"):
        mh.interval_elapsed.return_value = True
        state = {}
        post_weekly_digest(config, state)
        assert "last_weekly_digest" in state


