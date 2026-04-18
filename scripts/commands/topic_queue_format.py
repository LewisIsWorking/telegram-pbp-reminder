"""
Per-topic pinned queue message formatter.

Formats a compact queue message for posting directly in a PBP topic
thread. No campaign header is included — the reader is already in
context. Re-uses the age-icon scale from commands/queue_format.py.

Used by scheduled/topic_queue_poster.py.
"""

from datetime import datetime, timezone

import helpers
from commands.queue_format import entry_age_icon, age_str, short_preview, format_queue_line

_SEPARATOR = "━━━━━━━━━━━━━━━━"
_AGE_LEGEND = (
    "Age: 🆕<1h 🌱6h 🌿12h 🌳1d 🟢2d 🟩3d 🟡4d 🟨5d 🟠6d 🟧7d "
    "🔴8d 🟥9d 🟣10d 🟪11d 🔵12d 🟦13d 🟤14d 🟫15d ⚫16d ⬛17d 💀21d ☠️25d"
)


_MAX_MSG = 3900  # Telegram limit is 4096; leave headroom


def format_topic_queue(entries: list, now: datetime) -> list[str]:
    """Format a per-topic queue message body, split into ≤4096-char chunks.

    Args:
        entries: list of entry dicts with name, time, preview, link keys.
        now:     current UTC datetime used for age calculation.

    Returns:
        List of message strings, each within Telegram's character limit.
        The header (separator + count + legend) appears only in the first chunk.
    """
    header = f"{_SEPARATOR}\n📋 Unreplied: {len(entries)}\n{_AGE_LEGEND}"
    entry_lines = []
    for i, entry in enumerate(entries, 1):
        hours = _entry_hours(entry, now)
        line = format_queue_line(i, entry, hours)
        link = entry.get("link", "")
        if link:
            line += f" 🔗 {link}"
        entry_lines.append(line)
    return _chunk_lines(header, entry_lines)


def _chunk_lines(header: str, entry_lines: list[str]) -> list[str]:
    """Pack entry lines into chunks that each fit within _MAX_MSG chars."""
    chunks = []
    current_lines = [header]
    current_len = len(header)
    for line in entry_lines:
        # +1 for the newline separator
        if current_len + len(line) + 1 > _MAX_MSG and len(current_lines) > 1:
            chunks.append("\n".join(current_lines))
            current_lines = [line]
            current_len = len(line)
        else:
            current_lines.append(line)
            current_len += len(line) + 1
    if current_lines:
        chunks.append("\n".join(current_lines))
    return chunks if chunks else [header]


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
