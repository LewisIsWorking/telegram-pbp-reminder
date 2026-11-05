"""The ETA to clear the GM queue, on the queue post under the rate lines.

Lewis, 2026-11-05: "It would be nice based on GM posting pace if we sent
another message that would say ETA of the queue being cleared."

The pace is replies cleared per day (``state["queue_history"]``) over the
seven complete London days before today. Every test pins ``now``.
"""

from datetime import datetime, timedelta, timezone

from scheduled import gm_post_rate as rate
from scheduled import queue_eta as eta

# 12:00 UTC on a GMT day (after the clocks went back) is 12:00 in London.
NOW = datetime(2026, 11, 5, 12, 0, tzinfo=timezone.utc)


def _ago(hours):
    return (NOW - timedelta(hours=hours)).isoformat()


def _history(per_day, days=7):
    """``per_day`` clears on each of the ``days`` complete days before today."""
    return {"queue_history": {"25059": [
        _ago(24 * d) for d in range(1, days + 1) for _ in range(per_day)]}}


class TestPace:
    def test_average_over_seven_complete_days(self):
        assert eta.clears_per_day(_history(3), NOW) == 3.0

    def test_today_and_older_than_a_week_are_left_out(self):
        state = _history(2)
        state["queue_history"]["25059"] += [_ago(1)] * 9 + [_ago(24 * 9)] * 9
        assert eta.clears_per_day(state, NOW) == 2.0

    def test_every_campaign_counts(self):
        state = {"queue_history": {"1": [_ago(24)] * 7, "2": [_ago(48)] * 7}}
        assert eta.clears_per_day(state, NOW) == 2.0

    def test_the_boundary_is_london_midnight(self):
        """In BST, 23:30 UTC is 00:30 the next London day."""
        now = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)
        today_in_london = datetime(2026, 10, 19, 23, 30, tzinfo=timezone.utc)
        state = {"queue_history": {"1": [today_in_london.isoformat()]}}
        assert eta.clears_per_day(state, now) == 0.0

    def test_unreadable_and_naive_stamps(self):
        naive = (NOW - timedelta(hours=24)).replace(tzinfo=None).isoformat()
        state = {"queue_history": {"1": ["junk", naive]}}
        assert eta.clears_per_day(state, NOW) == 1 / 7


class TestEtaLine:
    def test_days(self):
        state = _history(11)
        assert eta.eta_line(state, 15, NOW) == (
            "⏱ ETA to clear: ~1.4 days (15 unreplied, ~11 cleared/day)")

    def test_hours_under_a_day(self):
        assert eta.eta_line(_history(12), 3, NOW) == (
            "⏱ ETA to clear: ~6 hours (3 unreplied, ~12 cleared/day)")

    def test_one_hour_is_singular_and_never_zero(self):
        assert "~1 hour (" in eta.eta_line(_history(100), 1, NOW)

    def test_slow_pace_keeps_a_decimal(self):
        state = {"queue_history": {"1": [_ago(24 * d) for d in (1, 2, 3)]}}
        line = eta.eta_line(state, 6, NOW)
        assert line == "⏱ ETA to clear: ~14.0 days (6 unreplied, ~0.4 cleared/day)"

    def test_no_recent_clears(self):
        assert eta.eta_line({}, 4, NOW) == (
            "⏱ ETA to clear: none, no clears in the last 7 days (4 unreplied)")

    def test_empty_queue_has_no_line(self):
        assert eta.eta_line(_history(5), 0, NOW) is None


class TestOnTheRateLines:
    def test_eta_goes_last(self):
        lines = rate.rate_lines({"gm_user_ids": [1]}, _history(10), 5, NOW)
        assert lines[-1].startswith("⏱ ETA to clear: ~12 hours"), lines

    def test_no_eta_when_the_queue_is_empty(self):
        lines = rate.rate_lines({"gm_user_ids": [1]}, _history(10), 0, NOW)
        assert not any("ETA" in line for line in lines), lines
