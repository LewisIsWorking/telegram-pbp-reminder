"""A campaign can be left out of every campaign-wide post. Added 2026-09-21.

For the Tongs Browser test campaign (C99): players must not read
"Tongs Testing - 0 posts" beside their real tables, and a campaign with
nobody in it must not make the roster nudge fire.
"""
from datetime import datetime, timezone

from commands.roster import build_roster_overview
from helpers_pkg.listing import listed, listed_pairs, listed_pids
from scheduled import roster_nudge
from scheduled.community_roster_build import build_community_roster
from scheduled.digest import _build_weekly_digest
from scheduled.leaderboard_data import _gather_leaderboard_stats

NOW = datetime(2026, 9, 21, 12, 0, tzinfo=timezone.utc)
REAL = {"name": "Metal City", "code": "C09", "chat_topic_id": 2, "pbp_topic_ids": [1],
        "roster_target": 1}
TEST = {"name": "Tongs Testing", "code": "C99", "chat_topic_id": 75843,
        "pbp_topic_ids": [75843], "disabled_features": ["alerts", "listing"]}


def _config():
    return {"group_id": -100, "gm_user_ids": [999], "bot_topic_id": 300,
            "leaderboard_topic_id": 400, "topic_pairs": [REAL, TEST]}


def _state():
    return {"players": {"a": {"user_id": "1", "first_name": "Ryo", "pbp_topic_id": "1",
                              "last_post_time": NOW.isoformat()}},
            "topics": {}, "post_timestamps": {}, "message_counts": {}}


def test_the_switch_reads_disabled_features():
    assert listed(REAL) and not listed(TEST)
    assert listed_pairs(_config()) == [REAL]
    assert listed_pids(_config()) == {"1"}


def test_the_roster_overview_and_nudge_leave_the_test_campaign_out():
    assert "Tongs Testing" not in build_roster_overview(_config(), _state())
    assert "C99" not in roster_nudge._roster_snapshot(_config(), _state())
    # The real campaign is at its target, and the empty test one no longer counts.
    assert roster_nudge._needs_nudge(_config(), _state()) is False


def test_the_digest_leaderboard_and_community_roster_leave_it_out():
    assert "Tongs Testing" not in _build_weekly_digest(_config(), _state(), NOW)
    assert "Tongs Testing" not in build_community_roster(_config(), _state(), NOW)
    campaigns, _, _ = _gather_leaderboard_stats(_config(), _state(), NOW)
    assert [each["name"] for each in campaigns] == ["Metal City"]
