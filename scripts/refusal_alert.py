"""Post a Telegram alert if any new delete refusals have been logged.

Runs after the main bot job in CI. Reads
``data/state/refusal_log.json`` for any entries newer than the
``data/state/refusal_log_alerted.json`` marker and, if any are
found, posts a summary to the bot's reserved topic in the Path Wars
group.

A refusal in production means one of two things, both of which the
operator should know about:

  1. The bot tried to delete a message it sent, but the registry
     didn't know about the ID. Either backfill missed a state field
     or a sender forgot to call ``record_sent``. Investigate and
     either fix the sender or seed the registry manually.

  2. Something tried to delete a message the bot didn't send. The
     guard correctly refused, but the attempt itself is suspicious
     and worth understanding.

Either way, alert and review.
"""

import os
import sys

import requests

# Add scripts/ to sys.path so the helpers_pkg import resolves regardless of cwd.
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from helpers_pkg.config import load_config
from posting.refusal_log import get_unalerted_refusals, mark_alerted


def _format_alert(refusals: list, sha: str) -> str:
    """Build the Telegram message body from a list of refusal entries."""
    n = len(refusals)
    header = (
        f"\u26a0\ufe0f Delete refusals: {n} message(s) refused since last alert\n"
        f"sha: {sha}\n\n"
        f"Each entry below is a delete that ``tg.delete_message`` "
        f"refused because the message_id was not in the bot-sent "
        f"registry. Investigate per ``docs/dev/delete-safety.md``.\n"
    )
    lines = [header]
    for entry in refusals[:25]:
        lines.append(
            f"\u2022 {entry.get('timestamp', '?')}  "
            f"chat={entry.get('chat_id', '?')}  "
            f"mid={entry.get('message_id', '?')}"
        )
    if n > 25:
        lines.append(f"\n\u2026 and {n - 25} more (see refusal_log.json)")
    return "\n".join(lines)


def main() -> int:
    """Read refusals; post alert if non-empty; mark alerted. Return 0 on
    success, 1 on missing config (still not an error in CI)."""
    refusals = get_unalerted_refusals()
    if not refusals:
        print("No new refusals to alert.")
        return 0

    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    sha = os.environ.get("GITHUB_SHA", "?")[:8]
    config = load_config()
    gid = config.get("group_id")
    tid = config.get("bot_topic_id")

    if not (token and gid and tid):
        # Don't crash CI just because alert can't be posted.
        # The refusals stay in the log for the next run that has
        # the right env / config.
        print(f"Found {len(refusals)} unalerted refusals but no token "
              f"/ group_id / bot_topic_id available; skipping alert. "
              f"They will be picked up on the next run.")
        return 1

    text = _format_alert(refusals, sha)
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": gid, "message_thread_id": tid, "text": text},
        timeout=15,
    )
    if not resp.ok:
        print(f"Alert post failed: {resp.status_code} {resp.text[:200]}")
        return 1

    last_ts = max(e.get("timestamp", "") for e in refusals)
    mark_alerted(last_ts)
    print(f"Posted alert for {len(refusals)} refusal(s); marked through {last_ts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
