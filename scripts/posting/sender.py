"""
Send a sequence of chunks as a single batch and (optionally) pin the
first successfully-delivered chunk.

This is the inverse of ``MessageBatch.delete_all``: where that method
turns a batch into a list of failed IDs, this function turns a list of
chunks into a batch (or ``None`` if every send failed).

The function exists in its own module — rather than as a static method
on ``MessageBatch`` — so the dataclass stays free of side-effecting
imports beyond the deletion helper. ``post_batch`` is the only place in
the package that knows how to *create* a batch by talking to Telegram.
"""

import telegram as tg
from posting.message_batch import MessageBatch


def post_batch(group_id: int, thread_id: int | None,
               chunks: list[str], *, pin: bool = True,
               disable_notification: bool = False) -> MessageBatch | None:
    """Send every chunk in order; return a ``MessageBatch`` describing
    the result, or ``None`` if every send failed.

    Args:
        group_id: Telegram chat/group ID.
        thread_id: Optional message thread (topic) ID. ``None`` for
            non-forum chats.
        chunks: Pre-formatted message strings, in the order they should
            appear in the topic. Each chunk must already be under
            Telegram's 4096-char limit; this function does not split.
        pin: When True, the first successfully-sent chunk is pinned.
        disable_notification: Forwarded to ``tg.pin_message``. Default
            ``False`` matches Telegram's "pin and notify" behaviour
            historically used by the GM queue and per-topic queues.

    Returns:
        A ``MessageBatch`` whose ``msg_ids`` lists every chunk that was
        delivered (in send order), and whose ``pin_id`` is the pinned
        chunk's ID (or ``None`` when ``pin`` is False or every send
        failed). Returns ``None`` when not a single chunk was delivered;
        callers can treat ``None`` as "post failed entirely".
    """
    msg_ids: list[int] = []
    for chunk in chunks:
        mid = tg.send_message_id(group_id, thread_id, chunk)
        if mid:
            msg_ids.append(mid)
    if not msg_ids:
        return None
    pin_id = msg_ids[0] if pin else None
    if pin_id is not None:
        tg.pin_message(group_id, pin_id,
                       disable_notification=disable_notification)
    return MessageBatch(msg_ids=msg_ids, pin_id=pin_id)
