"""Display-time conversion to Lewis's local clock (Belfast).

The bot reasons in UTC everywhere — cron fires in UTC, every gate
compares UTC hours, and all state timestamps are UTC. **None of that
changes.** This module exists purely so posts can be *rendered* in the
timezone the GM actually lives in, because "09:00 UTC" is a small piece
of mental arithmetic every single time you read it.

Belfast is ``Europe/London``: BST (UTC+1) in summer, GMT (UTC+0) in
winter. Using the named zone rather than a fixed offset means the
changeover is handled for us, and the rendered label says which one is
in force.

``tzdata`` is an explicit dependency (installed in the workflow) because
Windows has no system tz database, so ``ZoneInfo`` fails there without
it. If the zone still cannot be loaded for any reason, ``to_local``
degrades to returning the UTC value unchanged rather than raising —
this runs inside the scheduled-jobs loop, and a timezone lookup is never
worth taking the whole run down for.
"""

from datetime import datetime, timezone

DISPLAY_TZ = "Europe/London"

_zone = None
_zone_loaded = False


def _get_zone():
    """Load and cache the display zone. Returns None if unavailable."""
    global _zone, _zone_loaded
    if _zone_loaded:
        return _zone
    _zone_loaded = True
    try:
        from zoneinfo import ZoneInfo
        _zone = ZoneInfo(DISPLAY_TZ)
    except Exception as e:  # ZoneInfoNotFoundError, ImportError, ...
        print(f"[local_time] {DISPLAY_TZ} unavailable ({e}); "
              f"falling back to UTC for display")
        _zone = None
    return _zone


def to_local(dt: datetime) -> datetime:
    """Convert an aware UTC datetime to the display timezone.

    Naive datetimes are assumed UTC. Falls back to the input unchanged
    when the zone is unavailable.
    """
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    zone = _get_zone()
    return dt.astimezone(zone) if zone else dt


def tz_label(dt: datetime) -> str:
    """Short label for the converted time — 'BST', 'GMT', or 'UTC'.

    Takes the *converted* datetime so the label always matches the clock
    reading next to it.
    """
    return dt.tzname() or "UTC"


def fmt(dt: datetime, pattern: str = "%H:%M") -> str:
    """Format an aware UTC datetime in local time, with its tz label."""
    local = to_local(dt)
    return f"{local.strftime(pattern)} {tz_label(local)}"
