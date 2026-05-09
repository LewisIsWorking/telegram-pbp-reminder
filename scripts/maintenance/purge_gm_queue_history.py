"""Sweep a range of message IDs in the GM Queue topic, deleting bot-sent ones.

This script is the same shape as the original 2026-05-08 purge script
(``one-off, sweep IDs A through B, call deleteMessage on each``) but
routes through ``telegram.delete_message`` instead of calling the API
directly. That routing is *the* reason this version is safe:

  * ``telegram.delete_message`` checks the bot-sent registry before
    every deletion.
  * If a swept ID is in the registry (i.e. the bot really did send it
    and tracked the ID in state somewhere), it gets deleted.
  * If a swept ID is NOT in the registry (i.e. it's a player message,
    a GM message, or anything else the bot didn't post), the call is
    refused, a diagnostic line is printed, and no API request is made.

The previous version of this script — committed in 5a7df4d / 0a18a6f
— blindly POSTed to ``deleteMessage`` for every ID in the range
without consulting the registry. Because the bot has admin+delete
permissions in the Path Wars group, the Telegram API happily deleted
non-bot messages too, including ~200 player and GM messages across
several topics. This rewrite makes that mistake structurally
impossible: the only way to delete is via the guarded path.

Usage::

    cd scripts
    python -X utf8 maintenance/purge_gm_queue_history.py

Adjust ``START`` and ``END`` below before running. Bot-sent IDs in the
range are deleted; everything else is logged and left alone.
"""

import os
import sys
import time

# The script lives in scripts/maintenance/ but imports from scripts/
# so make sure scripts/ is on sys.path regardless of cwd.
_SCRIPTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

import telegram as tg

GROUP_ID = -1001661053273  # Path Wars group

# Adjust these before running. Range is inclusive on both ends.
START, END = 151518, 151741


def main() -> None:
    """Sweep [START, END] and delete bot-sent IDs only."""
    token = os.environ["TELEGRAM_BOT_TOKEN"]
    tg.init(token)

    print(f"Sweeping IDs {START}-{END} in group {GROUP_ID}")
    print(f"Total: {END - START + 1} IDs to check")

    deleted = refused = api_failed = 0
    for mid in range(START, END + 1):
        ok = tg.delete_message(GROUP_ID, mid)
        if ok:
            deleted += 1
            if deleted % 25 == 0:
                print(f"  {deleted} deleted (current: {mid})")
        else:
            # tg.delete_message returns False both when the registry
            # refuses (printing its own diagnostic) AND when the API
            # call itself fails. We can't distinguish them from the
            # return value alone — both count as "skipped".
            refused += 1
        time.sleep(0.05)

    print(f"Done. {deleted} deleted, {refused} skipped "
          f"(registry-refused or API-failed).")


if __name__ == "__main__":
    main()
