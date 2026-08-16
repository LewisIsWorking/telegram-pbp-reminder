"""Keeping tracked messages inside Telegram's 48-hour delete window.

⭐ Telegram will not let a bot delete its own message once it is more than
48 hours old. Administrator rights and ``can_delete_messages`` do **not**
lift this. Measured against the live Path Wars group on 2026-08-16:

    deletes attempted OVER 48h after sending:  15 of 15 STILL EXIST
    deletes attempted UNDER it:                 0 of 12 still exist

No exceptions either way. So holding a message ID for longer than that is
not a risk of failure, it is a **loss that has already happened** — the
delete is unwinnable before it is attempted, and no retry can recover it.

That is what orphaned the C06 "Unreplied: 2" post from 2026-08-03. The
poster skips its whole write path while the content fingerprint is
unchanged, so a quiet campaign left its pinned queue untouched for days;
by the time a player posted and the fingerprint moved, the tracked
message was already out of reach.

Extracted from ``topic_queue_write.py`` on 2026-08-16 at 202 lines. The
split is not arbitrary: this module owns one rule — **never hold an ID
longer than you can act on it** — and it applies to every tracked message,
not only the queue batch. The caught-up notice sweep lives here for the
same reason, and 15 of the 28 confirmed orphans were caught-up notices.

⚠️ If you add a new code path that stores a message ID for later deletion,
it belongs on this clock too. Storing an ID means owning its lifetime.
"""

from datetime import datetime, timedelta, timezone

# 36h leaves 12 hours of slack against the 48h wall — enough to absorb a
# missed run, a Telegram outage, or a workflow queued behind others.
MAX_TRACKED_AGE = timedelta(hours=36)


def _parse(stamp) -> datetime | None:
    """Parse an ISO timestamp, assuming UTC when it carries no zone."""
    if not stamp:
        return None
    try:
        parsed = datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def is_past(stamp, now: datetime, limit: timedelta | None = None) -> bool:
    """True when ``stamp`` is older than ``limit`` (default MAX_TRACKED_AGE).

    ⚠️ The default is resolved at CALL time, not bound in the signature.
    A ``limit=MAX_TRACKED_AGE`` default would be captured when this
    function is defined, so monkeypatching the module constant would
    silently have no effect — and the can-fail test that patches it to
    prove this guard works would itself prove nothing.

    Returns False for a missing or unparseable timestamp. That direction
    is deliberate: an untimestamped slot predates the field, and failing
    closed would republish every legacy slot at once on the first run
    after deploy. The callers that cannot tolerate an unknown age handle
    it explicitly rather than relying on this default.
    """
    posted = _parse(stamp)
    if posted is None:
        return False
    ceiling = MAX_TRACKED_AGE if limit is None else limit
    reference = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    return reference - posted > ceiling


def batch_is_stale(slot: dict, now: datetime) -> bool:
    """True when a slot's posted batch is old enough to need replacing."""
    return is_past(slot.get("last_posted_at"), now)


def caught_up_is_stale(slot: dict, now: datetime) -> bool:
    """True when a caught-up notice should be removed while it still can be.

    Unlike ``batch_is_stale`` an untimestamped notice counts as stale.
    The two defaults differ because the consequences do: a batch with no
    timestamp gets rewritten by the next content change anyway, whereas a
    notice with no timestamp is only ever revisited when its thread wakes
    up, which may be never. Treating it as stale gives it one attempt now
    — if it is already old that attempt cannot hurt, and if it is young it
    succeeds.
    """
    if not slot.get("caught_up_msg_id"):
        return False
    stamp = slot.get("caught_up_at")
    if not stamp:
        return True
    return is_past(stamp, now)
