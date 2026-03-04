"""
Helpers: time_utils.
"""

import re
from datetime import datetime, timezone, timedelta




def hours_since(now: datetime, then: datetime) -> float:
    """Return fractional hours between two datetimes."""
    return (now - then).total_seconds() / 3600


def days_since(now: datetime, then: datetime) -> float:
    """Return fractional days between two datetimes."""
    return (now - then).total_seconds() / 86400

def interval_elapsed(last_iso: str | None, interval_days: float, now: datetime) -> bool:
    """Return True if enough time has passed since last_iso, or if last_iso is None."""
    if not last_iso:
        return True
    return days_since(now, datetime.fromisoformat(last_iso)) >= interval_days



def timestamps_in_window(raw_timestamps: list[str], after: datetime,
                         before: datetime | None = None) -> list[datetime]:
    """Parse ISO timestamp strings and return those within the time window.

    Returns datetimes where: after <= dt (and dt < before, if given).
    """
    results = []
    for ts in raw_timestamps:
        dt = datetime.fromisoformat(ts)
        if dt >= after and (before is None or dt < before):
            results.append(dt)
    return results



def avg_gap_hours(sorted_times: list[datetime]) -> float | None:
    """Return average gap in hours between sorted datetimes, or None if < 2 entries."""
    if len(sorted_times) < 2:
        return None
    gaps = [(sorted_times[i] - sorted_times[i - 1]).total_seconds() / 3600
            for i in range(1, len(sorted_times))]
    return sum(gaps) / len(gaps)

# ------------------------------------------------------------------ #
#  Away / absence tracking
# ------------------------------------------------------------------ #
def is_away(state: dict, pid: str, user_id: str, now: datetime | None = None) -> dict | None:
    """Return the away record if player is currently away, or None.

    Auto-expires timed absences (returns None and cleans up state).
    """
    now = now or datetime.now(timedelta(0))  # UTC
    key = f"{pid}:{user_id}"
    record = state.get("away", {}).get(key)
    if not record:
        return None
    # Check expiry
    until = record.get("until")
    if until:
        try:
            until_dt = datetime.fromisoformat(until)
            if now >= until_dt:
                del state["away"][key]
                return None
        except (TypeError, ValueError):
            pass
    return record



def parse_away_duration(text: str, now: datetime) -> tuple[datetime | None, str]:
    """Parse '/away' arguments into (until_datetime_or_None, reason).

    Supports: '3 days reason', '2 weeks reason', 'until March 5 reason',
    or just 'reason' (indefinite).
    """
    text = text.strip()
    if not text:
        return None, "No reason given"

    import re

    # "N days/weeks" pattern
    m = re.match(r"^(\d+)\s*(days?|weeks?)\s*(.*)", text, re.IGNORECASE)
    if m:
        n = int(m.group(1))
        unit = m.group(2).lower()
        reason = m.group(3).strip() or "Away"
        if unit.startswith("week"):
            delta = timedelta(weeks=n)
        else:
            delta = timedelta(days=n)
        return now + delta, reason

    # "until <date>" pattern (best-effort)
    m = re.match(r"^until\s+(.+?)(?:\s+(?:because|for|:)\s*(.*))?$", text, re.IGNORECASE)
    if m:
        date_str = m.group(1).strip()
        reason = (m.group(2) or "Away").strip()
        try:
            # Try ISO format first
            dt = datetime.fromisoformat(date_str)
            return dt, reason
        except ValueError:
            pass
        # Try "Month Day" or "Month Day YYYY"
        for fmt in ("%B %d", "%B %d %Y", "%b %d", "%b %d %Y", "%d %B", "%d %b"):
            try:
                dt = datetime.strptime(date_str, fmt)
                if dt.year == 1900:  # no year provided
                    dt = dt.replace(year=now.year)
                    if dt < now:
                        dt = dt.replace(year=now.year + 1)
                return dt, reason
            except ValueError:
                continue
        # Couldn't parse date — treat whole thing as reason
        return None, text

    # No duration pattern matched — indefinite with the whole text as reason
    return None, text
