"""
Per-topic pinned queue message formatter.

Formats a compact queue message for posting directly in a PBP topic
thread. No campaign header is included — the reader is already in
context. Re-uses the age-icon scale from commands/queue_format.py.

Used by scheduled/topic_queue_poster.py.
"""

from datetime import datetime, timezone

import helpers
from commands.queue_format import entry_age_icon, age_str, short_preview

_SEPARATOR = "━━━━━━━━━━━━━━━━"
_AGE_LEGEND = (
    "Age: 🆕<1h 🌱6h 🌿12h 🌳1d 🟢2d 🟩3d 🟡4d 🟨5d 🟠6d 🟧7d "
    "🔴8d 🟥9d 🟣10d 🟪11d 🔵12d 🟦13d 🟤14d 🟫15d ⚫16d ⬛17d 💀21d ☠️25d"
)


def format_topic_queue(entries: list, now: datetime) -> str:
    """Format a per-topic queue message body.

    Args:
        entries: list of entry dicts with name, time, preview, link keys.
        now:     current UTC datetime used for age calculation.

    Returns:
        Formatted multi-line string ready to send as a Telegram message.
    """
    lines = [f"{_SEPARATOR}\n📋 Unreplied: {len(entries)}\n{_AGE_LEGEND}"]
    for i, entry in enumerate(entries, 1):
        hours = _entry_hours(entry, now)
        icon = entry_age_icon(hours)
        user = entry.get("name", "?")
        preview = short_preview(entry.get("preview", ""))
        line = f"{i:02d} {icon} {age_str(hours)}. {user}: {preview}"
        link = entry.get("link", "")
        if link:
            line += f" 🔗 {link}"
        lines.append(line)
    return "\n".join(lines)


def _entry_hours(entry: dict, now: datetime) -> float:
    """Return hours since entry was posted, or 0.0 on any parse failure."""
    try:
        posted = datetime.strptime(
            entry["time"], "%Y-%m-%d %H:%M:%S"
        ).replace(tzinfo=timezone.utc)
        return helpers.hours_since(now, posted)
    except (ValueError, KeyError):
        return 0.0


def build_topic_fingerprint(entries: list) -> str:
    """Build a stable change-detection fingerprint for a queue entry list.

    Returns 'empty' for an empty list so the sentinel value is always
    distinct from any real fingerprint.
    """
    return "|".join(e["time"] for e in entries) if entries else "empty"
