"""The bot must never attempt a delete it cannot possibly win.

COVERS  every delete recorded in ``data/state/pin_audit_log.json`` whose
        target's send time is also recorded there, i.e. every message the
        bot pinned. That is the topic-queue posts and GM queue batches —
        the ones that orphan.
MISSES  messages the bot sent but never pinned. ``pin_audit`` only
        records pin / unpin / delete, so an unpinned message has no birth
        timestamp and its age at delete is unknowable from this file.
        Closing that gap means timestamping ``bot_sent_ids``; see the
        note at the foot of this file.
ANCHORED to the audit log on disk, not to a hand-written list of
        incidents. It reads whatever is there.
PROVEN  by ``test_the_detector_can_fail``, and by the fact that on the
        day it was written it identified exactly the 15 known orphans
        with no false positives — see ``KNOWN_PRE_FIX_ORPHANS``.

────────────────────────────────────────────────────────────────────────

Telegram will not let a bot delete its own message once it is more than
48 hours old. Administrator rights and ``can_delete_messages`` do **not**
lift this. Measured against the live Path Wars group, 2026-08-16:

    deletes attempted when the message was OVER 48h old:  15 of 15 STILL EXIST
    deletes attempted when it was UNDER 48h old:           0 of 12 still exist

So an attempted delete past the wall is not a risk, it is a **loss that
has already happened**. The message will stay in the topic forever, and
before 2026-08-16 the bot recorded each one as a success.

Why this test and not a state invariant. The obvious guard — "no tracked
message may be older than 48h" — cannot work, and the reason is worth
keeping. Checking the committed state at 2026-08-06T06:38, minutes after
the C06 orphan was created:

    "40585": {"msg_ids": [], "last_posted_at": null,
              "caught_up_msg_id": 170384}

The stranded ID had already been dropped. **A detector that reads only
live state cannot see what state has forgotten**, and forgetting is the
failure mode. The audit log is the only artefact that retained both the
send and the delete, which is precisely why it could answer the question
after the fact.
"""
import datetime as dt
import json
from pathlib import Path

import pytest

# Telegram's hard limit. Not ours to choose.
WALL = dt.timedelta(hours=48)

_AUDIT = (Path(__file__).resolve().parent.parent
          / "data" / "state" / "pin_audit_log.json")

# The IDs and the reason each batch exists live in _orphan_ids.py,
# extracted 2026-09-01 when this file passed 200 lines.
from _orphan_ids import ALL as KNOWN_PRE_FIX_ORPHANS  # noqa: E402



