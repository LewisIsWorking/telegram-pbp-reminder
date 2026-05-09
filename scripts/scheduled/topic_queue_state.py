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

from posting import MessageBatch, SinglePin


def empty_slot() -> dict:
    """Return a fresh empty slot in the current schema."""
    return SinglePin.empty_slot()


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
