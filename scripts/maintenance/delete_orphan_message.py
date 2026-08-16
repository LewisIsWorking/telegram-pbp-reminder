#!/usr/bin/env python3
"""One-shot: delete specific orphaned bot messages, and say why if it fails.

Written 2026-08-16 for the orphan Lewis spotted in C06: an
``Unreplied: 2`` post from 2026-08-03 (mid 170029) still sitting in the
topic thirteen days after the bot recorded deleting it. That recording
was wrong — ``"message can't be deleted"`` was suppressed as a soft
success, so the ID was cleared from its slot and never retried. The code
fix stops that happening again; it cannot remove the messages already
stranded, because nothing tracks them any more.

Hence this script. Give it message IDs, it tries each one and prints the
outcome **per ID**, including the raw Telegram error when the delete is
declined. That last part is the point: after the incident above, the one
thing nobody could answer was *why* a delete failed, because no failure
had ever been recorded. Running this answers it directly.

  TELEGRAM_BOT_TOKEN=xxx py -3 scripts/maintenance/delete_orphan_message.py 170029

⚠️ IDs are checked against the bot-sent registry first, exactly like every
other delete path — this script has no force flag and cannot remove a
player's or GM's message. If an ID is refused as not-bot-sent, that is
the guard working; do not work around it.

⚠️ Being an admin of the group is what lets a bot delete its own messages
past Telegram's 48-hour window. If every ID here fails with a permission
error, check the bot's admin rights before touching the code — the 15
over-48h deletes in the pin audit are all consistent with the bot having
quietly lost ``can_delete_messages``.
"""
import os
import sys
import time

_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import telegram as tg  # noqa: E402
from posting.bot_sent_registry import is_bot_sent  # noqa: E402
from posting.stuck_deletes import clear_stuck, is_hopeless  # noqa: E402

GROUP_ID = -1001661053273  # Path Wars group


def main() -> int:
    """Delete each ID given on the command line. Returns a shell exit code."""
    ids = [int(a) for a in sys.argv[1:]]
    if not ids:
        print(__doc__)
        print("Usage: delete_orphan_message.py <message_id> [<message_id> ...]")
        return 2

    tg.init(os.environ["TELEGRAM_BOT_TOKEN"])
    print(f"Attempting {len(ids)} delete(s) in group {GROUP_ID}\n")

    gone = stuck = 0
    for mid in ids:
        if not is_bot_sent(mid):
            print(f"  {mid}: SKIPPED — not in the bot-sent registry. The bot "
                  f"only deletes its own messages.")
            stuck += 1
            continue
        # A previous run may have marked this hopeless. Clear it first so
        # this attempt is a real attempt rather than the cached give-up —
        # otherwise the script would report the old verdict as if it were
        # a fresh one, which is the same class of lie it exists to undo.
        if is_hopeless(mid):
            print(f"  {mid}: previously given up on; retrying anyway")
            clear_stuck(mid)
        if tg.delete_message(GROUP_ID, mid):
            print(f"  {mid}: DELETED")
            gone += 1
        else:
            # telegram._post has already printed Telegram's own error body
            # for anything outside ALREADY_GONE_ERRORS, so the reason is
            # on stdout immediately above this line.
            print(f"  {mid}: FAILED — see the Telegram error printed above. "
                  f"The message is still in the chat.")
            stuck += 1
        time.sleep(0.2)

    print(f"\nDone. {gone} deleted, {stuck} still present.")
    # Non-zero when anything survived, so a caller can tell without
    # parsing stdout. A script that prints a fault and exits 0 is how
    # faults get missed.
    return 1 if stuck else 0


if __name__ == "__main__":
    sys.exit(main())
