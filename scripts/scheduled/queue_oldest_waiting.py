"""The GM queue footer's chronological next: the oldest post waiting anywhere.

Lewis, 2026-11-03. The focus line above it ("Post here next" / "Reply to
this next") is the PRIORITY pick, and it stays. This adds the single oldest
unreplied post across every campaign, with its campaign, poster, age and
link, or one line saying the pick already is that post.

Lewis, 2026-11-20: "The Chronological queue should be C05 not Magni Guard."
A silent campaign (no posts for 5 days or more) has waited too, since its last
post, the same clock the queue body sorts it by (queue_silent_body). So it
competes here as well: C05, silent 10 days, beats a C04 post 2 days old.

Also home to the two small entry helpers the focus pick uses, so both read
"oldest" and "how long" the same way.
"""

from datetime import datetime, timezone

import helpers
from commands.queue_format import age_str


def oldest_entry(entries: list) -> dict:
    """Return the entry with the earliest timestamp."""
    return min(entries, key=lambda e: e.get("time", "9999"))


def wait_hours(entry: dict, now: datetime) -> float:
    """Hours since the entry was posted; 0 when the timestamp is unparseable."""
    try:
        posted = datetime.strptime(entry["time"], "%Y-%m-%d %H:%M:%S")
        return helpers.hours_since(now, posted.replace(tzinfo=timezone.utc))
    except (ValueError, KeyError):
        return 0.0


OLDEST_LABEL = "⏳ Oldest waiting:"
SAME_POST_LINE = "⏳ That is also the oldest post waiting anywhere."
SAME_CAMPAIGN_LINE = "⏳ That is also the longest wait anywhere."


def campaign_label(config: dict, data: dict) -> str:
    """'<emoji> C04: Magni Guard', as the focus line names a campaign."""
    code = data.get("code", "")
    name = data.get("campaign", "")
    label = f"{code}: {name}" if code else name
    emoji = next((p.get("emoji", "") for p in config.get("topic_pairs", [])
                  if p.get("code") == code), "") if code else ""
    return f"{emoji} {label}" if emoji else label


def pick_oldest_waiting(scanned: dict):
    """(pid, entry) for the oldest unreplied post in any campaign, or None."""
    best = None
    for pid, data in scanned.items():
        entries = data.get("entries") or []
        if not entries:
            continue
        entry = oldest_entry(entries)
        if best is None or entry.get("time", "9999") < best[1].get("time", "9999"):
            best = (pid, entry)
    return best


def pick_oldest_any(scanned: dict, silent: list, now: datetime):
    """(pid, entry, None) for the oldest unreplied post, or (pid, None, row) when a silent
    campaign has waited longer. None when nothing waits. A never-posted campaign has no age
    and never wins (queue_silent_body sorts it last for the same reason)."""
    from scheduled.queue_silent_body import silent_since
    best = pick_oldest_waiting(scanned)
    best_time = best[1].get("time", "9999") if best else "~"
    winner = (best[0], best[1], None) if best else None
    for row in silent or []:
        since = silent_since(row, now)
        if row.ever_posted and since < best_time:
            best_time, winner = since, (row.pid, None, row)
    return winner


def oldest_waiting_lines(config: dict, scanned: dict, now: datetime,
                         focus_entry: dict | None = None,
                         silent: list | None = None,
                         focus_pid: str | None = None) -> list:
    """The chronological next, as lines to add under the priority pick.

    ``focus_entry`` is the post the pick already points at, if it points at a
    post at all (an idle campaign is a campaign, not a post). When it is the
    oldest post too, a single line says so rather than naming it twice.
    """
    oldest = pick_oldest_any(scanned, silent or [], now)
    if oldest is None:
        return []
    pid, entry, row = oldest
    if row is not None:
        if focus_pid is not None and focus_pid == row.pid:
            return [SAME_CAMPAIGN_LINE]
        from scheduled.queue_silence_rows import phrase
        return [f"{OLDEST_LABEL} {row.icon} {row.label}, silent: {phrase(row)}",
                *([row.link.strip()] if row.link.strip() else [])]  # the row's link is " 🔗 <url>"
    if focus_entry is not None and entry is focus_entry:
        return [SAME_POST_LINE]
    lines = [f"{OLDEST_LABEL} {campaign_label(config, scanned[pid])}, "
             f"{entry.get('name', '?')}, {age_str(wait_hours(entry, now))}"]
    link = entry.get("link", "")
    if link:
        lines.append(f"🔗 {link}")
    return lines
