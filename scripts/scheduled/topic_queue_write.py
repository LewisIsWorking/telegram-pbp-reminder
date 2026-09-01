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
from scheduled.topic_queue_age import (batch_is_stale, can_still_delete,
                                       caught_up_is_stale)



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

    chunks = format_topic_queue(entries, now)

    # ⛔⛔ NEVER ATTEMPT A DELETE THAT CANNOT WIN. Past Telegram's 48h
    # wall a delete is not a risk, it is a loss that has already
    # happened, and the old code attempted it anyway. Three more queue
    # posts were stranded that way by the 2026-08-31 outage.
    #
    # ⭐ Editing has no such limit, so a message past the wall is REUSED
    # instead of abandoned. The batch keeps its IDs, its pin and its
    # original send time; only the text changes.
    #
    # ⚠️ last_posted_at is deliberately NOT refreshed here. It records
    # when these IDs were SENT, which is what governs deletability, and
    # an edit does not move that clock. Writing it would make the slot
    # look freshly deletable and put us straight back into doomed
    # deletes. `batch_is_stale` will keep asking for a republish that
    # `can_still_delete` keeps refusing, which is the correct standoff:
    # the message stays current by edit and is never orphaned.
    if not existing.is_empty and not can_still_delete(slot, now):
        if existing.edit_all(group_id, chunks):
            slot["fingerprint"] = fingerprint
            slot["last_edited_at"] = now.isoformat()
            print(f"Topic queue EDITED in place (past the 48h delete wall, "
                  f"so a delete would have orphaned it): thread={thread_id} "
                  f"entries={len(entries)} chunks={len(chunks)}")
            return
        # Chunk count changed, so an edit cannot carry the content. Fall
        # through and post fresh, but do NOT attempt the doomed delete
        # below: the old batch is unreachable either way, and attempting
        # it only adds a failure to the audit log.
        print(f"Topic queue past the wall AND the chunk count changed "
              f"({len(existing.msg_ids)} -> {len(chunks)}): thread={thread_id}. "
              f"Posting fresh; the old batch cannot be removed by anyone "
              f"but a human.")
        SinglePin.clear(slot)
        existing = SinglePin.read_batch(slot)

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


# Clearing a thread's queue lives in topic_queue_clear (extracted
# 2026-09-01 at 222 lines). Re-exported so topic_queue_poster's existing
# import site keeps working.
from scheduled.topic_queue_clear import (  # noqa: E402,F401
    _clear_thread_queue, sweep_aged_caught_up)
