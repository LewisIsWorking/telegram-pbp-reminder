"""
Audit-trail side-effects for /markdone clears.

When the GM clears a queue entry via /markdone, two stores need to be
updated: the per-campaign ``reply_log`` (uncapped audit trail used by
the all-time counter) and the global ``state.queue_history`` /
``state.queue_archive`` pair (the daily "today" counter).

Before this module existed, only ``reply_log`` got the markdone clear,
which is why the queue header showed /markdone clears in
"Z all-time" but not in "Y today". ``record_clear`` mirrors the
event into both stores so the two counters agree on what counts.

Callers are expected to dedupe at the ``replied[]`` level first
(``is_new_clear`` gate); ``record_reply`` itself is also defensively
idempotent against the most recent (pid, msg_id) in
``state.queue_archive``.
"""

from datetime import datetime


def record_clear(cq: dict, pid: str, state: dict, *,
                 mid_str: str, thread_id: str,
                 player_name: str, preview: str,
                 now: datetime) -> None:
    """Append the clear to reply_log and mirror it into queue_history."""
    cq.setdefault("reply_log", []).append({
        "t":         now.isoformat(),
        "pid":       pid,
        "msg_id":    mid_str,
        "thread_id": thread_id,
        "player":    player_name,
        "preview":   preview[:80],
        "via":       "markdone",
    })
    # Local import keeps queue_stats out of markdone's import-time graph
    # (queue_stats pulls in helpers and is not needed for /markdone parse).
    from commands.queue_stats import record_reply
    record_reply(pid, state, preview, player_name,
                 now=now, msg_id=mid_str)
