"""A stale heartbeat has two causes. The gate must act on the right one.

Written 2026-09-04 from a real day. The bot paused and alerted Lewis
three times - "the last state push landed 3.2h ago", then 3.1h, then 3.3h
- while **every one of the last 40 runs had concluded success**. Nothing
had failed to push. GitHub had skipped two hours of a cron it was
delivering about 27% of, three separate times, and each gap read as a
state-persistence outage.

The two halves of this file are the two failure directions, and both must
hold at once or the fix is worse than the bug:

  TestTheRealMonday    a gap with no runs behind it must NOT halt
  TestTheCachedPage    the 2026-08-19 cached-API reading must STILL halt

The second is the reason ``delivery_gap`` demands a freshness proof at
all. A cached page of old runs is indistinguishable from a delivery gap
by timestamps alone, so without that proof this whole change would have
re-opened the incident it must not touch.
"""

from datetime import datetime, timedelta, timezone

import pytest

from preflight import gate
from preflight.delivery_gap import (STALE_HEARTBEAT_MARKER, is_delivery_gap,
                                    drop_stale_heartbeat_reason)
from preflight.prior_runs import halt_reasons

_NOW = datetime(2026, 9, 4, 15, 5, tzinfo=timezone.utc)
_THIS_RUN = "33906473914"


def _at(hours_ago: float) -> str:
    return (_NOW - timedelta(hours=hours_ago)).isoformat()


def _run(run_id, hours_ago, conclusion="success"):
    return {"id": run_id, "conclusion": conclusion,
            "created_at": _at(hours_ago)}


def _heartbeat(hours_ago: float) -> dict:
    return {"written_at": _at(hours_ago), "last_run_id": "33900000000"}


class TestTheMarkerStillMatches:
    """⚠️ The suppression keys off prose built somewhere else.

    ``delivery_gap`` recognises the reason to drop by substring, and
    ``prior_runs.halt_reasons`` writes that prose. Pin them together, or
    a reword silently disarms the suppression and the pauses come back
    with every test still green.
    """

    def test_the_marker_matches_a_real_halt_reason(self):
        reasons = halt_reasons(0, 3.2)
        assert len(reasons) == 1, "expected the stale-heartbeat reason alone"
        assert STALE_HEARTBEAT_MARKER in reasons[0], (
            f"delivery_gap keys off {STALE_HEARTBEAT_MARKER!r} but "
            f"halt_reasons now says {reasons[0]!r}")

    def test_the_marker_does_not_match_the_failed_run_reason(self):
        """It must remove ONE reason, never the streak's."""
        assert STALE_HEARTBEAT_MARKER not in halt_reasons(9, None)[0]


class TestTheRealMonday:
    """2026-09-04: no runs at all for 3.3h, every prior run green."""

    def test_a_gap_with_no_runs_behind_it_is_not_a_persistence_failure(self):
        # The last push landed 3.3h ago; the newest run before this one
        # is the run that wrote it. Nothing has tried and lost.
        runs = [_run(_THIS_RUN, 0.0), _run(90, 3.3), _run(89, 4.1)]
        assert is_delivery_gap(runs, _heartbeat(3.3), _THIS_RUN)

    def test_and_so_the_gate_does_not_pause(self):
        runs = [_run(_THIS_RUN, 0.0), _run(90, 3.3)]
        kept, note = drop_stale_heartbeat_reason(
            halt_reasons(0, 3.3), runs, _heartbeat(3.3), _THIS_RUN)
        assert kept == []
        assert "not delivering the schedule" in note

    def test_a_run_that_did_happen_and_failed_still_pauses(self):
        """⭐ The can-fail counterpart. One finished run since the last
        push is enough: it had its chance and state did not move."""
        runs = [_run(_THIS_RUN, 0.0), _run(91, 1.0, "failure"),
                _run(90, 3.3)]
        assert not is_delivery_gap(runs, _heartbeat(3.3), _THIS_RUN)
        kept, note = drop_stale_heartbeat_reason(
            halt_reasons(0, 3.3), runs, _heartbeat(3.3), _THIS_RUN)
        assert len(kept) == 1 and note == ""

    def test_an_in_progress_run_is_not_yet_evidence(self):
        """A run that has not finished has not attempted its push."""
        runs = [_run(_THIS_RUN, 0.0), {"id": 91, "conclusion": None,
                                       "created_at": _at(0.2)},
                _run(90, 3.3)]
        assert is_delivery_gap(runs, _heartbeat(3.3), _THIS_RUN)

    def test_the_streak_reason_is_never_suppressed(self):
        """⛔ Failed runs are direct evidence a push lost. Untouchable."""
        runs = [_run(_THIS_RUN, 0.0), _run(90, 3.3)]
        kept, _ = drop_stale_heartbeat_reason(
            halt_reasons(9, 3.3), runs, _heartbeat(3.3), _THIS_RUN)
        assert len(kept) == 1
        assert "9 consecutive workflow runs failed" in kept[0]

    def test_a_streak_alone_survives_and_reports_nothing(self):
        """A gap that explains none of the reasons must say so by
        staying silent. A note describing a suppression that did not
        happen would put a false exoneration in the log."""
        runs = [_run(_THIS_RUN, 0.0), _run(90, 3.3)]
        streak_only = halt_reasons(9, None)
        kept, note = drop_stale_heartbeat_reason(
            streak_only, runs, _heartbeat(3.3), _THIS_RUN)
        assert kept == streak_only
        assert note == ""


