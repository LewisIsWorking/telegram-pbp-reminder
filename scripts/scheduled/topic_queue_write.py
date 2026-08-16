"""Posting and clearing one topic's queue message.

Extracted from ``scheduled/topic_queue_poster.py`` on 2026-08-15, which
had reached 207 lines. These two are the per-thread write path;
``topic_queue_poster`` keeps the orchestration that decides which
threads need touching at all.
"""

import time
from datetime import datetime

import telegram as tg
from commands.queue_io import load as _load, save as _save, all_pids as _all_pids
from commands.topic_queue_format import format_topic_queue, build_topic_fingerprint
from helpers_pkg.campaigns import get_pair
from posting import SinglePin, post_batch
from scheduled.per_topic_caught_up import build_caught_up_text
from scheduled.topic_queue_state import (slot_msg_ids, empty_slot,
                                         queue_pending_deletes,
                                         retry_pending_deletes)
from scheduled.topic_queue_state import normalise_queue_keys as _normalise_queue_keys
from scheduled.topic_queue_age import batch_is_stale, caught_up_is_stale



def _post_thread_queue(group_id: int, thread_id: str,
                       slot: dict, entries: list, now: datetime) -> None:
    """Post or refresh the pinned queue for one physical thread.

    slot is a mutable dict in either schema (legacy ``msg_id`` or
    current ``msg_ids``). Updated in place to the current schema on
    every successful write. Sending and pinning are delegated to
    ``posting.post_batch``; the existing tracked batch (if any) is
    deleted first via ``MessageBatch.delete_all``.
    """
    fingerprint = build_topic_fingerprint(entries)
    # Retry deleting anything a previous run failed to remove, every run,
    # before deciding whether to skip — so lingering orphans get swept
    # even when the queue content hasn't changed. See L28.
    retry_pending_deletes(slot, group_id)
    existing = SinglePin.read_batch(slot)
    unchanged = fingerprint == slot.get("fingerprint", "")
    if unchanged and not existing.is_empty and not batch_is_stale(slot, now):
        return  # No change and still young enough to delete later — skip

    # If a "All caught up!" message lingers from a prior clear cycle, drop
    # it before posting the new queue so the topic doesn't accumulate stale
    # caught-up notices.
    prev_caught_up = slot.get("caught_up_msg_id")
    if prev_caught_up:
        if not tg.delete_message(group_id, prev_caught_up):
            queue_pending_deletes(slot, [prev_caught_up])
        slot["caught_up_msg_id"] = None

    # Delete the previous batch so the topic only ever shows the freshest
    # queue, unpinning the bot's own pin first. A failed delete is parked in
    # pending_delete and retried on the next run rather than being abandoned —
    # that abandonment was the 2026-05-28 C01 orphan (see L28).
    #
    # When the slot has no tracked IDs there is nothing of *ours* to unpin, so
    # we skip straight to posting. We deliberately do NOT call
    # unpinAllChatMessages here: that endpoint clears pins across the *entire
    # group* (it ignores the message_thread_id arg), wiping GM pins the bot
    # never created. Only ever unpin a specific ID the bot itself pinned.
    if not existing.is_empty:
        if existing.pin_id is not None:
            tg.unpin_message(group_id, existing.pin_id)
        failed = existing.delete_all(group_id)
        if failed:
            queue_pending_deletes(slot, failed)
            print(f"Topic queue prev-delete queued for retry: "
                  f"thread={thread_id} undeleted={failed}")

    chunks = format_topic_queue(entries, now)
    # An age-only refresh must not ping the players — the content they
    # already saw has not changed, and a silent repost is the price of
    # keeping the message deletable. A real content change notifies as
    # it always did.
    new_batch = post_batch(group_id, int(thread_id), chunks,
                           pin=True, disable_notification=unchanged)
    if new_batch is not None:
        SinglePin.write_batch(slot, new_batch, fingerprint)
        print(f"Topic queue {'refreshed (age)' if unchanged else 'posted'}: "
              f"thread={thread_id} entries={len(entries)} "
              f"chunks={len(chunks)}")


def sweep_aged_caught_up(group_id: int, slot: dict, now: datetime) -> bool:
    """Remove a caught-up notice before it ages out of reach. True if changed.

    A per-thread "All caught up" notice is only deleted when that thread
    next has something to queue. In a quiet campaign that can be weeks,
    by which point the message is past Telegram's 48h wall and the delete
    is unwinnable — the same defect as the queue post itself, on a path
    nobody had looked at.

    Found 2026-08-16 by ``maintenance/audit_orphans.py``, which asks
    Telegram directly instead of trusting our own records. The offline
    detector could not see these: ``pin_audit`` only timestamps messages
    the bot *pinned*, and caught-up notices are never pinned. **15 of the
    28 confirmed orphans were caught-up notices** — 169063, 169383,
    170384 and 171632 among them.

    We delete rather than refresh. A refresh would repost "All caught up"
    into a quiet topic every 36 hours forever; the notice has done its
    job long before then, and an absent notice is the correct end state.

    A slot with no ``caught_up_at`` predates this field. It gets one
    attempt now rather than a 36h wait, because if it is already old the
    wait cannot help and if it is young the attempt succeeds.
    """
    if not caught_up_is_stale(slot, now):
        return False
    mid = slot["caught_up_msg_id"]
    if not tg.delete_message(group_id, mid):
        queue_pending_deletes(slot, [mid])
    slot["caught_up_msg_id"] = None
    slot["caught_up_at"] = None
    return True


def _clear_thread_queue(group_id: int, thread_id: str, slot: dict,
                        *, pid: str, state: dict | None,
                        config: dict, now: datetime) -> None:
    """Send caught-up message and remove every stale pinned message.

    Slot is reset via ``SinglePin.clear``; the new caught-up message
    ID is stored on the slot, with ``now`` as its timestamp, so it can be
    removed on age by ``sweep_aged_caught_up`` rather than waiting for a
    next cycle that may be weeks away. ``now`` is required rather than
    defaulted: a caught-up notice with no timestamp is exactly the state
    that orphaned 15 messages, so there must be no way to create one by
    forgetting an argument.
    Caught-up message body comes from
    ``scheduled.per_topic_caught_up.build_caught_up_text``.
    """
    retry_pending_deletes(slot, group_id)
    existing = SinglePin.read_batch(slot)
    if existing.is_empty:
        return  # nothing tracked; any pending zombies were retried above
    # Delete the previous caught-up notice (if any) so we don't pile them up.
    prev_caught_up = slot.get("caught_up_msg_id")
    if prev_caught_up and not tg.delete_message(group_id, prev_caught_up):
        queue_pending_deletes(slot, [prev_caught_up])
    new_caught_up = tg.send_message_id(
        group_id, int(thread_id), build_caught_up_text(pid, state, config))
    # Unpin only the first message (the pinned one); delete every tracked id.
    if existing.pin_id is not None:
        tg.unpin_message(group_id, existing.pin_id)
    failed = existing.delete_all(group_id)
    if failed:
        queue_pending_deletes(slot, failed)
    SinglePin.clear(slot)
    slot["caught_up_msg_id"] = new_caught_up
    # Stamped so sweep_aged_caught_up can remove it while it is still
    # removable. Without a timestamp the notice's age is unknowable and
    # it silently becomes permanent — that is how 15 of them orphaned.
    slot["caught_up_at"] = now.isoformat() if now else None
    print(f"Topic queue cleared: thread={thread_id}")
