"""The streak arithmetic, fed the incident it was written for.

⭐ The load-bearing test in this file is ``test_halts_on_the_real_incident``:
it replays the actual conclusions from 2026-08-18/19 and requires a halt.
Its counterpart ``test_does_not_halt_a_healthy_history`` proves the gate
can still open - without it, a function hardcoded to ``return True`` would
pass the first test and read as working.
"""

from preflight.prior_runs import (HALT_AFTER_CONSECUTIVE_FAILURES,
                                  REPEAT_ALERT_EVERY, consecutive_failures,
                                  explain, should_alert, should_halt_posting)

# The run history as `gh run list` reported it on 2026-08-19, newest first:
# 25 straight failures after the last success at 2026-08-18T15:01.
REAL_INCIDENT = [None] + ["failure"] * 25 + ["success", "success"]


class TestConsecutiveFailures:
    def test_counts_a_leading_run_of_failures(self):
        assert consecutive_failures(["failure", "failure", "success"]) == 2

    def test_stops_at_the_first_success(self):
        assert consecutive_failures(["failure", "success", "failure"]) == 1

    def test_a_clean_history_is_zero(self):
        assert consecutive_failures(["success", "success"]) == 0

    def test_no_history_at_all_is_zero(self):
        assert consecutive_failures([]) == 0

    def test_skips_the_in_progress_run_asking_the_question(self):
        # The current run appears with conclusion None. It must not count
        # as a failure, or the very first run would halt itself.
        assert consecutive_failures([None, "success"]) == 0

    def test_none_between_failures_does_not_break_the_streak(self):
        assert consecutive_failures(["failure", None, "failure", "success"]) == 2

    def test_cancelled_and_timed_out_count_as_failures(self):
        # The question is "did state reach the remote", and for all three
        # of these it did not. Only `success` may break the streak.
        assert consecutive_failures(["cancelled", "timed_out",
                                     "startup_failure", "success"]) == 3

    def test_the_real_incident_streak(self):
        assert consecutive_failures(REAL_INCIDENT) == 25


class TestShouldHaltPosting:
    def test_halts_on_the_real_incident(self):
        # ⭐ Feed the guard the bug. Four duplicate "Unreplied: 1" posts
        # went out during this streak; every one should have been blocked.
        assert should_halt_posting(consecutive_failures(REAL_INCIDENT))

    def test_does_not_halt_a_healthy_history(self):
        # ⭐ The can-fail counterpart. Without this, `return True` passes.
        assert not should_halt_posting(consecutive_failures(["success"] * 5))

    def test_one_failure_is_tolerated(self):
        # A single red run is a blip - a runner dying, a rebase race the
        # next run wins. Halting on one would silence the bot constantly.
        assert not should_halt_posting(1)

    def test_two_failures_trips_it(self):
        assert should_halt_posting(HALT_AFTER_CONSECUTIVE_FAILURES)

    def test_reopens_once_a_run_goes_green(self):
        # The recovery path, and the reason the gate must not fail its own
        # job: one successful push must be enough to let the bot speak.
        recovered = ["success"] + ["failure"] * 25
        assert not should_halt_posting(consecutive_failures(recovered))


class TestShouldAlert:
    def test_alerts_when_it_first_trips(self):
        assert should_alert(2)

    def test_alerts_again_when_nobody_has_looked(self):
        assert should_alert(6)

    def test_stays_quiet_between_those(self):
        # Otherwise the fix for spam is itself hourly spam.
        assert not should_alert(3)
        assert not should_alert(4)
        assert not should_alert(5)

    def test_then_once_a_day(self):
        assert should_alert(REPEAT_ALERT_EVERY)
        assert should_alert(REPEAT_ALERT_EVERY * 2)

    def test_not_on_the_hours_in_between(self):
        assert not should_alert(REPEAT_ALERT_EVERY + 1)

    def test_silent_while_healthy(self):
        assert not should_alert(0)
        assert not should_alert(1)


class TestExplain:
    def test_names_the_cause_and_the_consequence_when_halting(self):
        message = explain(25)
        assert "25 consecutive" in message
        # The operator needs to know where to look and why it matters.
        assert "state-commit step" in message
        assert "48h" in message

    def test_says_so_when_healthy(self):
        assert "healthy" in explain(0)
