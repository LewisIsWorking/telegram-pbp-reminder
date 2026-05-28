"""
Per-topic pinned queue post/update/delete loop.

Called once per hourly run from scheduled/queue_reminder.py.
For each physical PBP topic thread with unreplied entries, maintains a
pinned queue message scoped to only that thread's entries.

Multi-topic campaigns (e.g. C06 Kibwe with PBP + COMBAT threads) each get
their own pinned queue in the correct thread, not everything posted to the
canonical pid thread.

A single thread's queue may overflow Telegram's 4096-char limit and be
sent as multiple messages. Every message ID is tracked so the entire
previous batch can be deleted before the next one is posted — slot
schema lives in ``posting.SinglePin``; sending/pinning lives in
``posting.post_batch``.

State per canonical campaign pid in data/state/queues/{pid}.json:
  topic_queues: {thread_id: {msg_ids: [int, ...], fingerprint, ...}}
  topic_msg_id, topic_fingerprint — legacy fields, migrated on first run
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


def _group_id_for(config: dict, pid: str) -> int:
    """Return the Telegram group_id for a campaign."""
    pair = get_pair(config, pid)
    return pair.get("group_id", config["group_id"]) if pair else config["group_id"]  # pragma: no cover


def _migrate_legacy(cq: dict, group_id: int) -> None:
    """Migrate old top-level topic_msg_id/topic_fingerprint into topic_queues.

    Tries to delete the stale message so it doesn't linger in the chat.
    Safe to call multiple times — no-ops if already migrated.
    """
    old_msg_id = cq.get("topic_msg_id")
    if old_msg_id is None:
        return
    tg.delete_message(group_id, old_msg_id)
    cq["topic_msg_id"] = None
    cq["topic_fingerprint"] = ""


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
    if fingerprint == slot.get("fingerprint", "") and not existing.is_empty:
        return  # No change — skip

    # If a "All caught up!" message lingers from a prior clear cycle, drop
    # it before posting the new queue so the topic doesn't accumulate stale
    # caught-up notices.
    prev_caught_up = slot.get("caught_up_msg_id")
    if prev_caught_up:
        if not tg.delete_message(group_id, prev_caught_up):
            queue_pending_deletes(slot, [prev_caught_up])
        slot["caught_up_msg_id"] = None

    # Clear legacy pins if slot has no tracked IDs (pre-tracking messages).
    # Otherwise delete the previous batch so the topic only ever shows the
    # freshest queue. A failed delete is parked in pending_delete and
    # retried on the next run rather than being abandoned — that
    # abandonment was the 2026-05-28 C01 orphan (see L28).
    if existing.is_empty:
        tg.unpin_all_messages(group_id, int(thread_id))
    else:
        if existing.pin_id is not None:
            tg.unpin_message(group_id, existing.pin_id)
        failed = existing.delete_all(group_id)
        if failed:
            queue_pending_deletes(slot, failed)
            print(f"Topic queue prev-delete queued for retry: "
                  f"thread={thread_id} undeleted={failed}")

    chunks = format_topic_queue(entries, now)
    new_batch = post_batch(group_id, int(thread_id), chunks,
                           pin=True, disable_notification=False)
    if new_batch is not None:
        SinglePin.write_batch(slot, new_batch, fingerprint)
        print(f"Topic queue posted: thread={thread_id} "
              f"entries={len(entries)} chunks={len(chunks)}")


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


def _threads_from_scanned(scanned: dict) -> dict[str, tuple[str, list]]:
    """Split scanned entries by physical thread_id.

    Returns {thread_id: (canonical_pid, entries_for_this_thread)}.
    Multi-topic campaigns produce one entry per active thread.
    """
    result: dict[str, tuple[str, list]] = {}
    for pid, data in scanned.items():
        by_thread: dict[str, list] = {}
        for entry in data["entries"]:
            tid = entry.get("thread_id", pid)
            by_thread.setdefault(tid, []).append(entry)
        for tid, entries in by_thread.items():
            result[tid] = (pid, entries)
    return result


def post_topic_queues(config: dict, scanned: dict, now: datetime,
                      *, state: dict | None = None) -> None:
    """Post/update/clear per-thread pinned queues. ``state`` enables caught-up roster tagging via per_topic_caught_up."""
    active_threads = _threads_from_scanned(scanned)

    # Active threads — post or refresh
    for thread_id, (pid, entries) in active_threads.items():
        group_id = _group_id_for(config, pid)
        cq = _load(pid)
        _migrate_legacy(cq, group_id)
        queues = cq.setdefault("topic_queues", {})
        slot = queues.setdefault(thread_id, empty_slot())
        _post_thread_queue(group_id, thread_id, slot, entries, now)
        _save(pid, cq)
        time.sleep(1)

    # Inactive threads — clear any stale pins
    for pid in _all_pids():
        cq = _load(pid)
        group_id = _group_id_for(config, pid)
        _migrate_legacy(cq, group_id)
        queues = cq.get("topic_queues", {})
        changed = False
        for thread_id, slot in queues.items():
            if thread_id not in active_threads and (
                    slot_msg_ids(slot) or slot.get("pending_delete")):
                _clear_thread_queue(group_id, thread_id, slot,
                                    pid=pid, state=state, config=config)
                changed = True
                time.sleep(1)
        if changed or cq.get("topic_msg_id") is not None:
            _save(pid, cq)


# The per-topic-queue schema migration (``_migrate_legacy`` above) is
# registered in the central migration registry from a sibling module,
# imported here so registration runs whenever this poster is imported
# (the migration-registry test triggers it by importing this module).
from scheduled import topic_queue_migration  # noqa: F401, E402
