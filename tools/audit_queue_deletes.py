"""Which superseded queue posts were actually deleted, from the DIRECT record.

Added 2026-09-04, after I got this wrong by inferring it.

⛔ **The mistake this exists to prevent.** Looking for orphaned queue
posts, I measured the GAP between consecutive posts in a thread and
called anything over Telegram's 48h delete wall an orphan. That produced
four, and I gave Lewis four links to delete by hand. Only three were
real: ``m175902`` (thread 52083) had been deleted successfully by the bot
on the first attempt, and ``pin_audit_log.json`` had been recording that
the whole time.

The gap is a **proxy**. It says "a delete attempted at the end of this
window could not have succeeded", which is true, and says nothing about
whether the delete happened earlier, or happened at all. It agreed with
the direct evidence 3 times out of 4, which is precisely how a proxy
earns trust it has not got.

⭐ The direct record was always available and is what this reads:

    data/state/pin_audit_log.json   every delete ATTEMPT, with ok/refused
    data/state/stuck_deletes.json   ids the bot gave up on, for a human
    data/state/sent_messages.json   what was posted, when, to which thread

A post is only an orphan when the audit log shows attempts and none
succeeded. Anything else is arithmetic about calendars.

⚠️ Reports the whole population, not just the offenders: "292 superseded,
0 dropped" is the sentence that tells you the bookkeeping still works. A
report that only ever lists problems cannot be distinguished from a
report that has quietly stopped finding them.

Usage::

    python tools/audit_queue_deletes.py [--since 2026-08-01] [--marker Unreplied]
"""

import argparse
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_STATE = os.path.join(_ROOT, "data", "state")


def _load(name: str, default):
    path = os.path.join(_STATE, name)
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as error:
        print(f"[audit] cannot read {name}: {error}")
        return default


def delete_attempts(audit: list) -> dict:
    """message_id -> its delete attempts, newest last."""
    out: dict = {}
    for entry in audit:
        if entry.get("action") == "delete":
            out.setdefault(str(entry.get("message_id")), []).append(entry)
    return out


def superseded(sent: dict, marker: str, since: str) -> list:
    """Posts that a later post in the same thread replaced.

    The newest post per thread is excluded: it is the live one, and
    nothing was supposed to delete it.
    """
    by_thread: dict = {}
    for msg_id, record in sent.items():
        if marker in record.get("preview", ""):
            by_thread.setdefault(record.get("thread_id"), []).append(
                (record["at"], msg_id))
    rows = []
    for thread, items in by_thread.items():
        items.sort()
        for at, msg_id in items[:-1]:
            if at >= since:
                rows.append({"at": at, "thread": thread, "msg_id": msg_id})
    return sorted(rows, key=lambda r: r["at"])


def classify(rows: list, attempts: dict, stuck: dict) -> list:
    for row in rows:
        tries = attempts.get(row["msg_id"], [])
        row["attempts"] = len(tries)
        row["deleted"] = any(t.get("ok") for t in tries)
        row["filed"] = row["msg_id"] in stuck
        entry = stuck.get(row["msg_id"]) or {}
        row["resolved"] = bool(entry.get("resolved_at"))
        if row["deleted"]:
            row["verdict"] = "deleted"
        elif tries and row["resolved"]:
            # ⭐ Was a real orphan; a human has since removed it. Kept in
            # the file rather than cleared so the history survives, and
            # distinguished here so an old, handled orphan does not read
            # as an outstanding one forever.
            row["verdict"] = f"ORPHAN (resolved {entry['resolved_at'][:10]})"
        elif tries:
            row["verdict"] = "ORPHAN" if row["filed"] else "ORPHAN (unfiled)"
        else:
            row["verdict"] = "DROPPED (no attempt ever made)"
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--since", default="2026-08-01")
    parser.add_argument("--marker", default="Unreplied")
    parser.add_argument("--all", action="store_true",
                        help="list every post, not only the problems")
    args = parser.parse_args()

    rows = classify(
        superseded(_load("sent_messages.json", {}), args.marker, args.since),
        delete_attempts(_load("pin_audit_log.json", [])),
        _load("stuck_deletes.json", {}))

    if not rows:
        print("No superseded posts found. That is suspicious, not clean: "
              "check --since and --marker against the sent log.")
        return 1

    bad = [r for r in rows if r["verdict"] != "deleted"]
    outstanding = [r for r in rows
                   if r["verdict"].startswith("ORPHAN") and not r["resolved"]]
    for row in (rows if args.all else bad):
        print(f"  {row['at'][:16]}  thread {str(row['thread']):>7}  "
              f"m{row['msg_id']:>7}  attempts {row['attempts']}  "
              f"{row['verdict']}")

    print()
    print(f"superseded since {args.since}: {len(rows)}")
    print(f"  deleted cleanly            : {sum(1 for r in rows if r['deleted'])}")
    print(f"  ORPHANS (tried, all failed): "
          f"{sum(1 for r in rows if r['verdict'].startswith('ORPHAN'))}"
          f"  of which still outstanding: {len(outstanding)}")
    print(f"  DROPPED (never attempted)  : "
          f"{sum(1 for r in rows if r['verdict'].startswith('DROPPED'))}")
    # ⚠️ Exit 0 even with orphans. They are history, not a broken build;
    # only a DROPPED post means the bookkeeping itself is losing ids.
    return 1 if any(r["verdict"].startswith("DROPPED") for r in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
