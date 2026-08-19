"""The streak arithmetic, fed the incident it was written for.

⭐ The load-bearing test in this file is ``test_halts_on_the_real_incident``:
it replays the actual conclusions from 2026-08-18/19 and requires a halt.
Its counterpart ``test_does_not_halt_a_healthy_history`` proves the gate
can still open - without it, a function hardcoded to ``return True`` would
pass the first test and read as working.
"""

from preflight.prior_runs import (HALT_AFTER_CONSECUTIVE_FAILURES,
                                  MAX_HEARTBEAT_AGE_HOURS,
                                  REPEAT_ALERT_EVERY_HOURS, broken_hours,
                                  consecutive_failures, explain, halt_reasons,
                                  should_alert, should_halt_for_stale_heartbeat,
                                  should_halt_posting)

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


class TestStaleHeartbeat:
    def test_a_fresh_push_does_not_halt(self):
        assert not should_halt_for_stale_heartbeat(0.5)

    def test_an_old_push_halts(self):
        assert should_halt_for_stale_heartbeat(MAX_HEARTBEAT_AGE_HOURS + 0.1)

    def test_exactly_at_the_limit_is_tolerated(self):
        assert not should_halt_for_stale_heartbeat(MAX_HEARTBEAT_AGE_HOURS)

    def test_unknown_age_does_not_halt_on_its_own(self):
        # ⚠️ "Cannot read the heartbeat" is not evidence of staleness. It
        # contributes nothing rather than halting, or the very first run
        # after this ships would silence the bot.
        assert not should_halt_for_stale_heartbeat(None)


class TestHaltReasons:
    def test_the_cached_api_case_still_halts(self):
        # ⭐⭐ THE REGRESSION TEST. On 2026-08-19 the Actions API served a
        # cached page of runs from three days earlier, so the streak read 0
        # while state had not been pushed for 15 hours. The gate opened and
        # posting proceeded. Now the heartbeat halts it regardless of what
        # the API claims.
        reasons = halt_reasons(0, 15.0)
        assert reasons, "a stale heartbeat must halt even when the API says all is well"
        assert "15.0h ago" in reasons[0]

    def test_the_reverse_also_holds(self):
        # A fresh heartbeat must not clear a failing streak either. Neither
        # signal may overrule the other; each can only add a reason.
        assert halt_reasons(25, 0.1)

    def test_both_signals_are_reported_when_both_fire(self):
        assert len(halt_reasons(25, 15.0)) == 2

    def test_nothing_wrong_means_no_reasons(self):
        # ⭐ can-fail counterpart: without this, returning a constant
        # non-empty list would pass every test above.
        assert halt_reasons(0, 0.5) == []

    def test_unknown_age_with_a_clean_history_does_not_halt(self):
        assert halt_reasons(0, None) == []


class TestBrokenHours:
    def test_prefers_the_heartbeat(self):
        assert broken_hours(0, MAX_HEARTBEAT_AGE_HOURS + 5) == 5

    def test_falls_back_to_the_streak_when_age_is_unknown(self):
        assert broken_hours(6, None) == 3  # two runs an hour

    def test_never_negative(self):
        assert broken_hours(0, 0.0) == 0


class TestShouldAlert:
    def test_alerts_at_onset(self):
        assert should_alert(0)

    def test_alerts_again_when_nobody_has_looked(self):
        assert should_alert(3)

    def test_stays_quiet_between_those(self):
        # Otherwise the fix for spam is itself spam.
        assert not should_alert(1)
        assert not should_alert(2)

    def test_then_once_a_day(self):
        assert should_alert(REPEAT_ALERT_EVERY_HOURS)
        assert should_alert(REPEAT_ALERT_EVERY_HOURS * 2)

    def test_not_on_the_hours_in_between(self):
        assert not should_alert(REPEAT_ALERT_EVERY_HOURS + 1)
        assert not should_alert(5)


class TestExplain:
    def test_names_every_cause_and_the_consequence(self):
        message = explain(halt_reasons(25, 15.0), 15.0)
        assert "25 consecutive" in message
        assert "15.0h ago" in message
        # The operator needs to know where to look and why it matters.
        assert "state-commit step" in message
        assert "48h" in message

    def test_says_so_when_healthy(self):
        assert "healthy" in explain([], 0.4)

    def test_cannot_disagree_with_the_decision(self):
        # ⭐ explain() takes the reasons the gate acted on, not the raw
        # numbers, so it cannot report a cause that was not acted upon.
        assert "healthy" in explain([], 99.0)
