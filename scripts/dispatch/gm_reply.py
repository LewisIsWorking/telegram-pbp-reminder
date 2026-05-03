"""
GM reply recording.

Extracted from dispatch/tracking.py: when a GM replies to a player
message via Telegram's reply-to feature, this module owns the
side-effects (per-campaign queue file update, state.queue_history /
state.queue_archive append). The flow is gated on
``queue_io.mark_replied`` so duplicate updates from Telegram (offset
re-replays, edits, retries) do not produce duplicate entries.
"""

from datetime import datetime, timezone

from commands import queue_io


def record_gm_reply(parsed: dict, state: dict, pid: str,
                    reply_to: int) -> bool:
    """Record a GM's reply-to-message clear for the given campaign.

    Loads the per-campaign queue file, builds a ``log_entry`` from the
    matching unreplied entry (if any), and calls
    ``queue_io.mark_replied``. When ``mark_replied`` reports the reply
    is new, ``record_reply`` is invoked to update the global
    ``state.queue_history`` / ``state.queue_archive`` stores.

    Returns ``True`` when this call recorded a new reply; ``False``
    when the reply was already on file (no-op, idempotent).
    """
    cq = queue_io.load(pid)
    mid_key = f"msg:{reply_to}"
    ts_key: str | None = None
    replied_entry: dict = {}

    for e in cq.get("unreplied", []):
        if e["message_id"] == reply_to:
            replied_entry = e
            ts = e.get("time", "")[:19].replace("T", " ")
            ts_key = ts if ts else None
            break
    else:
        reply_date = parsed.get("reply_to_date")  # pragma: no cover
        if reply_date:  # pragma: no cover
            ts_key = datetime.fromtimestamp(  # pragma: no cover
                reply_date, tz=timezone.utc
            ).strftime("%Y-%m-%d %H:%M:%S")

    log_entry = {
        "t":         parsed["msg_time_iso"],
        "pid":       pid,
        "msg_id":    str(reply_to),
        "thread_id": replied_entry.get("thread_id", pid),
        "player":    replied_entry.get("user_name", "?"),
        "preview":   replied_entry.get("preview", "")[:80],
        "via":       "reply",
    }
    is_new = queue_io.mark_replied(pid, mid_key, ts_key, log_entry)
    if is_new:
        # record_reply writes to state.queue_history and state.queue_archive
        # (global per-bot stores). Only call when the reply is genuinely
        # new so dupes from Telegram retries don't inflate the stats.
        from commands.queue_stats import record_reply
        record_reply(pid, state,
                     replied_entry.get("preview", ""),
                     replied_entry.get("user_name", ""),
                     msg_id=str(reply_to))
    return is_new
