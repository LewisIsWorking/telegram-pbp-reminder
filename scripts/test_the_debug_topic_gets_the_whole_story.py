"""What the "bot stopped posting" report actually SAYS.

Written 2026-09-04 from Lewis's ask: *"add more debugging to the bot
stopped posting messages to aid you in debugging."*

The bar: a report is only worth sending if it answers the question asked
during a real incident. That day the one-line alert sent Lewis to a
state-commit step that had never failed, three times, because it named a
symptom and no cause. So these check the report NAMES A CAUSE and carries
the evidence - not merely that it is long.

Where it goes is ``test_bot_alerts_reach_the_right_topic``; the delete
wall it reports on is ``test_orphan_risk_warns_before_the_wall``.
"""

import pytest

from _test_preflight_helpers import NOW, REPO, THIS_RUN, at, heartbeat, run
from preflight import diagnostics


class TestItNamesTheCause:
    """The whole point. A symptom without a cause is what failed before."""

    def test_a_delivery_gap_is_named_as_github_not_running_us(self):
        runs = [run(THIS_RUN, 0.0), run(90, 3.3)]
        report = diagnostics.build(["stale"], 3.3, heartbeat(3.3), runs, THIS_RUN,
                                   REPO, now=NOW)
        assert "GITHUB DID NOT RUN US" in report
        assert "Posting is safe" in report

    def test_a_failed_push_is_named_as_a_failed_push(self):
        """⭐ Can-fail counterpart: the same shape must reach the OTHER
        verdict, or the first test would pass on a hardcoded string."""
        runs = [run(THIS_RUN, 0.0), run(91, 1.0, "failure"), run(90, 3.3)]
        report = diagnostics.build(["stale"], 3.3, heartbeat(3.3), runs, THIS_RUN,
                                   REPO, now=NOW)
        assert "A PUSH LIKELY FAILED" in report
        assert "GITHUB DID NOT RUN US" not in report
        assert "state-commit step" in report

    def test_it_refuses_to_name_a_cause_it_cannot_prove(self):
        """⛔ An unfresh history must produce UNDETERMINED, never a guess.
        This is the 2026-08-19 cached-page shape."""
        stale_page = [run(70, 72.0), run(69, 72.5)]
        report = diagnostics.build(["stale"], 70.0, heartbeat(70.0), stale_page,
                                   THIS_RUN, REPO, now=NOW)
        assert "UNDETERMINED" in report
        assert "GITHUB DID NOT RUN US" not in report
        assert "A PUSH LIKELY FAILED" not in report


class TestItCarriesTheEvidence:
    def test_the_run_gaps_are_shown(self):
        """The gaps, not the runs, are what make non-delivery obvious."""
        runs = [run(THIS_RUN, 0.0), run(90, 3.3), run(89, 4.1)]
        report = diagnostics.build([], None, heartbeat(3.3), runs, THIS_RUN, REPO,
                                   now=NOW)
        assert "+3.30h" in report

    def test_the_delivery_rate_is_measured_against_what_was_asked(self):
        runs = [run(THIS_RUN, 0.0)] + [run(100 + i, i + 1.0) for i in range(11)]
        line = diagnostics.delivery_line(runs, NOW)
        assert "12/48" in line and "25%" in line

    def test_a_full_history_page_admits_it_may_undercount(self):
        """⚠️ 40 runs is the page size, so a healthy day can fill it and
        read as a low number. Saying so beats reporting a lie."""
        runs = [run(200 + i, i * 0.5) for i in range(40)]
        assert "may undercount" in diagnostics.delivery_line(runs, NOW)

    def test_an_unavailable_history_says_unknown_not_zero(self):
        assert "UNKNOWN" in diagnostics.delivery_line(None, NOW)

    def test_the_heartbeat_names_the_run_that_wrote_it(self):
        report = diagnostics.build([], 1.0, heartbeat(1.0), None, THIS_RUN, REPO,
                                   now=NOW)
        assert "33900000000" in report

    def test_it_reports_daily_jobs_that_have_stopped_happening(self, monkeypatch):
        """⛔⛔ The section that would have caught two features being dead
        for ten days while every other line said healthy.

        A mutation deleting this section from the report SURVIVED the
        whole suite: the block was built and tested on its own, and
        nothing asserted it reached the message. Building a diagnostic
        and not wiring it in is the same as not having it.
        """
        monkeypatch.setattr(diagnostics, "summarise_from_disk",
                            lambda now: "Daily jobs: 10 tracked, 2 overdue")
        report = diagnostics.build([], 1.0, heartbeat(1.0), None, THIS_RUN,
                                   REPO, now=NOW)
        assert "2 overdue" in report

    def test_a_broken_section_costs_only_itself(self, monkeypatch):
        """⛔ This is read when nothing else works. One raising section
        must not take the other six down with it."""
        monkeypatch.setattr(diagnostics, "scan",
                            lambda *a, **k: (_ for _ in ()).throw(OSError("x")))
        report = diagnostics.build([], 1.0, heartbeat(1.0), [run(THIS_RUN, 0.0)],
                                   THIS_RUN, REPO, now=NOW)
        assert "section failed" in report
        assert "RECENT RUNS" in report

    def test_it_fits_telegrams_cap(self):
        """⚠️ Telegram REJECTS over 4096, it does not truncate, so an
        oversized report would send nothing at all.

        ⛔ The input must ACTUALLY overflow. The first version of this
        test passed 40 one-character reasons, which came to well under
        the cap, so deleting the trim left it green - a measurement with
        no expected value cannot fail. Asserted below that the raw
        material really was too big.
        """
        reasons = [f"reason {i} " + "x" * 300 for i in range(40)]
        assert sum(len(r) for r in reasons) > diagnostics.MAX_MESSAGE
        report = diagnostics.build(reasons, 3.3, heartbeat(3.3), None, THIS_RUN,
                                   REPO, now=NOW)
        assert len(report) <= diagnostics.MAX_MESSAGE + 40
        assert "trimmed to fit Telegram" in report
