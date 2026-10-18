"""message_id -> thread_id map from the persisted per-campaign queue files.

Extracted from ``commands/queue_scan.py`` on 2026-10-18, which sat at the
200-line limit and needed room for the ``tracked_since`` floor. The queue
files are authoritative for which physical topic a message lives in, which
is what makes multi-topic campaigns (C00, C05, C06) link correctly.
"""


def thread_lookup_from_queues() -> dict[str, str]:
    """Map every known message id to its thread id, as strings."""
    # Imported here, as before the extraction, so a test that patches
    # commands.queue_io still reaches this read.
    from commands.queue_io import load as _load_queue, all_pids as _all_pids
    lookup: dict[str, str] = {}
    for pid in _all_pids():
        cq = _load_queue(pid)
        for e in cq.get("unreplied", []):
            mid, tid = e.get("message_id"), e.get("thread_id")
            if mid and tid:
                lookup[str(mid)] = str(tid)
        for e in cq.get("reply_log", []):
            mid, tid = e.get("msg_id"), e.get("thread_id")
            if mid and tid:
                lookup[str(mid)] = str(tid)
    return lookup