def _load_audit():
    if not _AUDIT.exists():
        pytest.skip("pin_audit_log.json absent on this checkout")
    try:
        rows = json.loads(_AUDIT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pytest.skip("pin_audit_log.json unreadable")
    return rows if isinstance(rows, list) else []


def deletes_past_the_wall(rows) -> dict[int, float]:
    """Return {message_id: age_in_hours} for every doomed delete attempt.

    Birth is the earliest recorded action for an ID — a pin, in practice,
    since that is the first thing the bot does after sending. An ID whose
    first recorded action IS the delete has no known birth and is skipped
    rather than guessed at: reporting an unknown as a violation would
    make this test noisy, and noisy guards get deleted.
    """
    born: dict[int, dt.datetime] = {}
    for row in rows:
        mid, stamp = row.get("message_id"), row.get("timestamp")
        if mid is None or not stamp or row.get("action") == "delete":
            continue
        when = dt.datetime.fromisoformat(stamp)
        if mid not in born or when < born[mid]:
            born[mid] = when

    doomed: dict[int, float] = {}
    for row in rows:
        if row.get("action") != "delete":
            continue
        mid = row.get("message_id")
        start = born.get(mid)
        if start is None:
            continue
        age = dt.datetime.fromisoformat(row["timestamp"]) - start
        if age > WALL:
            doomed[mid] = round(age.total_seconds() / 3600, 1)
    return doomed


def test_no_new_delete_is_attempted_past_the_wall():
    """A delete past 48h is a message orphaned in the group, permanently."""
    doomed = deletes_past_the_wall(_load_audit())
    fresh = {m: h for m, h in doomed.items() if m not in KNOWN_PRE_FIX_ORPHANS}
    assert not fresh, (
        f"The bot attempted {len(fresh)} delete(s) on messages already past "
        f"Telegram's 48h wall: {fresh} (message_id -> age in hours). Every "
        f"one of those messages is now stuck in its topic and only a human "
        f"can remove it.\n\n"
        f"This means something is holding a message ID for longer than 36h "
        f"without refreshing it. Check scheduled/topic_queue_age.py, which "
        f"owns that clock, and any NEW code path that stores a message ID "
        f"for later deletion — caught-up notices, poll messages, pinned "
        f"reports. Storing an ID means owning its lifetime."
    )


def test_the_known_orphan_list_does_not_grow():
    """The allowlist is a ratchet: it may shrink, never grow.

    A frozen ceiling would let the count regrow to its worst-ever value
    and still pass. Anything that appears here must be a real historical
    entry, not a newly-tolerated one.
    """
    doomed = set(deletes_past_the_wall(_load_audit()))
    assert doomed <= KNOWN_PRE_FIX_ORPHANS, (
        f"IDs past the wall that are not in the known list: "
        f"{sorted(doomed - KNOWN_PRE_FIX_ORPHANS)}"
    )


def test_healthy_deletes_are_the_overwhelming_majority():
    """Sanity floor. If most deletes were doomed the detector above would
    be measuring something other than what it claims — a clock bug, a
    timestamp format change, a rewritten audit schema."""
    rows = _load_audit()
    total = sum(1 for r in rows if r.get("action") == "delete")
    if total < 20:
        pytest.skip("too few deletes recorded to judge")
    doomed = len(deletes_past_the_wall(rows))
    assert doomed / total < 0.25, (
        f"{doomed} of {total} deletes were past the wall. That is too many "
        f"to be a lifecycle bug — suspect the timestamps themselves."
    )


# ── PROVE the detector can fail ──────────────────────────────────────────────

def test_the_detector_can_fail():
    """Feed it a synthetic doomed delete and confirm it is reported.

    Per ``guards-that-mean-something``: a green detector is evidence only
    if it would have gone red. This is the whole file in miniature — a
    message born, then deleted three days later.
    """
    born = dt.datetime(2026, 8, 1, 12, 0, tzinfo=dt.timezone.utc)
    rows = [
        {"action": "pin", "message_id": 4242, "timestamp": born.isoformat()},
        {"action": "delete", "message_id": 4242,
         "timestamp": (born + dt.timedelta(hours=72)).isoformat()},
        # A healthy one alongside it, so the test also proves the detector
        # discriminates rather than flagging everything it sees.
        {"action": "pin", "message_id": 4243, "timestamp": born.isoformat()},
        {"action": "delete", "message_id": 4243,
         "timestamp": (born + dt.timedelta(hours=5)).isoformat()},
    ]
    found = deletes_past_the_wall(rows)
    assert found == {4242: 72.0}, f"expected only 4242 to be doomed, got {found}"


def test_unknown_birth_is_not_guessed_at():
    """An ID whose first recorded action is its delete must be skipped,
    not assumed old. Guessing here would flag every unpinned message."""
    rows = [{"action": "delete", "message_id": 5555,
             "timestamp": "2026-08-01T12:00:00+00:00"}]
    assert deletes_past_the_wall(rows) == {}


# ⚠️ THE GAP: only PINNED messages have a birth timestamp, because
# pin_audit records pin/unpin/delete and nothing else. Caught-up notices,
# the recruit focus post and poll messages are invisible here — 15 of the
# 28 orphans found on 2026-08-16 were caught-up notices, and only
# maintenance/audit_orphans.py (which asks Telegram) could see them.
# Closing it properly means timestamping bot_sent_ids.json, today a flat
# list of ints. Making it {id: sent_at} would let every delete path ask
# "can I still win this?" BEFORE calling Telegram. Deliberately not done
# in the same change as the fix it would have caught.
