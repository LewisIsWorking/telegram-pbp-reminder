"""Calendar gating shared by the POTW award and its midweek countdown.

Both posts must agree on what "this week" means, otherwise the Thursday
standings could describe a different window than the Monday award that
follows it. Keeping the week key and the weekday gate in one module makes
that agreement structural rather than a convention two files have to
remember.

Why a week key instead of a rolling interval
--------------------------------------------
POTW used to fire on ``interval_elapsed(last_potw[pid], 7, now)`` — "seven
days since this campaign last posted one". That drifted two ways:

* It fires on the first cron tick *at or after* the 7-day mark, and the
  cron ticks at :00 and :30, so the post time crept later every week and
  eventually wandered onto a different day.
* Worse, a week with fewer than ``POTW_MIN_POSTS`` qualifying posts hit
  ``continue`` **without stamping** ``last_potw``. The gate stayed open,
  so the award fired on the first tick after activity resumed — that is
  the "it goes off whenever someone posts" behaviour.

A week key fixes both by construction: the gate is a calendar fact, not a
duration, so it cannot drift, and a skipped week is simply a skipped week.
This mirrors ``scheduled.week_welcome``, which guards on
``state["last_week_welcome"] == week_key``.
"""

from datetime import datetime


def week_key(now: datetime) -> str:
    """Return the ISO year-week key for ``now`` (e.g. ``"2026-W33"``).

    ISO weeks start on Monday, which is the POTW award day, so the award
    and the Thursday countdown that precedes it share one key for the
    whole Monday-to-Sunday block.
    """
    iso_year, iso_week, _ = now.isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def due(now: datetime, weekday: int, post_hour: int) -> bool:
    """True when ``now`` is on ``weekday`` at or after ``post_hour`` UTC.

    ``weekday`` uses ``datetime.weekday()`` numbering (0 = Monday). The
    hour floor stops the post landing at 00:xx just because that is when
    the day rolled over; the same ``hour <`` idiom is used by
    ``week_welcome`` and ``poll_result``.
    """
    return now.weekday() == weekday and now.hour >= post_hour


def already_done(state: dict, key: str, now: datetime) -> bool:
    """True if ``state[key]`` already holds this week's key.

    Idempotency guard: the cron runs twice an hour, so without this every
    tick for the rest of the day would repost. Callers stamp via
    ``mark_done`` only after a successful send.
    """
    return state.get(key) == week_key(now)


def mark_done(state: dict, key: str, now: datetime) -> None:
    """Record that ``key`` has fired for this week."""
    state[key] = week_key(now)
