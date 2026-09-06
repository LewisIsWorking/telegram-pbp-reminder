"""Is a once-a-day job due? Asked so a missed hour does not skip the day.

⛔⛔ Added 2026-09-06 after finding two features silently dead for TEN
DAYS. ``last_diagnostic`` and ``last_pin_digest`` both read 2026-08-27,
and both were gated like this::

    if now.hour != config.get("diagnostic_hour", 8):
        return

That is correct only if a run happens during hour 8. The bot asks GitHub
for 48 scheduled runs a day and has been getting about 27% of them, so
its runs land in **4 to 13 distinct hours out of 24**. Measured over the
13 days to 2026-09-06: a run landed in hour 08 on **3 days**, and there
was an unbroken run of **8 days with none at all**.

So the gate was not "run daily at 08:00". It was "run daily at 08:00 if
GitHub happens to fire in that hour", which is a coin toss, and nothing
anywhere reported the misses. The features were green, tested, and never
happened.

⭐ **The fix is the shape the rest of the codebase already uses.**
``potw_schedule``, ``session_poll``, ``week_welcome``, ``swimming_poll``
and ``poll_result`` all gate on ``hour >= post_hour``, so the first run
at or after the hour does the work. Only these two used equality. This
module makes that shape explicit and shared rather than re-derived.

⚠️ The once-a-day guarantee still comes from the caller's ``last_*``
date marker, which is unchanged. This answers "is it time yet", never
"have I already done it" - keeping those separate is what lets a caller
be late without being repeated.
"""

from datetime import datetime


def is_due(now: datetime, hour: int, last_done: str | None) -> bool:
    """True when today's run at ``hour`` is due and has not happened.

    ``last_done`` is an ISO date string (or datetime string) recording
    the last completion; anything whose first 10 characters equal
    today's date counts as done.

    ⚠️ Deliberately ``>=``, not ``==``. Equality is the bug this module
    exists for: it converts "daily" into "daily, if the scheduler
    cooperates during one specific hour".
    """
    if now.hour < hour:
        return False
    return not is_done_today(now, last_done)


def is_done_today(now: datetime, last_done: str | None) -> bool:
    """True when ``last_done`` records a completion dated today.

    Tolerates None, a bare date, and a full timestamp, because these
    markers were written by several different callers over time. An
    unparseable marker reads as NOT done: a job that runs twice is a
    duplicate message, a job that never runs is a feature that silently
    does not exist, and only one of those gets noticed.
    """
    if not isinstance(last_done, str) or len(last_done) < 10:
        return False
    return last_done[:10] == now.date().isoformat()


def missed_days(now: datetime, last_done: str | None) -> int | None:
    """Whole days since this job last ran, or None if it never has.

    Used by the health report to say a feature has stopped happening.
    ⛔ Nothing was asking this, which is why ten days passed unnoticed.
    """
    if not isinstance(last_done, str) or len(last_done) < 10:
        return None
    try:
        then = datetime.fromisoformat(last_done[:10]).date()
    except ValueError:
        return None
    return (now.date() - then).days


def latest_due_slot(now: datetime, hours: list, posted_slots) -> str | None:
    """The ``YYYY-MM-DD:HH`` slot that is due now and not yet posted.

    ⛔ ``queue_reminder`` had the same equality bug in list form -
    ``if now.hour in daily_hours`` - and the evidence is in the state
    file: of 28 daily slots in the two weeks to 2026-09-04, **10 were
    never posted**, including both slots on three separate days. Two
    configured hours instead of one meant it half-worked, which is why
    it read as healthy.

    ⭐ Returns the LATEST due slot, never every missed one. At 22:00 with
    hours [9, 21] and both unposted, this posts the 21 slot and leaves 09
    missed on purpose: a 09:00 reminder delivered at 22:00 next to the
    21:00 one is two messages saying the same thing, and the queue post
    is replaced rather than appended anyway.
    """
    today = now.date().isoformat()
    due = [h for h in hours if isinstance(h, int) and now.hour >= h]
    if not due:
        return None
    slot = f"{today}:{max(due):02d}"
    return None if slot in (posted_slots or []) else slot