class TestTheCachedPage:
    """⛔⛔ 2026-08-19. This must keep halting or the fix is a regression.

    That day the Actions API served a page of runs from three days
    earlier. By timestamps alone it is the same shape as a quiet
    scheduler: old runs, none since the heartbeat. Only the freshness
    proof separates them.
    """

    def test_a_stale_page_cannot_unlock_the_gate(self):
        stale = [_run(70, 72.0), _run(69, 72.5), _run(68, 73.0)]
        assert not is_delivery_gap(stale, _heartbeat(70.0), _THIS_RUN), (
            "a page that does not contain the running run was believed")

    def test_the_same_page_containing_this_run_is_trusted(self):
        """⭐ Can-fail counterpart: proves the rejection above is the
        freshness proof doing its job and not some other refusal."""
        fresh = [_run(_THIS_RUN, 0.0), _run(70, 72.0), _run(69, 72.5)]
        assert is_delivery_gap(fresh, _heartbeat(70.0), _THIS_RUN)


class TestItFailsClosed:
    """Every unknown leaves the halt standing."""

    @pytest.mark.parametrize("runs,heartbeat,run_id", [
        (None, _heartbeat(3.3), _THIS_RUN),                 # no history
        ([], _heartbeat(3.3), _THIS_RUN),                   # empty history
        ([_run(_THIS_RUN, 0.0)], _heartbeat(3.3), None),    # not in Actions
        ([_run(_THIS_RUN, 0.0)], _heartbeat(3.3), ""),      # blank run id
        ([_run(_THIS_RUN, 0.0)], None, _THIS_RUN),          # no heartbeat
        ([_run(_THIS_RUN, 0.0)], {}, _THIS_RUN),            # unreadable
        ([_run(_THIS_RUN, 0.0)], {"written_at": "?"}, _THIS_RUN),
    ])
    def test_unknowns_never_suppress(self, runs, heartbeat, run_id):
        assert not is_delivery_gap(runs, heartbeat, run_id)

    def test_no_reasons_stays_no_reasons(self):
        assert drop_stale_heartbeat_reason([], None, None, None) == ([], "")


class TestEndToEndThroughMain:
    """The wiring, not just the arithmetic. A correct decision that
    ``main`` never consults changes nothing."""

    @pytest.fixture(autouse=True)
    def _env(self, tmp_path, monkeypatch):
        self.out = tmp_path / "out.txt"
        monkeypatch.setenv("GITHUB_OUTPUT", str(self.out))
        monkeypatch.setenv("GITHUB_REPOSITORY", "o/r")
        monkeypatch.setenv("GITHUB_TOKEN", "tok")
        monkeypatch.setenv("GITHUB_RUN_ID", _THIS_RUN)
        self.alerts = []
        monkeypatch.setattr(gate, "send_alert",
                            lambda *a, **k: self.alerts.append(a))
        monkeypatch.setattr(gate, "write_heartbeat", lambda *a, **k: {})

    def _main(self, runs, heartbeat, monkeypatch):
        monkeypatch.setattr(gate, "fetch_runs", lambda *a, **k: runs)
        monkeypatch.setattr(gate, "read_heartbeat", lambda *a, **k: heartbeat)
        monkeypatch.setattr(gate, "heartbeat_age_hours", lambda r, n: 3.3)
        return gate.main()

    def test_the_gap_no_longer_pauses_or_alerts(self, monkeypatch):
        runs = [_run(_THIS_RUN, 0.0), _run(90, 3.3)]
        assert self._main(runs, _heartbeat(3.3), monkeypatch) == 0
        assert self.out.read_text(encoding="utf-8") == "halt=false\n"
        assert self.alerts == [], "alerted about a push that never failed"

    def test_a_real_push_failure_still_pauses_and_alerts(self, monkeypatch):
        # ⭐ Can-fail counterpart, through the same wiring.
        runs = [_run(_THIS_RUN, 0.0), _run(91, 1.0, "failure"),
                _run(90, 3.3)]
        assert self._main(runs, _heartbeat(3.3), monkeypatch) == 0
        assert self.out.read_text(encoding="utf-8") == "halt=true\n"
        assert len(self.alerts) == 1
