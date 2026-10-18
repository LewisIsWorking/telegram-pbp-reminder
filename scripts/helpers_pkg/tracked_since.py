"""``tracked_since``: the day the bot started (or restarted) seeing a campaign.

Added 2026-10-18 when C11 Dark Pockets came back. It was retired on
2026-07-07 (#22) because the bot had been removed from its group, and the
bot's state still held its last post from 2026-06-29. Re-adding the pair
with nothing else would have made the GM queue read that June post as the
campaign's last activity, so C11 would have looked silent for 100+ days and
taken "Post here next" on every queue until someone posted there.

The months in between are not silence. They are months the bot could not
see. So for a pair carrying ``"tracked_since": "YYYY-MM-DD"``:

* its last post is never older than that day (``clamp_last_post``), so the
  silent clock starts when tracking did; and
* a transcript entry from before that day is never an unreplied message
  (``before_tracking``), so a June post cannot resurface as owed.

The date is midnight UTC. Leave it out for a campaign the bot has always
seen; nothing changes for it.
"""

from datetime import datetime, timezone

KEY = "tracked_since"


def tracked_since(pair: dict) -> datetime | None:
    """The pair's tracking start as midnight UTC, or None if unset or bad."""
    raw = (pair or {}).get(KEY)
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None


def clamp_last_post(pair: dict, last: datetime | None) -> datetime | None:
    """``last`` moved up to the tracking start when it is older than that.

    A campaign with no recorded post at all stays None ("no posts yet"):
    that wording is already honest about a campaign the bot has not seen.
    """
    floor = tracked_since(pair)
    if last is None or floor is None:
        return last
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return max(last, floor)


def before_tracking(pair: dict, timestamp: str) -> bool:
    """True when a transcript stamp ('YYYY-MM-DD HH:MM:SS') predates tracking."""
    floor = (pair or {}).get(KEY)
    return bool(floor) and tracked_since(pair) is not None and timestamp[:10] < floor


def config_issues(pair: dict, label: str) -> list[str]:
    """Validation messages for a malformed ``tracked_since``."""
    raw = pair.get(KEY)
    if raw and tracked_since(pair) is None:
        return [f"ERROR: {label} '{KEY}' must be YYYY-MM-DD format, got '{raw}'"]
    return []
