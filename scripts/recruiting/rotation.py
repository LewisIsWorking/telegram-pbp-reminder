"""Which venues are due today, and which are still cooling down.

The point of a rotation is not to post in more places. It is to post in
more places **without getting thrown out of any of them.** Every venue
here has a cooldown, and the ones we have not verified are treated as the
strictest rather than the loosest.

⚠️ A venue we have never posted to is DUE, not "0 days since". Those are
two different states and only one of them is an opportunity. See
``due_venues``.
"""

from datetime import datetime, timezone

from recruiting import catalogue, log

# Never surface more than this at once. A list of nine venues reads as a
# chore and gets skipped entirely; three reads as a task and gets done.
# The rest are not lost, they are simply next.
MAX_SUGGESTIONS = 3


def days_since(then_iso: str | None, now: datetime) -> float | None:
    """Days since an ISO timestamp, or None if it never happened.

    None is "never", which is emphatically not zero. Returning 0.0 for a
    venue nobody has ever posted to would make it look freshly used and
    permanently suppress it.
    """
    if not then_iso:
        return None
    try:
        then = datetime.fromisoformat(then_iso)
    except (TypeError, ValueError):
        return None
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return (now - then).total_seconds() / 86400.0


def is_due(venue: dict, state: dict, now: datetime) -> bool:
    """True when this venue may be posted to right now."""
    elapsed = days_since(log.last_posted(state, venue["id"]), now)
    return elapsed is None or elapsed >= venue["cooldown_days"]


def cooldown_remaining(venue: dict, state: dict, now: datetime) -> float:
    """Days left before this venue is due. 0.0 when it is due now."""
    elapsed = days_since(log.last_posted(state, venue["id"]), now)
    if elapsed is None:
        return 0.0
    return max(0.0, venue["cooldown_days"] - elapsed)


def _priority(venue: dict, state: dict, now: datetime) -> tuple:
    """Sort key. Lower sorts first.

    Never-posted venues come first: an untried venue is the only kind that
    can still teach us something, and the whole exercise is a search. After
    that, whichever has been waiting longest.
    """
    elapsed = days_since(log.last_posted(state, venue["id"]), now)
    never_tried = elapsed is None
    return (0 if never_tried else 1, -(elapsed or 0.0))


def due_venues(state: dict, now: datetime | None = None,
               venues: list | None = None, limit: int = MAX_SUGGESTIONS) -> list:
    """Venues that may be posted to now, best first, capped at ``limit``."""
    now = now or datetime.now(timezone.utc)
    venues = catalogue.postable(venues if venues is not None else catalogue.load())
    due = [v for v in venues if is_due(v, state, now)]
    due.sort(key=lambda v: _priority(v, state, now))
    return due[:limit]


def waiting_venues(state: dict, now: datetime | None = None,
                   venues: list | None = None) -> list:
    """Venues still cooling down, soonest first, with days remaining.

    Surfaced rather than hidden so that "nothing to do today" is
    distinguishable from "the catalogue is empty and the rotation is
    silently broken".
    """
    now = now or datetime.now(timezone.utc)
    venues = catalogue.postable(venues if venues is not None else catalogue.load())
    rows = [(v, cooldown_remaining(v, state, now))
            for v in venues if not is_due(v, state, now)]
    rows.sort(key=lambda r: r[1])
    return rows
