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
    — keys are ALWAYS str (JSON forces it); see _threads_from_scanned
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
from scheduled.topic_queue_state import normalise_queue_keys as _normalise_queue_keys


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


from scheduled.topic_queue_write import (  # noqa: F401
    _post_thread_queue, _clear_thread_queue, sweep_aged_caught_up)


def _threads_from_scanned(scanned: dict) -> dict[str, tuple[str, list]]:
    """Split scanned entries by physical thread_id.

    Returns {thread_id: (canonical_pid, entries_for_this_thread)}.
    Multi-topic campaigns produce one entry per active thread.
    """
    result: dict[str, tuple[str, list]] = {}
    for pid, data in scanned.items():
        by_thread: dict[str, list] = {}
        for entry in data["entries"]:
            # str() is load-bearing: entries carry Telegram's raw int
            # thread_id, but topic_queues is JSON so its keys are always
            # str. An int key misses the on-disk slot and the previous
            # batch is never deleted — the 2026-08-10 C05 orphan. See
            # topic_queue_state.normalise_queue_keys.
            tid = str(entry.get("thread_id", pid))
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
        _normalise_queue_keys(queues)
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
        changed = _normalise_queue_keys(queues)
        for thread_id, slot in list(queues.items()):
            if thread_id in active_threads:
                continue
            if slot_msg_ids(slot) or slot.get("pending_delete"):
                _clear_thread_queue(group_id, thread_id, slot, pid=pid,
                                    state=state, config=config, now=now)
                changed = True
                time.sleep(1)
            # A slot holding ONLY a caught-up notice never entered the
            # branch above, so nothing ever revisited it and the notice
            # sat until the thread woke up — often past Telegram's 48h
            # delete wall. 15 of the 28 orphans found on 2026-08-16 were
            # these. Sweeping on age is what bounds their lifetime.
            elif sweep_aged_caught_up(group_id, slot, now):
                changed = True
                time.sleep(1)
        if changed or cq.get("topic_msg_id") is not None:
            _save(pid, cq)


# Registers the per-topic-queue schema migration (``_migrate_legacy``) in
# the central migration registry; imported here so registration runs
# whenever this poster is imported (the migration-registry test relies on
# that import side effect).
from scheduled import topic_queue_migration  # noqa: F401, E402
