"""Read the WHOLE backlog before drawing any conclusion from it.

Added 2026-09-01, and it is the bug behind three separate complaints
Lewis raised in one message:

* the daily "campaign that needs players most" post never arrived;
* the GM queue looked wrong;
* the bot posted **"All caught up. Time for players to post!"** into C07
  while two player messages sat unanswered.

⛔⛔ **`getUpdates` returns AT MOST 100 UPDATES PER CALL, and the checker
called it exactly once per run.** After the 15 hour outage there were
several hundred queued. The 16:33 run logged::

    Received 100 new updates

drained the OLDEST hundred (still 2026-08-31), advanced the offset, and
then ran every scheduled check against that partial view. From inside
that run C07 genuinely had nothing unreplied, because the 11:20 and
11:28 messages had not been read yet. **The caught-up notice was not
wrong. It was answered from half a page.**

⭐ So the rule is not "fetch more". It is: **a partial drain must not
produce posts.** Paging fixes the common case; refusing to run the
checks when the backlog is still not empty is what stops the bot
announcing a conclusion it has not finished reading the evidence for.

⚠️ ``PAGE_LIMIT`` must match ``telegram_utils.fetch_updates``'s ``limit``.
It is imported from there rather than repeated, because a duplicated
literal across a boundary is exactly what took the bot down earlier the
same day (the crons and the job conditions).
"""

from telegram_utils import PAGE_LIMIT

# 20 pages = 2000 updates, comfortably more than any real backlog and far
# inside the job timeout. Hitting it means something is very wrong, and
# the caller is told rather than left to guess.
MAX_PAGES = 20


def drain(offset: int, fetch, process) -> tuple[int, int, bool]:
    """Read every pending update, one page at a time.

    ``fetch(offset) -> list`` and ``process(updates) -> new_offset`` are
    injected so this is testable without Telegram or global state.

    Returns ``(new_offset, total_read, complete)``. **``complete`` is
    False when the backlog was still full after MAX_PAGES**, which the
    caller must treat as "do not post anything this run".
    """
    total = 0
    for _ in range(MAX_PAGES):
        updates = fetch(offset)
        if not updates:
            return offset, total, True
        offset = process(updates)
        total += len(updates)
        if len(updates) < PAGE_LIMIT:
            # A short page is Telegram saying there is nothing more.
            return offset, total, True
    # Still a full page after MAX_PAGES: the caller must not conclude
    # anything from what it has read.
    return offset, total, False


def drain_into(bot_state: dict, fetch, process) -> bool:
    """Drain into ``bot_state['offset']`` and report completeness.

    Wraps :func:`drain` with the state write and the log line, so the
    checker's main loop stays one call. Returns True when the backlog is
    empty and it is therefore safe to run the scheduled checks.
    """
    offset, received, complete = drain(bot_state.get("offset", 0),
                                       fetch, process)
    bot_state["offset"] = offset
    print(f"Received {received} new updates (backlog "
          f"{'drained' if complete else 'STILL NOT EMPTY'})")
    if not complete:
        print("Skipping scheduled checks: the update backlog is not empty, "
              "so anything posted now would be a conclusion drawn from a "
              "partial read. The next run continues the drain.")
    return complete
