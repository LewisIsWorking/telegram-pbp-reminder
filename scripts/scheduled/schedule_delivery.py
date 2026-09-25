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


# Runs that actually do the bot's work. pull_request runs only test.
_WORKING_EVENTS = ("schedule", "workflow_dispatch", "push")


def covered_slots(runs: list, now: datetime, hours: int = 24) -> int:
    """How many of the window's half-hour slots had at least one working run.

    ⭐ Added 2026-09-25. GitHub's cron delivers about a quarter of what it is
    asked for, and the VPS backstop (tools/external_heartbeat.py) covers the
    rest. So "scheduled runs delivered" warned every day about something
    already handled, while the number that matters - did the bot run every
    half hour, from any source - was never reported.
    """
    seen = set()
    for run in runs:
        if run.get("event") not in _WORKING_EVENTS:
            continue
        try:
            started = datetime.fromisoformat(
                (run.get("created_at") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        age = (now - started).total_seconds()
        if 0 <= age < hours * 3600:
            seen.add(int(age // 1800))
    return len(seen)


def report_line(runs: list, now: datetime, *, page_size: int | None = None,
                hours: int = 24) -> str:
    """The scheduler line for the daily diagnostic: coverage first, cron second."""
    delivered = delivered_in_window(runs, now, hours)
    # ⛔ 2026-09-23: A FULL PAGE IS NOT A TRUNCATED COUNT. This used to be
    # `len(runs) >= page_size`, and the page of 100 is full on every day the
    # workflow has ever run 100 times, so the diagnostic said "at least" on a
    # real 12 of 48 and made GitHub dropping three quarters of the schedule
    # read as a measurement problem. The page only cuts the count short when
    # its OLDEST run is still inside the window; if the page reaches back
    # past the window, every run in the window is on it.
    capped = (page_size is not None and len(runs) >= page_size
              and _oldest_is_inside(runs, now - timedelta(hours=hours)))
    expected = expected_in_window(hours)
    if capped or expected <= 0:
        return delivery_line(delivered, expected, capped=capped)
    slots = hours * 2
    covered = covered_slots(runs, now, hours)
    ratio = covered / slots
    ok = ratio >= HEALTHY_DELIVERY
    text = (f"{'🕒' if ok else '⚠️'} Schedule: {covered} of {slots} half-hour slots "
            f"had a run ({ratio:.0%}). GitHub's own cron sent {delivered} of "
            f"{expected}; the VPS backstop covers the rest.")
    if ok:
        return text
    return (text + f" Expected {HEALTHY_DELIVERY:.0%}+: the bot is running less "
            f"often than it should. Check the VPS backstop (its crontab and "
            f"/var/log/pathwars-heartbeat.log) as well as GitHub.")


def _oldest_is_inside(runs: list, cutoff: datetime) -> bool:
    """True when the earliest run on the page started after ``cutoff``.

    Any event counts here, not only ``schedule``: the question is how far
    back the PAGE reaches, and a push run marks that just as well. An
    unreadable timestamp is treated as inside, so doubt keeps "at least".
    """
    stamps = []
    for run in runs:
        try:
            stamps.append(datetime.fromisoformat(
                (run.get("created_at") or "").replace("Z", "+00:00")))
        except ValueError:
            return True
    return not stamps or min(stamps) > cutoff
