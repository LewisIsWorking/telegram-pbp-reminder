"""
Slot schema helpers for per-topic pinned queues.

Each physical PBP thread has a *slot* tracking the queue messages
currently pinned in that thread. The slot lives inside a campaign's
``data/state/queues/{pid}.json`` file under the ``topic_queues`` key.

Schema evolution:

  Legacy slot:  {"msg_id": int|None, "fingerprint": str}
                — only the first message of a multi-message post was
                  tracked, so subsequent messages were orphaned when a
                  new batch replaced them.

  Current slot: {"msg_ids": list[int], "fingerprint": str}
                — every message ID returned by the send loop is tracked
                  so the entire previous batch can be deleted before
                  the next one is posted.

Migration is implicit and idempotent: ``slot_msg_ids`` reads from
either shape, and ``set_slot_msg_ids`` writes the new shape and drops
the legacy key on first update.
"""


def empty_slot() -> dict:
    """Return a fresh empty slot in the current schema."""
    return {"msg_ids": [], "fingerprint": "", "last_posted_at": None}


def slot_msg_ids(slot: dict) -> list[int]:
    """Return the list of message IDs tracked in this slot.

    Reads ``msg_ids`` if present (current schema). Falls back to a
    single-element list synthesised from the legacy ``msg_id`` field.
    Returns an empty list when neither is set.
    """
    if slot.get("msg_ids"):
        return list(slot["msg_ids"])
    legacy = slot.get("msg_id")
    return [legacy] if legacy else []


def set_slot_msg_ids(slot: dict, msg_ids: list[int],
                     fingerprint: str) -> None:
    """Store a new batch's message IDs and fingerprint in the slot.

    Drops the legacy ``msg_id`` key if present so the slot is fully
    migrated to the current schema after the first write.
    """
    slot["msg_ids"] = list(msg_ids)
    slot["fingerprint"] = fingerprint
    slot.pop("msg_id", None)
    from datetime import datetime, timezone
    slot["last_posted_at"] = datetime.now(timezone.utc).isoformat()


def clear_slot(slot: dict) -> None:
    """Reset the slot — call after deleting all tracked messages."""
    slot["msg_ids"] = []
    slot["fingerprint"] = ""
    slot["last_posted_at"] = None
    slot.pop("msg_id", None)
