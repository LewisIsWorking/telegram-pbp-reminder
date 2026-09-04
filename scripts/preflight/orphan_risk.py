"""Which tracked messages are running out of time to be deleted.

Added 2026-09-04, from a failure Lewis found by eye rather than by alert.

The bot tracks one queue post per thread and replaces it when the content
changes, deleting the old one. Telegram refuses to let a bot delete its
own message once it is **48 hours old**, and admin rights do not lift
that (measured 2026-08-16: 15 of 15 deletes over 48h failed, 0 of 12
under it). So a tracked id that ages past the wall is not at risk of
being lost - it **is** lost, before anything is attempted.

⛔ It happened. Between 2026-08-30 07:05 and 2026-09-01 16:34 GitHub
delivered no run that republished the queues, a gap of **57.5h**, and
three posts crossed the wall in that one window (all deleted by hand by
Lewis on 2026-09-04)::

    thread 145040  m175996   thread 51357  m175998   thread 107171  m176000

⚠️ This said FOUR until 2026-09-04, and named m175902 (thread 52083) as
the fourth. It was not an orphan: ``pin_audit_log`` records its delete
succeeding on the first attempt. The number came from spotting a >48h
GAP BETWEEN POSTS and inferring the outcome, while the log that records
the actual outcome was sitting right there. A proxy agreed with the
direct evidence three times out of four, which is exactly how a proxy
earns trust it has not got. Count orphans with
``tools/audit_queue_deletes.py``, never from the gaps.

``topic_queue_age.can_still_delete`` (2026-09-01) stops those becoming
orphans: past 46h the poster edits the message in place instead of
abandoning it. But nothing ever said the clock was running, and three
more threads cleared the wall by under two hours in the same week -
**66154 made it by twelve minutes.**

⭐ This module is the missing sentence in the alert: not "state is stale"
but "and here is what that staleness is about to cost". It reports; it
changes nothing and deletes nothing.

⚠️ Reports ALL tracked ids with their remaining time, not only the scary
ones. A list that only ever shows problems cannot be checked for having
gone silently empty - see ``a-false-positive-is-noticed-a-false-negative-
is-silence``. The caller picks a threshold.
"""

import json
import os
from datetime import datetime, timedelta, timezone

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))
QUEUES_DIR = os.path.join(_REPO_ROOT, "data", "state", "queues")

# ⛔⛔ Telegram's wall. Not ours, and not liftable by admin rights.
# Mirrors ``scheduled/topic_queue_age.DELETE_WALL``; kept as its own
# constant so this module can be read on its own, and pinned equal to it
# by a test so the two can never drift apart unnoticed.
DELETE_WALL = timedelta(hours=48)

# The poster republishes at 36h. Anything past that is already overdue
# for a refresh and is living on the 12h of slack, which is exactly the
# window the 2026-08-30 outage ate.
WARN_AFTER = timedelta(hours=36)


def _parse(stamp) -> datetime | None:
    if not isinstance(stamp, str):
        return None
    try:
        parsed = datetime.fromisoformat(stamp)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _slots(directory: str):
    """Every (campaign, thread, slot) triple on disk. Unreadable files are
    skipped loudly rather than crashing the gate that calls this."""
    try:
        names = sorted(os.listdir(directory))
    except OSError as error:
        print(f"[orphan-risk] cannot list {directory}: {error}")
        return
    for name in names:
        if not name.endswith(".json"):
            continue
        try:
            with open(os.path.join(directory, name), encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError) as error:
            print(f"[orphan-risk] cannot read {name}: {error}")
            continue
        for thread, slot in (data.get("topic_queues") or {}).items():
            if isinstance(slot, dict):
                yield data.get("pid", name[:-5]), thread, slot


def scan(now: datetime, directory: str = QUEUES_DIR) -> list:
    """Every tracked message with how long it has left to be deletable.

    ``hours_left`` is negative once the wall has passed, which is the
    only honest way to say "this one is already unrecoverable".
    ``hours_left`` of None means the slot carries no timestamp, so
    nothing can be said - reported as unknown rather than as safe.
    """
    rows = []
    for pid, thread, slot in _slots(directory):
        for stamp_key, id_key in (("last_posted_at", "msg_ids"),
                                  ("caught_up_at", "caught_up_msg_id")):
            raw = slot.get(id_key)
            ids = raw if isinstance(raw, list) else ([raw] if raw else [])
            if not ids:
                continue
            posted = _parse(slot.get(stamp_key))
            age = None if posted is None else (now - posted)
            rows.append({
                "pid": pid, "thread": str(thread), "kind": id_key,
                "msg_ids": ids,
                "age_hours": None if age is None else age.total_seconds() / 3600,
                "hours_left": None if age is None
                else (DELETE_WALL - age).total_seconds() / 3600,
            })
    return rows


def at_risk(rows: list, warn_after: timedelta = WARN_AFTER) -> list:
    """Rows worth putting in front of a human, worst first.

    Unknown-age rows are included: "cannot tell" about a delete deadline
    is a reason to look, not a reason to stay quiet.
    """
    ceiling = (DELETE_WALL - warn_after).total_seconds() / 3600
    picked = [r for r in rows
              if r["hours_left"] is None or r["hours_left"] <= ceiling]
    return sorted(picked, key=lambda r: (r["hours_left"] is not None,
                                         r["hours_left"]))


def summarise(rows: list, warn_after: timedelta = WARN_AFTER) -> str:
    """One block for the debug report. Never empty, so silence is visible."""
    if not rows:
        return "Tracked queue messages: NONE FOUND (suspicious - the scan may be broken)"
    risky = at_risk(rows, warn_after)
    head = (f"Tracked queue messages: {len(rows)} "
            f"({len(risky)} within {(DELETE_WALL - warn_after).total_seconds() / 3600:g}h "
            f"of the 48h delete wall)")
    if not risky:
        soonest = min(r["hours_left"] for r in rows if r["hours_left"] is not None)
        return f"{head}\n  soonest deadline: {soonest:.1f}h left"
    lines = [head]
    for row in risky[:8]:
        left = row["hours_left"]
        when = "age UNKNOWN" if left is None else (
            f"{left:.1f}h left" if left > 0 else f"PAST THE WALL by {-left:.1f}h")
        lines.append(f"  C{row['pid']} thread {row['thread']} "
                     f"{row['msg_ids']} {row['kind']}: {when}")
    return "\n".join(lines)
