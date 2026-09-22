"""A campaign with nothing to report still counts as checked (2026-09-22).

The roster summary skipped a campaign with no players, and the pace
report one with no posts, without stamping ``last_roster`` / ``last_pace``.
The diagnostic reports each per-campaign job by its OLDEST campaign, so
one quiet campaign (Theria, frozen at 2026-09-08 and 2026-09-01) made it
say "Roster summary: last 14d ago" and "Pace report: last 21d ago" every
day while every other campaign was current.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

from scheduled.reports import post_pace_report, post_roster_summary

NOW = datetime(2026, 9, 22, 12, tzinfo=timezone.utc)
CFG = {"group_id": -100, "bot_topic_id": 999}


def _maps():
    return MagicMock(to_chat={"107151": 1}, to_name={"107151": "Theria"})


@patch("scheduled.reports.tg")
@patch("scheduled.reports.helpers")
def test_roster_stamps_a_campaign_with_no_players(helpers, tg):
    helpers.feature_enabled.return_value = True
    helpers.interval_elapsed.return_value = True
    helpers.players_by_campaign.return_value = {}
    state = {"last_roster": {"107151": "2026-09-08T00:15:00+00:00"}, "message_counts": {}}
    post_roster_summary(CFG, state, now=NOW, maps=_maps())
    assert state["last_roster"]["107151"] == NOW.isoformat()
    tg.send_message.assert_not_called()


@patch("scheduled.reports.tg")
@patch("scheduled.reports.helpers")
def test_pace_stamps_a_campaign_with_no_posts(helpers, tg):
    helpers.feature_enabled.return_value = True
    helpers.interval_elapsed.return_value = True
    helpers.get_topic_timestamps.return_value = []
    state = {"last_pace": {"107151": "2026-09-01T16:33:00+00:00"}}
    post_pace_report(CFG, state, now=NOW, maps=_maps())
    assert state["last_pace"]["107151"] == NOW.isoformat()
    tg.send_message.assert_not_called()


@patch("scheduled.reports.tg")
@patch("scheduled.reports.helpers")
def test_a_campaign_whose_interval_has_not_elapsed_is_left_alone(helpers, tg):
    """Can-fail counterpart: stamping must not happen before the check."""
    helpers.feature_enabled.return_value = True
    helpers.interval_elapsed.return_value = False
    old = "2026-09-21T00:00:00+00:00"
    state = {"last_roster": {"107151": old}, "last_pace": {"107151": old}}
    post_roster_summary(CFG, state, now=NOW, maps=_maps())
    post_pace_report(CFG, state, now=NOW, maps=_maps())
    assert state["last_roster"]["107151"] == old
    assert state["last_pace"]["107151"] == old
