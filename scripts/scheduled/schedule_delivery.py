"""Is GitHub actually running us as often as we asked?

Added 2026-08-31, after four days in which it was not and nothing said so.

The visible symptom was preflight pausing posting: *"the last state push
landed 3.2h ago, over the 3h limit ... Check the state-commit step."* The
state-commit step was healthy and had never failed. The runs simply were
not happening: 173 of 372 scheduled runs delivered over 2026-08-23 to
08-31, and as few as 2 in a day.

⛔ **preflight cannot tell these apart.** A stale heartbeat means "no
state push landed recently", which has two causes: our push failed, or
GitHub never ran us. Both look identical from inside the repository,
because a run that never happened writes nothing and a run whose push
failed also leaves nothing behind. So preflight reports the one it was
built for and points at the state-commit step. This module measures the
other cause directly, so the two can be told apart from the report rather
than by hand.

⚠️ It reports and never halts. Delivery is GitHub's behaviour, not a
fault in this repository, and a gate on it would block posting for a
reason no change here could clear.
"""

from datetime import datetime, timedelta

# The two crons in .github/workflows/pbp-reminder.yml, each hourly.
# ⚠️ test_schedule_delivery.py fails if this stops matching the workflow.
# A hardcoded expected value that drifts from the schedule is worse than
# none, because it looks authoritative while comparing against fiction.
SCHEDULED_RUNS_PER_DAY = 48

# Below this, say so loudly. GitHub delays the schedule event under load
# and drops some entirely, so 100% is not a realistic target; 90% was the
# lived normal (45 to 52 a day) before 2026-08-27.
HEALTHY_DELIVERY = 0.90


def delivered_in_window(runs: list, now: datetime, hours: int = 24) -> int:
    """Count schedule-triggered runs started within the window.

    Only ``schedule``. Push and pull_request runs are real runs but say
    nothing about the scheduler, and counting them would let a busy day
    of merges disguise a dead cron.
    """
    cutoff = now - timedelta(hours=hours)
    count = 0
    for run in runs:
        if run.get("event") != "schedule":
            continue
        stamp = run.get("created_at") or ""
        try:
            started = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        except ValueError:
            continue
        if started > cutoff:
            count += 1
    return count


def expected_in_window(hours: int = 24) -> int:
    """How many scheduled runs that window asked GitHub for."""
    return int(SCHEDULED_RUNS_PER_DAY * hours / 24)


def delivery_line(delivered: int, expected: int, *, capped: bool = False) -> str:
    """One line naming the count, the basis, and the verdict.

    ⭐ The expected value is in the string, not in someone's head. The
    diagnostic previously printed "24 runs analysed" with no denominator,
    while asking the API for at most 25 and expecting 48. A count whose
    instrument tops out below the healthy value, reported without its
    basis, reads as normal at every level of brokenness.

    ``capped`` marks a reading that hit the page limit, so a truncated
    count is never presented as a measurement.
    """
    if expected <= 0:
        return "🕒 Scheduler: no schedule configured."
    ratio = delivered / expected
    icon = "🕒" if ratio >= HEALTHY_DELIVERY else "⚠️"
    text = (f"{icon} Scheduler: {delivered} of {expected} scheduled runs "
            f"delivered ({ratio:.0%})")
    if capped:
        return text + ", at least: the run list hit its page limit."
    if ratio >= HEALTHY_DELIVERY:
        return text + "."
    return (text + f". Expected {HEALTHY_DELIVERY:.0%}+. GitHub is dropping "
            f"scheduled runs, which ages the preflight heartbeat and pauses "
            f"posting; the state-commit step is not the fault.")


def report_line(runs: list, now: datetime, *, page_size: int | None = None,
                hours: int = 24) -> str:
    """The scheduler line for the daily diagnostic."""
    delivered = delivered_in_window(runs, now, hours)
    capped = page_size is not None and len(runs) >= page_size
    return delivery_line(delivered, expected_in_window(hours), capped=capped)
