"""Clearing a thread's queue, and retiring its caught-up notice.

Extracted from topic_queue_write.py on 2026-09-01 at 222 lines, when
the past-the-wall edit path landed. That module owns POSTING a queue;
this one owns taking it away again. Both obey the same rule, which is
the reason the split is here and not elsewhere: **never attempt a delete
that cannot win.**
"""

import telegram as tg
from posting import SinglePin
from scheduled.per_topic_caught_up import build_caught_up_text
from scheduled.topic_queue_age import can_still_delete, caught_up_is_stale
from scheduled.topic_queue_state import queue_pending_deletes, retry_pending_deletes
from datetime import datetime


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

    # ⛔⛔ Same rule as _post_thread_queue: never attempt a delete that
    # cannot win. Here it matters even more, because this is the
    # transition that produced 15 of the 28 confirmed orphans.
    #
    # ⭐ Past the wall, the queue message BECOMES the caught-up notice by
    # edit. One message per thread, reused forever, nothing abandoned.
    # It stays pinned, which is arguably better than the unpin-delete-
    # repost churn anyway.
    caught_up_text = build_caught_up_text(pid, state, config)
    if not can_still_delete(slot, now):
        if existing.edit_all(group_id, [caught_up_text]):
            kept = existing.msg_ids[0]
            SinglePin.clear(slot)
            slot["caught_up_msg_id"] = kept
            # ⚠️ NOT `now`. This notice is as old as the message it was
            # edited from, and pretending otherwise would tell
            # sweep_aged_caught_up it has 36 hours to delete something
            # it can never delete.
            slot["caught_up_at"] = None
            print(f"Topic queue EDITED into a caught-up notice (past the "
                  f"48h wall): thread={thread_id} msg={kept}")
            return
        print(f"Topic queue past the wall and cannot be edited into one "
              f"message ({len(existing.msg_ids)} chunks): thread={thread_id}. "
              f"Only a human can remove the old batch.")

    # Delete the previous caught-up notice (if any) so we don't pile them up.
    prev_caught_up = slot.get("caught_up_msg_id")
    if prev_caught_up and not tg.delete_message(group_id, prev_caught_up):
        queue_pending_deletes(slot, [prev_caught_up])
    new_caught_up = tg.send_message_id(group_id, int(thread_id), caught_up_text)
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
