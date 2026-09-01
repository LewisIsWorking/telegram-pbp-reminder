"""The outside trigger only fires when the bot has actually gone quiet.

2026-09-01. The watchdog inside GitHub cannot save the bot from GitHub's
own scheduler, because it is scheduled too. Measured after moving the
crons off the contended minutes, which was supposed to fix delivery:

```
2026-08-30   18 / 48   38%
2026-08-31    3 / 48    6%
2026-09-01    8 / 48   17%
```

⛔⛔ The decisive rule here, and it is the whole of the 2026-08-31
outage: **a `skipped` run does not count as the bot running.** Every run
that day was skipped, nothing was red, and any counter that asked "did a
run happen" said yes.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "tools"))

from external_heartbeat import QUIET_AFTER, last_real_run, should_dispatch

_NOW = datetime(2026, 9, 1, 20, 0, tzinfo=timezone.utc)


def _run(minutes_ago, conclusion="success"):
    return {"conclusion": conclusion,
            "created_at": (_NOW - timedelta(minutes=minutes_ago))
                          .isoformat().replace("+00:00", "Z")}


class TestItStaysQuietWhenTheBotIsRunning:
    def test_a_recent_run_needs_no_help(self):
        assert not should_dispatch([_run(10)], _NOW)

    def test_the_grace_window_is_where_it_is_documented(self):
        mins = QUIET_AFTER.total_seconds() / 60
        assert not should_dispatch([_run(mins - 1)], _NOW)
        assert should_dispatch([_run(mins + 1)], _NOW)

    def test_the_window_is_pinned_in_absolute_terms(self):
        # ⛔ The test above reads QUIET_AFTER, so it moves WITH the
        # constant and cannot detect the constant changing. A mutation
        # widening it to 10 hours survived until this existed.
        #
        # It must be longer than the 30-minute run interval, so ordinary
        # jitter costs nothing, and short enough that the bot cannot sit
        # dead for long. The 48h message wall leaves 12h of headroom, so
        # anything measured in hours here is far too slack.
        assert timedelta(minutes=30) < QUIET_AFTER <= timedelta(hours=2), (
            f"QUIET_AFTER is {QUIET_AFTER}; below 30m it fights normal "
            f"scheduling, above 2h the bot can be dead for most of the "
            f"headroom before the 48h message wall.")

    def test_it_uses_the_most_recent_run_not_the_first(self):
        assert not should_dispatch([_run(500), _run(5)], _NOW)


class TestASkippedRunIsNotARun:
    """⛔⛔ The 2026-08-31 outage in one assertion."""

    def test_skipped_runs_do_not_count(self):
        assert should_dispatch([_run(5, "skipped"), _run(9, "skipped")], _NOW)

    def test_a_failed_run_DOES_count(self):
        # ⭐ A failure means the bot ran and something went wrong, which
        # is a different problem and not one more runs will fix. Firing
        # here would just multiply a broken run.
        assert not should_dispatch([_run(5, "failure")], _NOW)

    def test_cancelled_and_in_progress_do_not_count(self):
        assert should_dispatch([_run(5, "cancelled"), _run(6, None)], _NOW)

    def test_a_real_run_behind_skipped_ones_still_counts(self):
        # can-fail counterpart: proves the filter picks the newest
        # REAL run rather than simply ignoring the list.
        assert not should_dispatch([_run(2, "skipped"), _run(20)], _NOW)


class TestWhenItCannotTell:
    def test_no_history_at_all_dispatches(self):
        # ⚠️ Deliberately acts on "cannot tell", which is the opposite of
        # the posting gate's rule, and for a stated reason: a redundant
        # run costs one cheap job, a missed one can orphan a message
        # permanently.
        assert should_dispatch([], _NOW)

    def test_unparseable_timestamps_are_ignored_not_trusted(self):
        assert should_dispatch([{"conclusion": "success",
                                 "created_at": "not-a-date"}], _NOW)

    def test_last_real_run_returns_none_when_nothing_qualifies(self):
        assert last_real_run([_run(1, "skipped")]) is None
