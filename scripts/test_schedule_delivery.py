"""The scheduler line, and the two numbers that made it necessary.

2026-08-31. GitHub delivered 173 of 372 scheduled runs over nine days and
nothing said so. The daily diagnostic ran throughout and reported
"✅ All clear across N hourly runs" the whole time, because:

* it asked the API for `per_page=25` while a healthy day is **48** runs,
  so the instrument's maximum reading was half the healthy value; and
* it printed that number with **no denominator**, so 24 and 4 both read
  as ordinary.

⛔ A count whose instrument tops out below the healthy value, reported
without its basis, cannot fail. It reads as normal at every level of
brokenness. Both halves are now pinned here.

The other half of the diagnosis lives in
``test_schedule_avoids_the_contended_minutes``.
"""

import os
import re
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(__file__))

from scheduled.schedule_delivery import (HEALTHY_DELIVERY,
                                         SCHEDULED_RUNS_PER_DAY,
                                         delivered_in_window, delivery_line,
                                         expected_in_window, report_line)

_NOW = datetime(2026, 8, 31, 12, 0, tzinfo=timezone.utc)


def _run(hours_ago: float, event: str = "schedule") -> dict:
    return {"id": 1000 + int(hours_ago * 10), "event": event,
            "created_at": (_NOW - timedelta(hours=hours_ago)).isoformat()
                          .replace("+00:00", "Z")}


class TestTheExpectedValueIsNotFiction:
    """⭐⭐ A hardcoded denominator that drifts is worse than none."""

    def test_it_matches_the_crons_in_the_workflow(self):
        # If somebody drops the :43 queue pass, the expected value must
        # follow or the diagnostic reports a 50% outage forever.
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        wf = os.path.join(root, ".github", "workflows", "pbp-reminder.yml")
        with open(wf, encoding="utf-8") as handle:
            crons = re.findall(r"^\s*- cron: '([^']+)'", handle.read(),
                               re.MULTILINE)
        hourly = [c for c in crons if c.split()[1:] == ["*", "*", "*", "*"]]
        assert len(hourly) * 24 == SCHEDULED_RUNS_PER_DAY, (
            f"the workflow has {len(hourly)} hourly crons = "
            f"{len(hourly) * 24}/day, but SCHEDULED_RUNS_PER_DAY is "
            f"{SCHEDULED_RUNS_PER_DAY}")

    def test_the_page_size_can_hold_a_healthy_day(self):
        # ⛔ The original bug, as a guard. per_page=25 could not represent
        # 48, so the measurement was capped below health.
        from scheduled.diagnostic import _RUNS_PAGE
        assert _RUNS_PAGE > SCHEDULED_RUNS_PER_DAY, (
            f"per_page={_RUNS_PAGE} cannot represent a healthy day of "
            f"{SCHEDULED_RUNS_PER_DAY} runs, so the count truncates")


class TestCounting:
    def test_it_counts_runs_inside_the_window(self):
        runs = [_run(1), _run(5), _run(23)]
        assert delivered_in_window(runs, _NOW) == 3

    def test_it_drops_runs_outside_it(self):
        assert delivered_in_window([_run(25), _run(48)], _NOW) == 0

    def test_push_runs_do_not_count(self):
        # ⭐ A busy day of merges must not disguise a dead cron. On
        # 2026-08-30 there were 12 scheduled runs and 12 push/PR runs;
        # counting all 24 would have read as half-healthy, not quarter.
        runs = [_run(1), _run(2, "push"), _run(3, "pull_request")]
        assert delivered_in_window(runs, _NOW) == 1

    def test_an_unparseable_timestamp_is_skipped_not_fatal(self):
        runs = [_run(1), {"event": "schedule", "created_at": "not-a-date"}]
        assert delivered_in_window(runs, _NOW) == 1

    def test_the_window_scales(self):
        assert expected_in_window(24) == SCHEDULED_RUNS_PER_DAY
        assert expected_in_window(12) == SCHEDULED_RUNS_PER_DAY // 2


class TestTheLineCarriesItsBasis:
    def test_a_healthy_day_names_both_numbers(self):
        line = delivery_line(46, 48)
        assert "46 of 48" in line and "96%" in line
        assert line.startswith("🕒")

    def test_a_bad_day_is_flagged_and_explains_the_symptom(self):
        # ⭐⭐ The real 2026-08-28 reading. It must not read as ordinary,
        # and it must point away from the state-commit step, which is
        # where the preflight alert points and where the fault is not.
        line = delivery_line(4, 48)
        assert line.startswith("⚠️")
        assert "4 of 48" in line and "8%" in line
        assert "state-commit step is not the fault" in line

    def test_the_threshold_is_the_one_that_is_documented(self):
        # can-fail counterpart: pins WHERE the icon flips, so a later
        # edit cannot quietly widen "healthy" to cover the outage.
        expected = SCHEDULED_RUNS_PER_DAY
        just_under = int(expected * HEALTHY_DELIVERY) - 1
        assert delivery_line(just_under, expected).startswith("⚠️")
        assert delivery_line(expected, expected).startswith("🕒")

    def test_a_truncated_reading_says_so(self):
        # ⛔ Never present a capped count as a measurement. This is the
        # exact shape of the per_page=25 bug.
        line = report_line([_run(i * 0.1) for i in range(50)], _NOW,
                           page_size=50)
        assert "at least" in line and "page limit" in line

    def test_an_uncapped_reading_does_not(self):
        line = report_line([_run(i * 0.1) for i in range(10)], _NOW,
                           page_size=100)
        assert "at least" not in line

    def test_no_schedule_configured_says_that_rather_than_zero_percent(self):
        assert "no schedule" in delivery_line(0, 0)
