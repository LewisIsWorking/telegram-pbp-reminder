#!/usr/bin/env python3
"""Ask Telegram whether the messages the bot believes it deleted are gone.

    TELEGRAM_BOT_TOKEN=xxx py -3 scripts/maintenance/audit_orphans.py
    ... --limit 50        check only the 50 most recent claims
    ... --since 2026-08-01

Exit code 0 when every claim checks out, 1 when any message the bot
recorded as deleted is still in the group.

────────────────────────────────────────────────────────────────────────

Why this exists. On 2026-08-16 Lewis found an ``Unreplied: 2`` post from
2026-08-03 still sitting in the C06 topic. The bot's audit trail said it
had deleted that message on 2026-08-06. Nothing in the repo disagreed,
because every artefact in the repo was derived from the same belief —
the state file, the audit log and the tests all agreed with each other
and all of them were wrong.

⭐ **A system cannot audit a belief using only its own records.** The
offline detector (``test_no_delete_attempted_past_the_wall.py``) catches
the one mechanism we now understand: a delete attempted past Telegram's
48-hour wall. This tool catches the mechanisms we do not understand yet,
because it asks the only authority that cannot be wrong about whether a
message exists — Telegram.

Run it after any change to the delete/pin lifecycle, and periodically.

────────────────────────────────────────────────────────────────────────

The probe. ``setMessageReaction`` with an empty reaction list removes the
**bot's own** reaction to a message. This bot has never reacted to
anything, so the call is a no-op: nothing changes, nobody is notified.
The response still distinguishes the two cases, which is all we need:

    "message to react not found"  -> GONE   (the claim was true)
    anything else                 -> EXISTS (the claim was false)

⚠️ Do NOT be tempted back to ``editMessageReplyMarkup`` for this. It
reads as harmless and it is not: ``telegram.send_button_message`` sends
inline keyboards, and an empty-markup edit on one of those would strip
its buttons and break an interactive message. Verified 2026-08-16.

⚠️ This script never calls ``getUpdates``. Doing so would consume the
bot's update offset and make the live poller miss real player messages.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

import requests

_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

GROUP_ID = -1001661053273  # Path Wars group
_AUDIT = Path(_SCRIPTS_DIR).parent / "data" / "state" / "pin_audit_log.json"

# Telegram allows ~30 requests/second to a group; this is far under that
# and keeps a full sweep polite even at several hundred IDs.
_PAUSE = 0.35


def claimed_deleted(rows, since: str | None) -> list[tuple[int, str]]:
    """Return (message_id, timestamp) for every delete the bot called a success.

    Deduplicated on message_id, keeping the most recent claim — an ID may
    be attempted more than once, and the last word is the one the bot is
    currently standing behind.
    """
    latest: dict[int, str] = {}
    for row in rows:
        if row.get("action") != "delete" or not row.get("ok"):
            continue
        if row.get("refused"):
            continue  # refused before any HTTP call; no claim was made
        stamp = row.get("timestamp", "")
        if since and stamp < since:
            continue
        mid = row.get("message_id")
        if mid is not None and stamp >= latest.get(mid, ""):
            latest[mid] = stamp
    return sorted(latest.items(), key=lambda kv: kv[1])


def still_exists(api: str, message_id: int) -> bool | None:
    """True if the message is still in the group, None if undeterminable."""
    try:
        r = requests.post(f"{api}/setMessageReaction",
                          json={"chat_id": GROUP_ID,
                                "message_id": message_id,
                                "reaction": []}, timeout=20).json()
    except requests.RequestException as e:
        print(f"  {message_id}: network error, skipped ({e})")
        return None
    if r.get("ok"):
        return True
    description = r.get("description", "")
    if "not found" in description:
        return False
    if "FLOOD" in description.upper() or "Too Many" in description:
        print(f"  {message_id}: rate limited, skipped ({description})")
        return None
    # Any other error still proves Telegram found the message.
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--limit", type=int, default=0,
                    help="check only the N most recent claims")
    ap.add_argument("--since", help="ISO timestamp; ignore older claims")
    args = ap.parse_args()

    if not _AUDIT.exists():
        print(f"No audit log at {_AUDIT}; nothing to reconcile.")
        return 0
    rows = json.loads(_AUDIT.read_text(encoding="utf-8"))
    claims = claimed_deleted(rows, args.since)
    if args.limit:
        claims = claims[-args.limit:]
    if not claims:
        print("No delete claims to check.")
        return 0

    api = f"https://api.telegram.org/bot{os.environ['TELEGRAM_BOT_TOKEN']}"
    print(f"Reconciling {len(claims)} delete claim(s) against Telegram.\n")

    survivors, unknown = [], 0
    for mid, stamp in claims:
        verdict = still_exists(api, mid)
        if verdict is None:
            unknown += 1
        elif verdict:
            survivors.append((mid, stamp))
            print(f"  ORPHAN {mid}: recorded deleted at {stamp}, "
                  f"still in the group")
        time.sleep(_PAUSE)

    checked = len(claims) - unknown
    print(f"\nChecked {checked} claim(s). {len(survivors)} orphan(s).")
    if unknown:
        # Never let a skipped check read as a pass. See
        # a-failure-must-say-whose-fault-it-is.
        print(f"⚠️  {unknown} could not be checked (network / rate limit). "
              f"This run did NOT cover them — re-run to close the gap.")
    if survivors:
        print("\nThese messages are still in the group and the bot believes "
              "they are gone. It cannot remove them itself once they are "
              "past 48h — delete them by hand:")
        for mid, _ in survivors:
            print(f"  https://t.me/Path_Wars/{mid}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
