"""'Reply to this next' focus message for the GM queue.

Posted as a follow-up message in the GM queue topic, immediately after the
queue itself, naming the single campaign most in need of a reply.

Selection rule:
  1. Normally the winner is the campaign whose *oldest* unreplied message has
     been waiting longest.
  2. Campaigns flagged ``queue_priority`` in their topic_pair override that:
     if any prioritised campaign has unreplied entries, the choice is made
     among those only. A prioritised campaign is therefore never passed over
     because some other campaign has an older message.

The message is appended to the queue's own message batch, so it is deleted
along with that batch on the next post (``MAX_KEPT_BATCHES = 1``). That
matters - a focus message that outlived its queue would keep pointing at a
message the GM has already answered.
"""

from datetime import datetime, timezone

import helpers
from commands.queue_format import age_str, short_preview


def _oldest_entry(entries: list) -> dict:
    """Return the entry with the earliest timestamp."""
    return min(entries, key=lambda e: e.get("time", "9999"))


def _wait_hours(entry: dict, now: datetime) -> float:
    """Hours since the entry was posted; 0 when the timestamp is unparseable."""
    try:
        posted = datetime.strptime(entry["time"], "%Y-%m-%d %H:%M:%S")
        return helpers.hours_since(now, posted.replace(tzinfo=timezone.utc))
    except (ValueError, KeyError):
        return 0.0


def pick_focus_pid(scanned: dict, priority_map: dict) -> str | None:
    """Return the pid of the campaign most in need of a reply, or None.

    ``priority_map`` is the same pid -> rank map the queue reminder builds
    from ``queue_priority``. When several prioritised campaigns are waiting,
    the lower rank wins first, then the older message.
    """
    pids = [p for p, d in scanned.items() if d.get("entries")]
    if not pids:
        return None
    prioritised = [p for p in pids if p in priority_map]
    pool = prioritised or pids

    def sort_key(pid):
        oldest = _oldest_entry(scanned[pid]["entries"]).get("time", "9999")
        return (priority_map.get(pid, 0) if prioritised else 0, oldest)

    return min(pool, key=sort_key)


def focus_key(scanned: dict, priority_map: dict) -> str | None:
    """A stable identity for the current focus target, or None if there is none.

    Used by ``queue_focus_dm`` to tell "the target moved" from "the same target
    was posted again". Built from ``pick_focus_pid`` and ``_oldest_entry``, the
    same two calls ``build_focus_message`` makes, so the key and the message
    cannot disagree about which message is being pointed at.

    ⚠️ Identifies the MESSAGE, not the campaign. Answering the oldest message in
    a campaign keeps the same campaign in focus but moves the target to its next
    oldest, and that is exactly a change worth announcing.
    """
    pid = pick_focus_pid(scanned, priority_map)
    if not pid:
        return None
    entry = _oldest_entry(scanned[pid]["entries"])
    return entry.get("link") or f"{pid}@{entry.get('time', '')}"


def build_focus_message(config: dict, scanned: dict, priority_map: dict,
                        now: datetime) -> str:
    """Build the focus message, or '' when there is nothing to point at."""
    pid = pick_focus_pid(scanned, priority_map)
    if not pid:
        return ""

    data = scanned[pid]
    entry = _oldest_entry(data["entries"])
    code = data.get("code", "")
    name = data.get("campaign", "")
    label = f"{code}: {name}" if code else name
    emoji = next((p.get("emoji", "") for p in config.get("topic_pairs", [])
                  if p.get("code") == code), "")
    emoji_prefix = f"{emoji} " if emoji else ""

    waiting = age_str(_wait_hours(entry, now))
    count = len(data["entries"])
    who = entry.get("name", "?")
    preview = short_preview(entry.get("preview", ""), words=18)

    lines = ["━━━━━━━━━━━━━━━━",
             f"🎯 Reply to this next: {emoji_prefix}{label}"]
    if pid in priority_map:
        lines.append("📌 Prioritised campaign, so it jumps the age queue.")
    lines.append(f"⏳ Oldest message waiting {waiting} "
                 f"({count} unreplied in this campaign).")
    lines.append(f"↗ {who}: {preview}")
    link = entry.get("link", "")
    if link:
        lines.append(f"🔗 {link}")
    return "\n".join(lines)
