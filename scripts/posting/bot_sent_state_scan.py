"""Pure helpers that extract bot-sent message IDs from on-disk state.

Lives in its own module to keep ``bot_sent_registry`` under the
200-line cap. These functions are pure: they accept a parsed-JSON
dict, return a list of ints, and have no side effects. They know the
shape of the live-state and per-campaign-queue JSON files but not how
the registry persists or locks.

Schemas understood here are documented at the source of each function.
When new fields are added to ``live.json`` or ``queues/{pid}.json``
that store a bot-sent message ID, that field should be picked up here
so the registry's backfill stays accurate.
"""


def extract_ids_from_live(live: dict) -> list:
    """Pull every bot-sent message ID from a ``live.json`` shape.

    Recognises:
        last_queue_pin_id           legacy single pin (one int)
        schedule_post_msg_id        self-replacing schedule/timer post
        gm_queue_history[*].msg_ids rolling window batch IDs
        gm_queue_history[*].pin_id  pinned-chunk ID inside each batch
    """
    ids: list = []
    if live.get("last_queue_pin_id"):
        ids.append(live["last_queue_pin_id"])
    # Added 2026-08-11. Omitting it broke the schedule post's self-replacement:
    # each Actions run is a fresh checkout, so bot_sent_ids.json does not
    # survive and the registry rebuilds from this scan. An ID the scan does not
    # know about is not in the registry, so perform_guarded_delete refuses it —
    # correctly, by its own rules — and the previous post is never removed. Two
    # posts became three became four, one every 30 minutes.
    if live.get("schedule_post_msg_id"):
        ids.append(live["schedule_post_msg_id"])
    # Added 2026-08-15. Same contract as the schedule post: the recruit
    # focus deletes its own predecessor, and an id missing from the
    # registry gets that delete refused by perform_guarded_delete.
    if live.get("recruit_focus_msg_id"):
        ids.append(live["recruit_focus_msg_id"])
    for batch in live.get("gm_queue_history") or []:
        for mid in batch.get("msg_ids") or []:
            ids.append(mid)
        if batch.get("pin_id"):
            ids.append(batch["pin_id"])
    return ids


def extract_ids_from_queue(cq: dict) -> list:
    """Pull every bot-sent message ID from a ``queues/{pid}.json`` file.

    Recognises:
        topic_msg_id                          legacy single pin (top-level)
        topic_queues[tid].msg_ids             current per-thread batch IDs
        topic_queues[tid].msg_id              legacy per-thread single pin
        topic_queues[tid].caught_up_msg_id    "All caught up!" message
        topic_queues[tid].pin_id              pinned-chunk ID
        topic_queues[tid].pending_delete      failed-delete IDs awaiting retry
    """
    ids: list = []
    if cq.get("topic_msg_id"):
        ids.append(cq["topic_msg_id"])
    for slot in (cq.get("topic_queues") or {}).values():
        if not isinstance(slot, dict):
            continue
        for mid in slot.get("msg_ids") or []:
            ids.append(mid)
        if slot.get("msg_id"):
            ids.append(slot["msg_id"])
        if slot.get("caught_up_msg_id"):
            ids.append(slot["caught_up_msg_id"])
        if slot.get("pin_id"):
            ids.append(slot["pin_id"])
        for mid in slot.get("pending_delete") or []:
            ids.append(mid)
    return ids
