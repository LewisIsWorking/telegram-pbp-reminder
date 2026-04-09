"""
Per-topic pinned queue post/update/delete loop.

Called once per hourly run from scheduled/queue_reminder.py.
For each physical PBP topic thread with unreplied entries, maintains a
pinned queue message scoped to only that thread's entries.

Multi-topic campaigns (e.g. C06 Kibwe with PBP + COMBAT threads) each get
their own pinned queue in the correct thread, not everything posted to the
canonical pid thread.

State per canonical campaign pid in data/state/queues/{pid}.json:
  topic_queues: {thread_id: {msg_id, fingerprint}}  — one slot per thread
  topic_msg_id, topic_fingerprint — legacy fields, migrated on first run
"""

import time
from datetime import datetime

import telegram as tg
from commands.queue_io import load as _load, save as _save, all_pids as _all_pids
from commands.topic_queue_format import format_topic_queue, build_topic_fingerprint
from helpers_pkg.campaigns import get_pair


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

    slot is a mutable dict: {msg_id, fingerprint} — updated in place.
    """
    fingerprint = build_topic_fingerprint(entries)
    if fingerprint == slot.get("fingerprint", "") and slot.get("msg_id"):
        return  # No change — skip

    old_msg_id = slot.get("msg_id")
    if old_msg_id:
        tg.delete_message(group_id, old_msg_id)

    text = format_topic_queue(entries, now)
    new_msg_id = tg.send_message_id(group_id, int(thread_id), text)
    if new_msg_id:
        tg.pin_message(group_id, new_msg_id, disable_notification=False)
        slot["msg_id"] = new_msg_id
        slot["fingerprint"] = fingerprint
        print(f"Topic queue posted: thread={thread_id} entries={len(entries)}")


def _clear_thread_queue(group_id: int, thread_id: str, slot: dict) -> None:
    """Send caught-up message and remove stale pin for one thread.

    No-op if no pin exists. slot updated in place.
    """
    old_msg_id = slot.get("msg_id")
    if not old_msg_id:
        return
    tg.send_message(group_id, int(thread_id), "━━━━━━━━━━━━━━━━\n✅ All caught up!")
    tg.unpin_message(group_id, old_msg_id)
    tg.delete_message(group_id, old_msg_id)
    slot["msg_id"] = None
    slot["fingerprint"] = ""
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
        slot = queues.setdefault(thread_id, {"msg_id": None, "fingerprint": ""})
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
            if thread_id not in active_threads and slot.get("msg_id"):
                _clear_thread_queue(group_id, thread_id, slot)
                changed = True
                time.sleep(1)
        if changed or cq.get("topic_msg_id") is not None:
            _save(pid, cq)
