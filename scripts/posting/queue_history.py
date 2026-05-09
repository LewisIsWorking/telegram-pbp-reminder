"""
Rolling window of recent message batches with retry-on-failure eviction.

A ``QueueHistory`` retains the most recent ``max_kept`` batches in a
Telegram topic. When a new batch is appended and the cap is exceeded,
older batches are evicted — every message ID inside an evicted batch is
deleted from Telegram.

Eviction is *not* fire-and-forget. If any delete returns False
(permission, age, transient API error), the batch is retained with
only its failed IDs so the next run can retry. This means a persistent
delete failure causes temporary overflow rather than silently orphaning
a message in the topic.

State is owned by the caller — this class does not read or write any
state file. It operates on plain ``list[MessageBatch]`` values that the
caller persists.
"""

from posting.message_batch import MessageBatch


class QueueHistory:
    """Append-and-evict policy for a rolling list of pinned posts.

    Attributes:
        max_kept: Maximum number of batches to retain in normal
            operation. Failed-delete batches may temporarily push the
            count above this until their messages are successfully
            removed.
    """

    def __init__(self, max_kept: int = 3):
        self.max_kept = max_kept

    @staticmethod
    def from_dicts(dicts: list[dict]) -> list[MessageBatch]:
        """Materialise a list of dict-shape batches into ``MessageBatch``."""
        return [MessageBatch.from_dict(d) for d in dicts]

    @staticmethod
    def to_dicts(batches: list[MessageBatch]) -> list[dict]:
        """Serialise a list of batches back to the on-disk dict shape."""
        return [b.to_dict() for b in batches]

    def append_with_retry(self, batches: list[MessageBatch],
                          new: MessageBatch,
                          group_id: int) -> list[MessageBatch]:
        """Append ``new`` and evict overflow with retry semantics.

        Returns a fresh list. The input is not mutated. Each candidate
        for eviction is asked to delete its messages; if any deletes
        fail, the batch is retained with only the failed IDs so the
        next call can retry. Retained batches are re-inserted at the
        front in their original order.

        Args:
            batches: Existing batches, oldest first.
            new: The freshly-posted batch to append at the tail.
            group_id: Telegram group ID for delete calls.
        """
        working: list[MessageBatch] = list(batches) + [new]
        retained: list[MessageBatch] = []
        while len(working) > self.max_kept:
            candidate = working.pop(0)
            failed = candidate.delete_all(group_id)
            if failed:
                candidate.msg_ids = failed
                retained.append(candidate)
        # Put retained batches back at the front, preserving their
        # original relative order (oldest first).
        for batch in reversed(retained):
            working.insert(0, batch)
        return working
