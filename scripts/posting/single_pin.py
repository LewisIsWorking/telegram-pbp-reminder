"""
Replace-only single-pin slot for per-thread pinned queues.

Where ``QueueHistory`` retains the last N batches, ``SinglePin``
retains just one — the current pin in a topic. When a new batch is
posted, the previous batch is deleted and the new one becomes current.

Used by per-campaign topic queues, where only the latest queue should
be visible in each PBP/COMBAT thread.

Like ``QueueHistory``, state is owned by the caller. The slot dict
shape (kept stable for backwards compatibility with existing state
files) is::

    {
      "msg_ids": [int, ...],          # current batch
      "fingerprint": str,             # change-detection key
      "last_posted_at": iso8601 str,  # when the current batch was sent
    }

Legacy slots may also have ``msg_id`` (single int) instead of
``msg_ids``; ``read_batch`` tolerates both.
"""

from datetime import datetime, timezone

from posting.message_batch import MessageBatch


class SinglePin:
    """Manage the single 'current pin' batch for one topic thread.

    All methods are static — the class is a namespace, not a stateful
    object. The slot dict is the source of truth; methods read from
    and write to it in place.
    """

    @staticmethod
    def empty_slot() -> dict:
        """Fresh slot in the current schema (no batch tracked)."""
        return {"msg_ids": [], "fingerprint": "", "last_posted_at": None}

    @staticmethod
    def read_batch(slot: dict) -> MessageBatch:
        """Decode the slot's tracked batch, tolerating legacy shapes.

        Reads ``msg_ids`` if present (current schema). Otherwise falls
        back to ``msg_id`` (legacy single-message schema) and
        synthesises a one-element batch. Returns an empty batch when
        neither field is set.
        """
        if slot.get("msg_ids"):
            return MessageBatch(msg_ids=list(slot["msg_ids"]),
                                pin_id=slot["msg_ids"][0])
        legacy = slot.get("msg_id")
        if legacy:
            return MessageBatch(msg_ids=[legacy], pin_id=legacy)
        return MessageBatch(msg_ids=[], pin_id=None)

    @staticmethod
    def write_batch(slot: dict, batch: MessageBatch,
                    fingerprint: str) -> None:
        """Persist a freshly-posted batch into the slot in place.

        Updates ``msg_ids``, ``fingerprint``, and stamps
        ``last_posted_at`` to the current UTC time. Drops the legacy
        ``msg_id`` key so the slot is fully migrated to the current
        schema after the first write.
        """
        slot["msg_ids"] = list(batch.msg_ids)
        slot["fingerprint"] = fingerprint
        slot["last_posted_at"] = datetime.now(timezone.utc).isoformat()
        slot.pop("msg_id", None)

    @staticmethod
    def clear(slot: dict) -> None:
        """Reset the slot to empty after deleting its tracked messages."""
        slot["msg_ids"] = []
        slot["fingerprint"] = ""
        slot["last_posted_at"] = None
        slot.pop("msg_id", None)
