"""
Rolling history of recent GM queue posts in the bot topic.

A single queue post may span multiple Telegram messages when the
formatted text exceeds Telegram's 4096-char limit. This module tracks
each post as a *batch* — the full list of message IDs that were
returned by the send loop — and keeps only the most recent
``MAX_KEPT_BATCHES`` batches in the topic.

State shape (unchanged for backwards compatibility)::

    state["gm_queue_history"] = [
        {"msg_ids": [int, ...], "pin_id": int},  # oldest kept batch
        ...,
        {"msg_ids": [int, ...], "pin_id": int},  # newest batch
    ]

The actual batch and history primitives now live in ``posting``;
this module is the GM-queue-specific orchestrator: legacy migration
from ``last_queue_pin_id``, unpin-previous-then-pin-new ordering, and
the public ``post_and_persist`` entry point.

When a new batch is appended and the cap is exceeded, the oldest
batches are deleted from Telegram. Failed deletes keep the batch in
history so the next run retries — see ``posting.queue_history``.
"""

import telegram as tg
from posting import QueueHistory, post_batch


# Maximum number of GM queue post batches retained in the bot topic.
# Older batches are deleted on every new post.
#
# Set to 1 (2026-05-10): Lewis wants only the newest GM queue visible
# at any time, matching the per-topic queue UX (single pinned message
# per thread). Multi-chunk queues (msg_ids = [a, b, c]) are still
# evicted as atomic units — ``MessageBatch.delete_all`` iterates every
# chunk in the batch — so a 3-chunk queue evicting another 3-chunk
# queue produces 3 delete_message calls, all of them safeguard-gated.
MAX_KEPT_BATCHES = 1

_history = QueueHistory(max_kept=MAX_KEPT_BATCHES)


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

    Mutates ``state["gm_queue_history"]`` in place. Delegates the
    rolling-window logic (and retry-on-failure semantics) to
    ``posting.QueueHistory``; this function only handles the dict-list
    boundary and in-place mutation expected by the rest of the codebase.
    """
    raw = state.setdefault("gm_queue_history", [])
    batches = QueueHistory.from_dicts(raw)
    from posting import MessageBatch
    new = MessageBatch(msg_ids=list(msg_ids), pin_id=pin_id)
    updated = _history.append_with_retry(batches, new, group_id)
    raw[:] = QueueHistory.to_dicts(updated)


def post_and_persist(state: dict, group_id: int, bot_topic: int,
                     msgs: list[str]) -> tuple[bool, int | None]:
    """Send every chunk, pin the first, and roll the history.

    Returns ``(sent, first_msg_id)``. A ``True`` ``sent`` flag means at
    least one chunk was delivered successfully; in that case the
    previous pin (if any) is unpinned, the new first message is pinned,
    and ``state["last_queue_pin_id"]`` plus
    ``state["gm_queue_history"]`` are updated together.

    Note: ``post_batch`` already pins the first chunk, so we don't
    re-pin here. We do still unpin the previous pin (if any) so the
    bot topic doesn't accumulate stale pin notifications.
    """
    batch = post_batch(group_id, bot_topic, msgs,
                       pin=True, disable_notification=False)
    if batch is None:
        return False, None

    # Migrate BEFORE updating last_queue_pin_id, so any pre-existing
    # legacy pin is preserved as a one-message batch in history rather
    # than being mis-detected as legacy on the next call.
    migrate_legacy(state)
    prev_pin = state.get("last_queue_pin_id")
    if prev_pin:
        tg.unpin_message(group_id, prev_pin)
    state["last_queue_pin_id"] = batch.pin_id
    append_and_evict(state, group_id, batch.msg_ids, batch.pin_id)
    return True, batch.pin_id
