"""The outside trigger fires only when the bot has actually gone quiet.

2026-09-01. The watchdog inside GitHub cannot save the bot from GitHub's
own scheduler, because it is scheduled too. Delivery, measured after
moving the crons off the contended minutes:

```
2026-08-30   18 / 48   38%
2026-08-31    3 / 48    6%
2026-09-01    8 / 48   17%
```

⭐⭐ **It reads the committed heartbeat, not the Actions run list**, and
that is a cost AND a correctness decision:

```
GitHub Actions run list   306,759 bytes   1415 ms
raw ci_heartbeat.json         200 bytes    452 ms
```

1,500x less traffic on Lewis's VPS, and a better signal. The heartbeat is
only written by a run that did the work **and pushed**, so a `skipped`
run cannot produce one. The first version needed an explicit "skipped
does not count" rule; this gets that property for free, because a skipped
run leaves nothing to misread.
"""

import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "tools"))

from external_heartbeat import (DISPATCH_COOLDOWN, QUIET_AFTER,
                                parse_written_at, should_dispatch)

_NOW = datetime(2026, 9, 1, 20, 0, tzinfo=timezone.utc)


def _mins(n):
    return timedelta(minutes=n)


class TestItStaysQuietWhenTheBotIsRunning:
    def test_a_fresh_heartbeat_needs_no_help(self):
        assert not should_dispatch(_mins(10), None)

    def test_a_stale_heartbeat_dispatches(self):
        assert should_dispatch(_mins(90), None)

    def test_the_grace_window_is_where_it_is_documented(self):
        assert not should_dispatch(QUIET_AFTER - _mins(1), None)
        assert should_dispatch(QUIET_AFTER + _mins(1), None)

    def test_the_window_is_pinned_in_absolute_terms(self):
        # ⛔ The test above reads QUIET_AFTER, so it moves WITH the
        # constant and cannot detect the constant changing. A mutation
        # widening it to ten hours survived until this existed.
        assert _mins(30) < QUIET_AFTER <= timedelta(hours=2), (
            f"QUIET_AFTER is {QUIET_AFTER}; below 30m it fights normal "
            f"scheduling, above 2h the bot can sit dead through most of "
            f"the headroom before the 48h message wall.")


class TestTheCooldownStopsItMultiplyingABrokenRun:
    """⛔ If the bot RUNS but its push is broken, the heartbeat never
    refreshes and nothing this script does will help. Without a floor it
    would fire every tick forever."""

    def test_a_recent_dispatch_blocks_another(self):
        assert not should_dispatch(_mins(600), DISPATCH_COOLDOWN - _mins(1))

    def test_an_old_dispatch_does_not(self):
        assert should_dispatch(_mins(600), DISPATCH_COOLDOWN + _mins(1))

    def test_the_cooldown_outranks_even_an_unreadable_heartbeat(self):
        assert not should_dispatch(None, _mins(1))

    def test_never_dispatched_is_not_treated_as_recent(self):
        # can-fail counterpart: None must not read as "just dispatched",
        # or the very first run after install would do nothing.
        assert should_dispatch(_mins(600), None)

    def test_the_cooldown_is_pinned_in_absolute_terms(self):
        assert _mins(15) <= DISPATCH_COOLDOWN <= timedelta(hours=2)


class TestWhenItCannotTell:
    def test_an_unreadable_heartbeat_dispatches(self):
        # ⚠️ The opposite of the posting gate's rule, deliberately: there
        # a wrong guess sends a message that can never be deleted, here
        # it costs one cheap run.
        assert should_dispatch(None, None)


class TestReadingTheHeartbeat:
    def test_it_reads_a_real_payload(self):
        payload = (b'{"last_run_id":"33568046800","last_run_attempt":"1",'
                   b'"written_at":"2026-09-01T22:48:25.915769+00:00"}')
        assert parse_written_at(payload) == datetime(
            2026, 9, 1, 22, 48, 25, 915769, tzinfo=timezone.utc)

    def test_a_naive_timestamp_is_treated_as_utc(self):
        got = parse_written_at(b'{"written_at":"2026-09-01T22:48:25"}')
        assert got.tzinfo is timezone.utc

    def test_malformed_json_reads_as_unknown(self):
        assert parse_written_at(b"not json") is None

    def test_a_missing_field_reads_as_unknown(self):
        assert parse_written_at(b'{"why":"no timestamp here"}') is None

    def test_an_unparseable_timestamp_reads_as_unknown(self):
        assert parse_written_at(b'{"written_at":"soon"}') is None
