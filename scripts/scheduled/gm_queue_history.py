"""
Rolling history of recent GM queue posts in the bot topic.

A single queue post may span multiple Telegram messages when the
formatted text exceeds Telegram's 4096-char limit. This module tracks
each post as a *batch* — the full list of message IDs that were
returned by the send loop — and keeps only the most recent
``MAX_KEPT_BATCHES`` batches in the topic.

State shape:
    state["gm_queue_history"] = [
        {"msg_ids": [int, ...], "pin_id": int},  # oldest kept batch
        ...,
        {"msg_ids": [int, ...], "pin_id": int},  # newest batch
    ]

When a new batch is appended and the cap is exceeded, the oldest
batches are popped and every message ID inside them is deleted from
Telegram. ``tg.delete_message`` silently ignores already-deleted IDs,
so the eviction is idempotent and safe to retry.
"""

import telegram as tg


# Maximum number of GM queue post batches retained in the bot topic.
# Older batches are deleted on every new post.
MAX_KEPT_BATCHES = 3


def migrate_legacy(state: dict) -> None:
    """Seed ``gm_queue_history`` from the legacy ``last_queue_pin_id`` field.

    Idempotent — if history is already populated this is a no-op. When
    history is empty but the legacy pin exists, a single-message batch
    is synthesised so the legacy pin participates in normal eviction
    rather than lingering forever.
    """
    if state.get("gm_queue_history"):
        return
    legacy_pin = state.get("last_queue_pin_id")
    if legacy_pin:
        state["gm_queue_history"] = [
            {"msg_ids": [legacy_pin], "pin_id": legacy_pin},
        ]
    else:
        state["gm_queue_history"] = []


def append_and_evict(state: dict, group_id: int,
                     msg_ids: list[int], pin_id: int) -> None:
    """Append a new batch and delete every message in any evicted batches.

    Mutates ``state["gm_queue_history"]`` in place. After append, while
    history exceeds ``MAX_KEPT_BATCHES`` the oldest batch is popped and
    each ``msg_id`` inside it is passed to ``tg.delete_message``.

    If any delete in a batch fails, that batch is retained in history
    so it can be retried on the next run rather than orphaning the
    message in Telegram with no path to recovery.
    """
    history = state.setdefault("gm_queue_history", [])
    history.append({"msg_ids": list(msg_ids), "pin_id": pin_id})
    # Try to evict oldest batches; keep any whose deletes did not all succeed
    retained: list[dict] = []
    while len(history) > MAX_KEPT_BATCHES:
        candidate = history.pop(0)
        remaining: list[int] = []
        for mid in candidate.get("msg_ids", []):
            if not tg.delete_message(group_id, mid):
                remaining.append(mid)
        if remaining:
            # Some deletes failed — keep this batch (with only failed IDs)
            # so the next run retries them.
            candidate["msg_ids"] = remaining
            retained.append(candidate)
    # Re-insert retained batches at the front in original order
    for batch in reversed(retained):
        history.insert(0, batch)


def post_and_persist(state: dict, group_id: int, bot_topic: int,
                     msgs: list[str]) -> tuple[bool, int | None]:
    """Send every chunk, pin the first, and roll the history.

    Returns ``(sent, first_msg_id)``. A ``True`` ``sent`` flag means at
    least one chunk was delivered successfully; in that case the
    previous pin (if any) is unpinned, the new first message is pinned,
    and ``state["last_queue_pin_id"]`` plus
    ``state["gm_queue_history"]`` are updated together.
    """
    sent = False
    first_msg_id: int | None = None
    sent_msg_ids: list[int] = []
    for i, msg in enumerate(msgs):
        result = tg.send_message_id(group_id, bot_topic, msg)
        if result:
            sent = True
            sent_msg_ids.append(result)
            if i == 0:
                first_msg_id = result
    if not sent or first_msg_id is None:
        return sent, first_msg_id
    # Migrate BEFORE updating last_queue_pin_id, so any pre-existing
    # legacy pin is preserved as a one-message batch in history rather
    # than being mis-detected as legacy on the next call.
    migrate_legacy(state)
    prev_pin = state.get("last_queue_pin_id")
    if prev_pin:
        tg.unpin_message(group_id, prev_pin)
    tg.pin_message(group_id, first_msg_id)
    state["last_queue_pin_id"] = first_msg_id
    append_and_evict(state, group_id, sent_msg_ids, first_msg_id)
    return sent, first_msg_id
