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
previous batch can be deleted before the next one is posted — see
``scheduled.topic_queue_state`` for the slot schema.

State per canonical campaign pid in data/state/queues/{pid}.json:
  topic_queues: {thread_id: {msg_ids: [int, ...], fingerprint}}
  topic_msg_id, topic_fingerprint — legacy fields, migrated on first run
"""

import time
from datetime import datetime

import telegram as tg
from commands.queue_io import load as _load, save as _save, all_pids as _all_pids
from commands.topic_queue_format import format_topic_queue, build_topic_fingerprint
from helpers_pkg.campaigns import get_pair
from scheduled.topic_queue_state import (
    slot_msg_ids, set_slot_msg_ids, clear_slot, empty_slot,
)


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
    every successful write.
    """
    fingerprint = build_topic_fingerprint(entries)
    if fingerprint == slot.get("fingerprint", "") and slot_msg_ids(slot):
        return  # No change — skip

    for old_msg_id in slot_msg_ids(slot):
        tg.delete_message(group_id, old_msg_id)

    chunks = format_topic_queue(entries, now)
    sent_msg_ids: list[int] = []
    first_msg_id: int | None = None
    for chunk in chunks:
        msg_id = tg.send_message_id(group_id, int(thread_id), chunk)
        if msg_id:
            sent_msg_ids.append(msg_id)
            if first_msg_id is None:
                first_msg_id = msg_id
    if first_msg_id:
        tg.pin_message(group_id, first_msg_id, disable_notification=False)
        set_slot_msg_ids(slot, sent_msg_ids, fingerprint)
        print(f"Topic queue posted: thread={thread_id} entries={len(entries)} chunks={len(chunks)}")


def _clear_thread_queue(group_id: int, thread_id: str, slot: dict) -> None:
    """Send caught-up message and remove every stale pinned message.

    No-op if the slot has no tracked messages. Slot is reset to the
    empty current-schema shape.
    """
    msg_ids = slot_msg_ids(slot)
    if not msg_ids:
        return  # pragma: no cover
    tg.send_message(group_id, int(thread_id), "━━━━━━━━━━━━━━━━\n✅ All caught up!")
    # Unpin only the first message (the pinned one); delete every tracked id.
    tg.unpin_message(group_id, msg_ids[0])
    for mid in msg_ids:
        tg.delete_message(group_id, mid)
    clear_slot(slot)
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


def post_topic_queues(config: dict, scanned: dict, now: datetime) -> None:
    """Post, update, or clear per-thread pinned queues for all campaigns."""
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
            if thread_id not in active_threads and slot_msg_ids(slot):
                _clear_thread_queue(group_id, thread_id, slot)
                changed = True
                time.sleep(1)
        if changed or cq.get("topic_msg_id") is not None:
            _save(pid, cq)
