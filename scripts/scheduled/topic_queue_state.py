"""
Backwards-compat shim around ``posting.SinglePin``.

Historically these four functions defined the slot schema for per-topic
pinned queues; they are now thin wrappers around the equivalent methods
on ``posting.SinglePin``. The public API (function names and signatures)
is preserved so existing callers and tests keep working.

Schema evolution:

  Legacy slot:  {"msg_id": int|None, "fingerprint": str}
                — single message tracked, multi-message posts orphaned.

  Current slot: {"msg_ids": list[int], "fingerprint": str,
                 "last_posted_at": iso8601 str | None}
                — every chunk tracked; replace-on-write semantics.

Migration is implicit: ``slot_msg_ids`` reads either shape, and
``set_slot_msg_ids`` always writes the current shape (dropping legacy
keys). The very first write upgrades any legacy slot.

New code should import from ``posting`` directly. This module exists
only so that existing imports (``from scheduled.topic_queue_state
import …``) keep resolving without churn.
"""

from datetime import datetime, timezone

from posting import MessageBatch, SinglePin

# Telegram refuses to let a bot delete a message older than 48h. The
# per-topic queue replaces its pinned message by delete-then-repost, so
# a tracked message must never be allowed to age past that window or the
# next replacement orphans it. We force a refresh well before 48h.
_REFRESH_AFTER_HOURS = 36


def empty_slot() -> dict:
    """Return a fresh empty slot in the current schema."""
    return SinglePin.empty_slot()


def _msg_age_hours(slot: dict, now: datetime) -> float | None:
    """Hours since the slot's tracked message was last (re)posted.

    Returns None when the slot has no recorded post time (legacy slot
    or first post) or the stored timestamp can't be parsed — callers
    treat None as "age unknown, assume stale" and force a refresh.
    """
    stamp = slot.get("last_posted_at")
    if not stamp:
        return None
    try:
        posted = datetime.fromisoformat(stamp)
    except (ValueError, TypeError):
        return None
    if posted.tzinfo is None:
        posted = posted.replace(tzinfo=timezone.utc)
    return (now - posted).total_seconds() / 3600.0


def can_skip_repost(slot: dict, fingerprint: str, existing: MessageBatch,
                    now: datetime,
                    max_age_hours: float = _REFRESH_AFTER_HOURS) -> bool:
    """Decide whether a per-topic queue re-post can be safely skipped.

    The poster normally skips when the queue content is unchanged (same
    fingerprint). But Telegram refuses to delete a message older than
    48h, so a queue that sits unchanged past that window becomes
    undeletable — and the NEXT real change orphans it (the bot can't
    remove the stale pinned message). This was the C01 orphan Lewis
    reported 2026-05-28: "Unreplied: 5" sat ~2d20h unchanged, then
    "Unreplied: 8" couldn't delete it. See L28.

    To prevent that we refuse to skip once the tracked message crosses
    ``max_age_hours`` (default 36h, comfortably under 48h): the poster
    then re-posts the same content, deleting the still-young old message
    and resetting the age clock.

    Returns True (safe to skip) only when ALL hold:
      * a message is currently tracked (non-empty batch), AND
      * the fingerprint is unchanged, AND
      * the tracked message is younger than ``max_age_hours``.
    """
    if existing.is_empty:
        return False
    if fingerprint != slot.get("fingerprint", ""):
        return False
    age = _msg_age_hours(slot, now)
    if age is None:
        return False  # unknown age → don't skip, force a refresh
    return age < max_age_hours


def slot_msg_ids(slot: dict) -> list[int]:
    """Return the list of message IDs tracked in this slot.

    Reads ``msg_ids`` if present (current schema). Falls back to a
    single-element list synthesised from the legacy ``msg_id`` field.
    Returns an empty list when neither is set.
    """
    return SinglePin.read_batch(slot).msg_ids


def set_slot_msg_ids(slot: dict, msg_ids: list[int],
                     fingerprint: str) -> None:
    """Store a new batch's message IDs and fingerprint in the slot.

    Drops the legacy ``msg_id`` key if present so the slot is fully
    migrated to the current schema after the first write. Stamps
    ``last_posted_at`` to the current UTC time.
    """
    pin_id = msg_ids[0] if msg_ids else None
    batch = MessageBatch(msg_ids=list(msg_ids), pin_id=pin_id)
    SinglePin.write_batch(slot, batch, fingerprint)


def clear_slot(slot: dict) -> None:
    """Reset the slot — call after deleting all tracked messages."""
    SinglePin.clear(slot)
