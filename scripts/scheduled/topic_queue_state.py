"""
Backwards-compat shim around ``posting.SinglePin``.

Historically these four functions defined the slot schema for per-topic
pinned queues; they are now thin wrappers around the equivalent methods
on ``posting.SinglePin``. The public API (function names and signatures)
is preserved so existing callers and tests keep working.

Schema evolution:

  Legacy slot:  {"msg_id": int|None, "fingerprint": str}
                — single message tracked, multi-message posts orphaned.

  Current slot: {"msg_ids": list[int], "fingerprint": str,
                 "last_posted_at": iso8601 str | None}
                — every chunk tracked; replace-on-write semantics.

Migration is implicit: ``slot_msg_ids`` reads either shape, and
``set_slot_msg_ids`` always writes the current shape (dropping legacy
keys). The very first write upgrades any legacy slot.

New code should import from ``posting`` directly. This module exists
only so that existing imports (``from scheduled.topic_queue_state
import …``) keep resolving without churn.
"""

from posting import MessageBatch, SinglePin
from posting.stuck_deletes import is_hopeless


def empty_slot() -> dict:
    """Return a fresh empty slot in the current schema."""
    return SinglePin.empty_slot()


def queue_pending_deletes(slot: dict, ids) -> None:
    """Remember message IDs whose delete failed, for retry next run.

    The per-topic queue replaces its pinned message by delete-then-
    repost. If a delete fails (transient Telegram error, an ID not yet
    in the bot-sent registry, etc.) the old message would orphan: the
    poster overwrites the slot with the freshly-posted message and the
    failed ID is forgotten, so nothing ever tries to delete it again.

    To stop that, every failed delete is parked in ``pending_delete``
    on the slot. ``retry_pending_deletes`` re-attempts them on every
    subsequent run until they succeed (the bot is a group admin, so its
    own messages have no 48h delete limit — a retry always eventually
    wins). This is the fix for the 2026-05-28 C01 orphan: ``Unreplied:
    5`` survived because its delete was abandoned, not retried. See L28.

    Deduplicates so the list can't grow without bound on repeated runs.
    """
    pending = slot.setdefault("pending_delete", [])
    for mid in ids:
        if mid not in pending:
            pending.append(mid)


def retry_pending_deletes(slot: dict, group_id: int) -> None:
    """Re-attempt every parked failed-delete; keep only those still failing.

    Called at the top of both the post and clear paths so lingering
    orphans get swept on every run regardless of whether the queue
    content changed. Updates ``slot['pending_delete']`` in place.
    """
    pending = slot.get("pending_delete") or []
    if not pending:
        return
    still_failed = MessageBatch(msg_ids=list(pending),
                                pin_id=None).delete_all(group_id)
    # Drop IDs the bot has given up on (2026-08-16). Without this the list
    # is append-only for any message Telegram will never delete, and every
    # run pays an API call per stuck ID forever. posting.stuck_deletes has
    # already alerted by the time is_hopeless goes True, so dropping here
    # loses no information — it moves the record from a growing slot field
    # to the log built to hold it.
    slot["pending_delete"] = [m for m in still_failed if not is_hopeless(m)]


def slot_msg_ids(slot: dict) -> list[int]:
    """Return the list of message IDs tracked in this slot.

    Reads ``msg_ids`` if present (current schema). Falls back to a
    single-element list synthesised from the legacy ``msg_id`` field.
    Returns an empty list when neither is set.
    """
    return SinglePin.read_batch(slot).msg_ids


def set_slot_msg_ids(slot: dict, msg_ids: list[int],
                     fingerprint: str) -> None:
    """Store a new batch's message IDs and fingerprint in the slot.

    Drops the legacy ``msg_id`` key if present so the slot is fully
    migrated to the current schema after the first write. Stamps
    ``last_posted_at`` to the current UTC time.
    """
    pin_id = msg_ids[0] if msg_ids else None
    batch = MessageBatch(msg_ids=list(msg_ids), pin_id=pin_id)
    SinglePin.write_batch(slot, batch, fingerprint)


def clear_slot(slot: dict) -> None:
    """Reset the slot — call after deleting all tracked messages."""
    SinglePin.clear(slot)


def normalise_queue_keys(queues: dict) -> bool:
    """Force every ``topic_queues`` key to ``str``; merge int/str twins.

    ``topic_queues`` is persisted as JSON, and **JSON object keys are
    always strings**. But ``parse_message`` returns Telegram's raw
    ``message_thread_id`` as an ``int``, and that int was used verbatim
    as the slot key. So ``queues.setdefault(51357, ...)`` missed the
    on-disk ``"51357"`` slot, handed the poster a fresh empty slot, and
    the previous batch was never deleted — then the save wrote the int
    key back out as a *second* string key, stranding the original IDs
    where even the ``pending_delete`` retry sweep could not reach them.
    That is the 2026-08-10 C05 orphan (three surviving "Unreplied:"
    posts). The poster now stringifies at the boundary; this function
    repairs state already corrupted by the buggy runs.

    When both an int and a string key exist for the same thread, the
    **int-keyed slot is the newer one** (the buggy run created it after
    loading the string-keyed slot), so it stays live. The stranded
    string-keyed IDs are parked in ``pending_delete`` rather than
    dropped, so the existing retry sweep deletes them on the next run.

    Mutates ``queues`` in place. Returns True if anything changed, so
    the caller knows to persist.
    """
    non_str = [k for k in list(queues) if not isinstance(k, str)]
    if not non_str:
        return False
    for key in non_str:
        slot = queues.pop(key)
        skey = str(key)
        twin = queues.get(skey)
        queues[skey] = slot
        if twin is None:
            continue
        live = set(slot_msg_ids(slot))
        stranded = [m for m in slot_msg_ids(twin) if m not in live]
        stranded += [m for m in (twin.get("pending_delete") or [])
                     if m not in live]
        if twin.get("caught_up_msg_id") and twin["caught_up_msg_id"] not in live:
            stranded.append(twin["caught_up_msg_id"])
        if stranded:
            queue_pending_deletes(slot, stranded)
    return True
