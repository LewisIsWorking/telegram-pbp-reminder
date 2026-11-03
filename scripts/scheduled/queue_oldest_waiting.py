"""The GM queue footer's chronological next: the oldest post waiting anywhere.

Lewis, 2026-11-03. The focus line above it ("Post here next" / "Reply to
this next") is the PRIORITY pick, and it stays. This adds the single oldest
unreplied post across every campaign, with its campaign, poster, age and
link, or one line saying the pick already is that post.

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


def oldest_waiting_lines(config: dict, scanned: dict, now: datetime,
                         focus_entry: dict | None = None) -> list:
    """The chronological next, as lines to add under the priority pick.

    ``focus_entry`` is the post the pick already points at, if it points at a
    post at all (an idle campaign is a campaign, not a post). When it is the
    oldest post too, a single line says so rather than naming it twice.
    """
    oldest = pick_oldest_waiting(scanned)
    if oldest is None:
        return []
    pid, entry = oldest
    if focus_entry is not None and entry is focus_entry:
        return [SAME_POST_LINE]
    lines = [f"{OLDEST_LABEL} {campaign_label(config, scanned[pid])}, "
             f"{entry.get('name', '?')}, {age_str(wait_hours(entry, now))}"]
    link = entry.get("link", "")
    if link:
        lines.append(f"🔗 {link}")
    return lines
