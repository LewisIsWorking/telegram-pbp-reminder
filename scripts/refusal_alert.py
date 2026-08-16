"""Post a Telegram alert if any new delete refusals have been logged.

Runs after the main bot job in CI. Reads
``data/state/refusal_log.json`` for any entries newer than the
``data/state/refusal_log_alerted.json`` marker and, if any are
found, posts a summary to the bot's reserved topic in the Path Wars
group.

Entries carry a ``reason`` and are rendered per reason, because the two
classes call for opposite responses:

  ``registry``    The registry did not list the ID. Either backfill
                  missed a state field, a sender forgot ``record_sent``,
                  or something tried to delete a message the bot never
                  sent. **A bug to investigate.**

  ``undeletable`` Telegram refuses to remove the message and the bot has
                  given up after ``stuck_deletes.MAX_ATTEMPTS``. The ID
                  is in the registry and the code is behaving correctly;
                  the message is simply older than Telegram's 48h limit
                  for bot deletes. **A chore for a human, not a bug.**

⚠️ Until 2026-08-16 this file asserted the first explanation for every
entry. When ``stuck_deletes`` started routing give-ups through the same
log, the alert announced 11 of them as registry refusals — and every one
of those IDs was in the registry. Reusing the transport was right;
reusing the explanation sent the operator to the wrong runbook. If a
third reason is ever added, give it its own section here.
"""

import os
import sys

import requests

# Add scripts/ to sys.path so the helpers_pkg import resolves regardless of cwd.
_SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from helpers_pkg.config import load_config
from posting import message_facts as mf
from posting.message_facts import describe, one_line
from posting.refusal_log import (REASON_REGISTRY, REASON_UNDELETABLE,
                                 get_unalerted_refusals, mark_alerted)


def _registry_section(entries: list) -> list:
    """A delete the bot-sent registry rejected. A code or backfill fault.

    \u2b50 Each entry is resolved to its sender and text. A registry refusal
    on a BOT message is a bookkeeping slip \u2014 backfill missed a state
    field. A registry refusal on a PLAYER's message is the guard stopping
    the thing it was built to stop, and is an incident. Under the old
    format both arrived as a bare ``mid=`` and read identically, which
    made the alert unable to report its own most important finding.
    """
    resolved = [(e, describe(e.get("message_id"))) for e in entries[:25]]
    alarming = [(e, f) for e, f in resolved if f["origin"] != mf.BOT]

    if alarming:
        out = [f"\U0001f6a8 Registry refusals: {len(entries)} "
               f"\u2014 {len(alarming)} NOT sent by the bot",
               "Something asked the bot to delete a message it did not "
               "send. The guard refused, so nothing was lost, but the "
               "attempt itself should not have happened. Find the caller."]
    else:
        out = [f"\U0001f6d1 Registry refusals: {len(entries)} "
               f"\u2014 all are bot messages",
               "The bot tried to delete its own messages that the registry "
               "does not list, so backfill missed a state field or a "
               "sender skipped record_sent. Nothing was at risk. "
               "Investigate per docs/dev/delete-safety.md."]
    for entry, facts in resolved:
        flag = "  \u26a0\ufe0f" if facts["origin"] != mf.BOT else ""
        out.append(f"\u2022 {one_line(entry.get('message_id'), facts)}{flag}")
    if len(entries) > 25:
        out.append(f"\u2026 and {len(entries) - 25} more")
    return out


def _undeletable_section(entries: list) -> list:
    """Telegram will not remove it. Nothing to fix in code; needs hands."""
    out = [f"\U0001f4cc Undeletable: {len(entries)}",
           "Telegram declined these repeatedly, so the bot has stopped "
           "asking. They are bot messages older than 48h, and admin rights "
           "do not lift that limit, so ONLY A HUMAN can remove them. This "
           "is not a code fault and needs no investigation. It needs a tap.",
           "Delete these by hand:"]
    for e in entries[:25]:
        mid = e.get("message_id", "?")
        facts = describe(mid)
        # The text matters here too: it is how Lewis decides whether a
        # stranded post is worth walking to the topic for.
        out.append(f"\u2022 https://t.me/Path_Wars/{mid} \u2014 "
                   f"{facts.get('preview') or '(no text recorded)'}")
    if len(entries) > 25:
        out.append(f"\u2026 and {len(entries) - 25} more "
                   f"(run maintenance/audit_orphans.py for the full list)")
    return out


# Renderer per reason. A reason with no renderer falls back to the
# registry wording, which is what every pre-2026-08-16 entry is.
_SECTIONS = {
    REASON_REGISTRY: _registry_section,
    REASON_UNDELETABLE: _undeletable_section,
}


def _format_alert(refusals: list, sha: str) -> str:
    """Build the Telegram body, grouped by WHY each delete failed.

    \u26a0\ufe0f The single-cause version of this function announced 11
    give-ups as "refused because the message_id was not in the bot-sent
    registry" on 2026-08-16. Every one of those IDs *was* in the
    registry. Reusing an alert channel for a second failure class is
    fine; reusing its explanation is not. The two need opposite
    responses: one is a bug to investigate, the other is a chore to do.
    """
    by_reason: dict[str, list] = {}
    for entry in refusals:
        by_reason.setdefault(
            entry.get("reason") or REASON_REGISTRY, []).append(entry)

    lines = [f"\u26a0\ufe0f Delete failures: {len(refusals)} since last alert",
             f"sha: {sha}"]
    for reason, entries in sorted(by_reason.items()):
        lines.append("")
        lines.extend(_SECTIONS.get(reason, _registry_section)(entries))
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
