"""How long the GM queue would take to clear at the current pace.

Lewis, 2026-11-05: "It would be nice based on GM posting pace if we sent
another message that would say ETA of the queue being cleared."

One line, under the rate lines on the GM queue post::

    ⏱ ETA to clear: ~1.4 days (15 unreplied, ~11 cleared/day)

**Pace is replies CLEARED per day, not GM posts per day.** A GM post is not a
cleared entry: one post can answer three players in a scene, and a post in a
campaign nobody was waiting on clears nothing. The ETA is about the unreplied
count, so it divides by the thing that shrinks that count. Clears are read
from ``state["queue_history"]``, which ``commands.queue_stats.record_reply``
appends to for every GM reply and every ``/markdone``. GM post pace is not
used as a fallback either: when nothing was cleared in a week, a busy posting
rate would still promise an ETA the queue has not been meeting.

**Days** are the seven COMPLETE Europe/London days before today, the same
window ``gm_post_rate`` averages GM posts over, so a morning with few clears
so far does not drag the pace down.

⚠️ **This is the time to clear TODAY'S backlog at the current pace, and no
more.** New player posts keep arriving while the GM clears old ones, so the
queue will not actually be empty by then unless players go quiet. It is an
answer to "how far behind am I", not a forecast.

Everything takes ``now`` so tests can pin the clock.
"""

from datetime import datetime, timedelta, timezone

from scheduled.local_time import to_local

HISTORY_KEY = "queue_history"
PACE_DAYS = 7


def _local_date(iso: str):
    """The London date of a stored UTC stamp, or None if it cannot be read."""
    try:
        at = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return None
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    return to_local(at).date()


def clears_per_day(state: dict, now: datetime) -> float:
    """Average clears per day over the PACE_DAYS complete days before today."""
    today = to_local(now).date()
    first = today - timedelta(days=PACE_DAYS)
    cleared = 0
    for stamps in state.get(HISTORY_KEY, {}).values():
        for iso in stamps:
            day = _local_date(iso)
            if day is not None and first <= day < today:
                cleared += 1
    return cleared / PACE_DAYS


def _duration(days: float) -> str:
    """'~5 hours' under a day, '~1.4 days' from a day up."""
    if days < 1:
        hours = max(1, round(days * 24))
        return f"~{hours} hour{'s' if hours != 1 else ''}"
    return f"~{days:.1f} days"


def eta_line(state: dict, total: int, now: datetime) -> str | None:
    """The ETA line, or None when the queue is empty."""
    if total <= 0:
        return None
    pace = clears_per_day(state, now)
    if pace <= 0:
        return (f"⏱ ETA to clear: none, no clears in the last {PACE_DAYS} "
                f"days ({total} unreplied)")
    rate = f"{pace:.0f}" if pace >= 10 else f"{pace:.1f}".removesuffix(".0")
    return (f"⏱ ETA to clear: {_duration(total / pace)} "
            f"({total} unreplied, ~{rate} cleared/day)")
