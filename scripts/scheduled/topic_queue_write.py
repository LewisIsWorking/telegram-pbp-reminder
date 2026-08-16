"""Posting and clearing one topic's queue message.

Extracted from ``scheduled/topic_queue_poster.py`` on 2026-08-15, which
had reached 207 lines. These two are the per-thread write path;
``topic_queue_poster`` keeps the orchestration that decides which
threads need touching at all.
"""

import time
from datetime import datetime, timedelta, timezone

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



# ⭐ Telegram will not let a bot delete its own message once it is more
# than 48 hours old — admin rights and can_delete_messages do NOT lift
# this. Measured against the live group on 2026-08-16: of the deletes in
# pin_audit_log, **15 of 15 attempted past the line still exist** and
# **12 of 12 attempted inside it are gone**. No exceptions either way.
#
# That is what orphaned the C06 "Unreplied: 2" post from 2026-08-03. The
# early return below skips the whole write path while the fingerprint is
# unchanged, so in a quiet campaign the pinned queue sat untouched for
# days. By the time a player finally posted and the fingerprint moved,
# the tracked message was already undeletable — the delete was doomed
# before it was ever attempted, and no amount of retrying could win.
#
# So the fix is not at the delete. It is here: never let a tracked
# message get old. Refreshing at 36h keeps every ID the bot is holding
# comfortably inside the window it can still act on, with 12 hours of
# slack for a missed run or an outage.
_MAX_TRACKED_AGE = timedelta(hours=36)


def _batch_is_stale(slot: dict, now: datetime) -> bool:
    """True when the tracked batch is old enough to risk becoming undeletable.

    Returns False when the slot carries no timestamp — an untimestamped
    slot predates ``last_posted_at`` and the next content change will
    rewrite it anyway. Failing closed here would republish every legacy
    slot at once on the first run after deploy.
    """
    stamp = slot.get("last_posted_at")
    if not stamp:
        return False
    try:
        posted = datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        return False
    if posted.tzinfo is None:
        posted = posted.replace(tzinfo=timezone.utc)
    reference = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    return reference - posted > _MAX_TRACKED_AGE


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
    if unchanged and not existing.is_empty and not _batch_is_stale(slot, now):
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


def _clear_thread_queue(group_id: int, thread_id: str, slot: dict,
                        *, pid: str, state: dict | None,
                        config: dict) -> None:
    """Send caught-up message and remove every stale pinned message.

    Slot is reset via ``SinglePin.clear``; the new caught-up message
    ID is stored on the slot so the *next* cycle can delete it.
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
    print(f"Topic queue cleared: thread={thread_id}")
