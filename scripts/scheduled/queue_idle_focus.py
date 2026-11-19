"""The focus pick's idle candidate: a silent or caught-up campaign.

Extracted from ``scheduled/queue_focus.py`` on 2026-11-19, when silent
campaigns gained a rank there and the module passed the 200-line limit.
``queue_focus.pick_idle_focus`` is still the entry point; it finds the reply
pick and hands it here.

Lewis, 2026-09-25: a campaign nobody is waiting on can still need the GM
more than the oldest unreplied message does. So it competes on the same
clock: hours since its last post against hours the oldest message has
waited, and the longer wait wins. A tie goes to the waiting message.

Lewis, 2026-11-19: "silent campaigns should be in the chronological queue
... as equal priority to wait for reply campaigns." So a SILENT campaign
(quiet for ``SILENCE_THRESHOLD_DAYS`` or more) competes on its own
``queue_priority`` rank, exactly as the queue body orders it (see
``queue_silent_body``): a silent C09 jumps an owed reply in an unprioritised
campaign, as an owed C09 reply would, and loses to an owed reply in a
higher-ranked one. A caught-up campaign (quiet under the threshold) still
competes on age alone, as before.

A campaign with no recorded post (``days=inf``) never competes, or it would
win forever.
"""

from datetime import datetime

from commands.queue_format import NO_PRIORITY, age_str
from scheduled.queue_oldest_waiting import oldest_entry, wait_hours
from scheduled.queue_silence_rows import (SILENCE_THRESHOLD_DAYS,
                                          callout_phrase, idle_campaigns)


def idle_key(row, priority_map: dict) -> tuple:
    """(rank, -hours quiet): silent rows keep their rank, caught-up ones do not."""
    silent = row.days >= SILENCE_THRESHOLD_DAYS
    rank = priority_map.get(row.pid, NO_PRIORITY) if silent else NO_PRIORITY
    return (rank, -row.days * 24)


def won_on_rank(row, priority_map: dict) -> bool:
    """True when an idle row ranks as a prioritised campaign, not on age alone."""
    return idle_key(row, priority_map)[0] != NO_PRIORITY


def pick_idle_row(config: dict, state: dict, scanned: dict, reply_pid: str,
                  priority_map: dict, now: datetime):
    """The idle row that beats the reply pick ``reply_pid``, or None."""
    rows = [r for r in idle_campaigns(config, state, scanned, now)
            if r.ever_posted and r.days != float("inf")]
    if not rows:
        return None
    row = min(rows, key=lambda r: idle_key(r, priority_map))
    waited = wait_hours(oldest_entry(scanned[reply_pid]["entries"]), now)
    # A tie goes to the waiting message: strictly less wins.
    reply_key = (priority_map.get(reply_pid, NO_PRIORITY), -waited)
    return row if idle_key(row, priority_map) < reply_key else None


def idle_focus_message(row, scanned: dict, pid: str, now: datetime,
                       on_rank: bool = False) -> str:
    """The focus message when a silent or caught-up campaign goes first.

    ``on_rank`` is True when a prioritised silent campaign is the pick. It may
    not have out-waited the oldest reply, so the age comparison is replaced
    by the usual prioritised line.
    """
    waiting = age_str(wait_hours(oldest_entry(scanned[pid]["entries"]), now))
    quiet = callout_phrase(row)
    quiet = f"{quiet[0].upper()}{quiet[1:]}"
    lines = ["━━━━━━━━━━━━━━━━",
             f"🎯 Post here next: {row.icon} {row.prefix}{row.label}"]
    if on_rank:
        lines += ["📌 Prioritised campaign, so it jumps the age queue.",
                  f"⏳ {quiet}."]
    else:
        lines.append(f"⏳ {quiet}, longer than the oldest reply owed "
                     f"anywhere ({waiting}).")
    lines.append("Nobody is waiting on you there, so it needs you to get it moving.")
    if row.link.strip():
        lines.append(row.link.strip())
    return "\n".join(lines)
