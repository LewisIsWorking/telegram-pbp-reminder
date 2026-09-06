"""Has this actually happened lately? Nothing was asking.

⛔⛔ 2026-09-06. ``last_diagnostic`` and ``last_pin_digest`` both read
2026-08-27 - **ten days** - while every hourly run reported the bot
healthy. Green runs, green suite, two features simply not happening.

Everything else in ``preflight`` asks whether the MACHINERY works: can
state be pushed, is the schedule being delivered, can a message still be
deleted. None of it asked the question a human asks first, and Lewis did
ask it: *"it sounds like the bot has issues it's not handling."*

⭐ The check reads the ``last_*`` markers the features already maintain,
so there is nothing new to keep in sync. A marker is the feature's own
record of having run; if it is old, the feature is not running.
"""

from datetime import datetime, timezone

import pytest

from preflight.stale_features import CADENCES, overdue, summarise

NOW = datetime(2026, 9, 6, 14, 0, tzinfo=timezone.utc)


def _state(**markers):
    return {"last_diagnostic": "2026-09-06", "last_pin_digest": "2026-09-06",
            **markers}


class TestTheRealTenDaySilence:
    def test_the_actual_markers_are_reported_overdue(self):
        """⭐⭐ The exact state that went unnoticed for ten days."""
        rows = overdue(_state(last_diagnostic="2026-08-27",
                              last_pin_digest="2026-08-27"), NOW)
        assert [r[0] for r in rows] == ["daily diagnostic", "pin digest"]
        assert all(r[1] == 10 for r in rows)

    def test_a_healthy_bot_reports_nothing_overdue(self):
        """⭐ Can-fail counterpart. Without this the check could return
        everything always and the test above would still pass."""
        assert overdue(_state(), NOW) == []

    def test_the_summary_names_the_feature_and_the_gap(self):
        text = summarise(_state(last_diagnostic="2026-08-27"), NOW)
        assert "daily diagnostic" in text and "10d ago" in text

    def test_one_day_late_is_not_worth_saying(self):
        """⚠️ Tolerance is a cadence plus slack. A nag that fires on an
        ordinary Tuesday gets ignored, and then so does the real one."""
        assert overdue(_state(last_diagnostic="2026-09-05"), NOW) == []


class TestTheAwkwardCases:
    def test_a_marker_that_was_NEVER_set_is_reported_not_skipped(self):
        """⛔ "no record of ever running" is the strongest version of the
        thing being looked for. Skipping it would hide the worst case."""
        rows = overdue(_state(last_diagnostic=None), NOW)
        assert ("daily diagnostic", None, 2) in rows

    @pytest.mark.parametrize("bad", ["", "soon", 20260827, {"d": 1}])
    def test_an_unreadable_marker_is_reported_too(self, bad):
        assert any(r[0] == "daily diagnostic"
                   for r in overdue(_state(last_diagnostic=bad), NOW))

    def test_a_feature_absent_from_state_is_not_invented(self):
        """A marker the deployment has never had is not a fault; it is a
        feature that was never enabled."""
        assert overdue({"last_diagnostic": "2026-09-06"}, NOW) == []

    def test_never_run_sorts_above_merely_late(self):
        rows = overdue(_state(last_diagnostic=None,
                              last_pin_digest="2026-08-27"), NOW)
        assert rows[0][0] == "daily diagnostic"

    def test_an_empty_state_is_called_suspicious_not_healthy(self):
        """⛔ A summary that goes quiet when its input vanishes is a
        check that fails silently. Say the shape looks wrong instead."""
        assert "suspicious" in summarise({}, NOW)


class TestAgainstTheRealState:
    """⚠️ Runs against the repository's real live.json. A check that only
    ever meets fixtures passes forever while its actual input drifts."""

    def _live(self):
        import json
        import pathlib
        path = (pathlib.Path(__file__).resolve().parent.parent
                / "data" / "state" / "live.json")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_the_markers_this_check_names_still_exist(self):
        """⛔ Every key here is a string this module made up. If the state
        schema renames one, this check silently stops watching it and
        reports 'nothing overdue' for a feature it can no longer see."""
        live = self._live()
        present = [k for k in CADENCES if k in live]
        assert len(present) >= 8, (
            f"only {len(present)} of {len(CADENCES)} tracked markers exist in "
            f"live.json: missing {sorted(set(CADENCES) - set(live))}")
