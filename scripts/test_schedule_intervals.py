"""Interval lines report the campaigns that actually exist (2026-08-13).

The bug this prevents
---------------------
The posted schedule read:

    • Roster summary — due now
    • Pace report — due now

Both had read "due now" for weeks, and both were technically true — but
the reason was not the one a reader would take from it.

``last_roster`` and ``last_pace`` are ``{pid: iso}``, and the line was
computed from the *earliest* value across every key. State accumulates
campaign ids indefinitely; ``1242`` had been removed from ``config`` and
its 2026-07-06 timestamp was still sitting there. Its job iterates
``config``, never reaches it, and so never restamps it — so the earliest
value could only ever move further into the past, and the line was
pinned to "due now" for good. A permanently-stuck status line is worse
than no line: it reads as information and carries none.

Filtering to configured campaigns fixes the orphan. The count is the
other half — "due now" alone cannot distinguish one stalled campaign
from all nine, and one stalled campaign is the common case (``107151``
has no players recorded, so its roster job skips without stamping).
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

_NOW = datetime(2026, 8, 13, 6, 56, tzinfo=timezone.utc)

# Two live campaigns; build_topic_maps keys on the FIRST pbp id, so the
# canonical pids here are "100" and "300".
_CFG = {"group_id": -100, "topic_pairs": [
    {"name": "Alpha", "code": "C01", "chat_topic_id": 11,
     "pbp_topic_ids": [100, 200]},
    {"name": "Beta", "code": "C02", "chat_topic_id": 22,
     "pbp_topic_ids": [300]},
]}
_NO_CAMPAIGNS = {"group_id": -100, "topic_pairs": []}


def _ago(days: float) -> str:
    return (_NOW - timedelta(days=days)).isoformat()


def _line(config, state, needle):
    from scheduled.schedule_intervals import interval_lines
    return next(l for l in interval_lines(config, state, _NOW) if needle in l)


class TestOrphanCampaignsAreIgnored:
    def test_a_removed_campaign_does_not_pin_the_line(self):
        """The reported bug: pid 1242 is not in config and never will be."""
        state = {"last_roster": {"100": _ago(0.5), "300": _ago(0.5),
                                 "1242": _ago(60)}}
        assert "due now" not in _line(_CFG, state, "Roster summary")

    def test_without_the_orphan_the_same_state_is_not_due(self):
        """Control: proves the orphan was the only thing making it due."""
        state = {"last_roster": {"100": _ago(0.5), "300": _ago(0.5)}}
        assert "due now" not in _line(_CFG, state, "Roster summary")

    def test_a_live_campaign_still_makes_it_due(self):
        """The filter must not swallow a real overdue campaign."""
        state = {"last_roster": {"100": _ago(60), "300": _ago(0.5)}}
        assert "due now" in _line(_CFG, state, "Roster summary")

    def test_no_configured_campaigns_means_no_filtering(self):
        """Empty is ambiguous — an unreadable config must not blank the line.

        Filtering on an empty set would drop every timestamp and render
        every per-campaign job permanently "due now", which is the bug
        this filter exists to remove.
        """
        state = {"last_roster": {"100": _ago(0.5)}}
        assert "due now" not in _line(_NO_CAMPAIGNS, state, "Roster summary")


class TestDueCount:
    def test_reports_how_many_campaigns_are_due(self):
        state = {"last_roster": {"100": _ago(60), "300": _ago(0.5)}}
        assert "(1 of 2 campaigns)" in _line(_CFG, state, "Roster summary")

    def test_counts_all_of_them(self):
        state = {"last_roster": {"100": _ago(60), "300": _ago(60)}}
        assert "(2 of 2 campaigns)" in _line(_CFG, state, "Roster summary")

    def test_orphans_are_excluded_from_the_total_too(self):
        """Not just from 'due' — a removed campaign is not one of N either.

        Three entries, one of them an orphan, one live one overdue: the
        line must read 1 of 2, never 1 of 3.
        """
        state = {"last_roster": {"100": _ago(60), "300": _ago(0.5),
                                 "1242": _ago(90)}}
        line = _line(_CFG, state, "Roster summary")
        assert "(1 of 2 campaigns)" in line, line

    def test_no_count_when_nothing_is_due(self):
        state = {"last_roster": {"100": _ago(0.5), "300": _ago(0.5)}}
        assert "campaigns)" not in _line(_CFG, state, "Roster summary")

    def test_single_value_jobs_get_no_count(self):
        """last_leaderboard is one timestamp, not a per-campaign dict."""
        state = {"last_leaderboard": _ago(10)}
        line = _line(_CFG, state, "Leaderboard")
        assert "due now" in line and "campaigns" not in line


class TestNewlyListedJobs:
    """The six added on 2026-08-13 must render, not just exist in the table."""

    def test_all_six_appear_in_the_lines(self):
        from scheduled.schedule_intervals import interval_lines
        text = "\n".join(interval_lines(_CFG, {}, _NOW))
        for label in ("Recruitment check", "Weekly digest", "Campaign table",
                      "Pace-drop alerts", "Daily tip", "State backup"):
            assert label in text, f"{label} is not rendered"

    def test_daily_tip_uses_its_22_hour_gate(self):
        """scheduled/tips.py gates on hours_since < 22, not a whole day."""
        state = {"last_daily_tip": _ago(23 / 24)}
        assert "due now" in _line(_CFG, state, "Daily tip")

    def test_daily_tip_is_not_due_before_22_hours(self):
        state = {"last_daily_tip": _ago(20 / 24)}
        assert "due now" not in _line(_CFG, state, "Daily tip")


class TestFormatting:
    def test_sorted_soonest_first(self):
        from scheduled.schedule_intervals import interval_lines
        state = {"last_leaderboard": _ago(2.9), "last_daily_tip": _ago(0.1)}
        lines = interval_lines(_CFG, state, _NOW)
        assert "due now" in lines[0], "unrun jobs sort to the top"

    def test_beyond_48_hours_reads_in_days(self):
        state = {"last_weekly_digest": _ago(1)}   # 7-day gate, 6 to go
        assert "in 6d" in _line(_CFG, state, "Weekly digest")

    def test_unparseable_timestamp_reads_due_now(self):
        state = {"last_leaderboard": "not a date"}
        assert "due now" in _line(_CFG, state, "Leaderboard")
