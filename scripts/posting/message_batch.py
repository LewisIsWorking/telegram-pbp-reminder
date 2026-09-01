"""
A single batch of Telegram messages forming one logical post.

A 'batch' is one or more chunks (messages) that were sent as part of a
single post — typically because the formatted text exceeded Telegram's
4096-char limit and had to be split. The chunks share a lifecycle: they
were posted together and they are deleted together.

The batch optionally tracks which chunk was *pinned* so a caller that
needs to unpin before re-pinning can find that ID without rescanning
the chunks.

Persistence is via ``to_dict`` / ``from_dict``. The on-disk shape is::

    {"msg_ids": [int, ...], "pin_id": int | null}

This is the same shape used historically by ``gm_queue_history`` and
``topic_queue_state``, so existing state files migrate transparently.
"""

from dataclasses import dataclass

import telegram as tg


@dataclass
class MessageBatch:
    """Group of message IDs that share a posting lifecycle.

    Attributes:
        msg_ids: All message IDs that were sent in this batch, in send
            order. The first ID is conventionally the pinned message
            but this class does not enforce that — callers decide.
        pin_id: The pinned message ID, if any. ``None`` for unpinned
            batches. Often equal to ``msg_ids[0]`` but tracked
            separately so a batch can be re-pinned to a different
            chunk if desired.
    """
    msg_ids: list[int]
    pin_id: int | None = None

    @property
    def is_empty(self) -> bool:
        """True when this batch has no message IDs (nothing to delete)."""
        return not self.msg_ids

    def delete_all(self, group_id: int) -> list[int]:
        """Attempt to delete every message; return IDs whose delete failed.

        Telegram's ``deleteMessage`` returns False for permission errors,
        messages older than 48h without admin delete rights, etc. Those
        IDs are surfaced here so the caller can keep this batch alive
        and retry on the next run rather than silently orphaning the
        Telegram message.

        An empty return list means every delete succeeded.
        """
        failed: list[int] = []
        for mid in self.msg_ids:
            if not tg.delete_message(group_id, mid):
                failed.append(mid)
        return failed

    def edit_all(self, group_id: int, chunks: list[str]) -> bool:
        """Rewrite this batch in place. True if every chunk was edited.

        ⭐⭐ **Editing has no 48-hour limit. Deleting does.** That
        asymmetry is the whole reason this exists: once a tracked message
        is past the wall, delete-and-repost is guaranteed to strand it,
        while an edit still works and reuses the same message.

        Added 2026-09-01 after a 15h outage orphaned three more queue
        posts. See ``scheduled/topic_queue_age.can_still_delete``.

        ⚠️ Requires the chunk count to match exactly. A batch of 2 cannot
        become a batch of 3 by editing, and rewriting only the first two
        would silently drop content. Returns False so the caller decides,
        rather than half-doing it.
        """
        if not self.msg_ids or len(chunks) != len(self.msg_ids):
            return False
        for mid, text in zip(self.msg_ids, chunks):
            if not tg.edit_message(group_id, mid, text):
                return False
        return True

    def to_dict(self) -> dict:
        """Serialise to the on-disk dict shape."""
        return {"msg_ids": list(self.msg_ids), "pin_id": self.pin_id}

    @classmethod
    def from_dict(cls, d: dict) -> "MessageBatch":
        """Construct from the on-disk dict shape, tolerating missing keys."""
        return cls(
            msg_ids=list(d.get("msg_ids", [])),
            pin_id=d.get("pin_id"),
        )
