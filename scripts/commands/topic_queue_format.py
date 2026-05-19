"""
Per-topic pinned queue message formatter.

Formats a slim queue message for posting directly in a PBP topic
thread. No campaign header, no age legend, no quote/preview text —
the reader is already in context and can scroll to see the
cited message. The bot-topic GM Queue (scheduled/queue_reminder.py)
remains verbose by design; this per-topic format is the slim sibling.

Format (per Lewis 2026-05-19, after player feedback from Cannon
about the meta brick in RP channels):

    📋 Unreplied: 2
    ↗ Ryo · 🌳 14h · t.me/Path_Wars/51357/153422
    ↗ Bruce · 🌳 13h · t.me/Path_Wars/142887/153432

The link is preserved (Lewis hard requirement — every entry needs
its own jumpable link), the age icon is preserved (urgency hint),
and everything else is stripped. See L27 in REFACTOR_PROGRESS.md
for the two-tier rationale.

Used by scheduled/topic_queue_poster.py.
"""

from datetime import datetime, timezone

import helpers
from commands.queue_format import entry_age_icon, age_str

_MAX_MSG = 3900  # Telegram limit is 4096; leave headroom


def format_topic_queue(entries: list, now: datetime) -> list[str]:
    """Format a per-topic queue message body, split into ≤4096-char chunks.

    Args:
        entries: list of entry dicts with name, time, preview, link keys.
        now:     current UTC datetime used for age calculation.

    Returns:
        List of message strings, each within Telegram's character limit.
        The header (“📋 Unreplied: N”) appears only in the first chunk.
    """
    header = f"📋 Unreplied: {len(entries)}"
    entry_lines = []
    for entry in entries:
        hours = _entry_hours(entry, now)
        entry_lines.append(_format_topic_line(entry, hours))
    return _chunk_lines(header, entry_lines)


def _format_topic_line(entry: dict, hours: float) -> str:
    """Slim per-entry line: ↗ Firstname · {icon} {age} · {link}.

    Drops the numbered prefix, message-id brackets, and quote/preview
    text used by the bot-topic format. Players see only what's needed
    to identify the unreplied message and jump to it. If the entry has
    no link, the line is just "↗ Firstname · {icon} {age}" — no
    trailing separator dangling.
    """
    icon = entry_age_icon(hours)
    age = age_str(hours)
    name = (entry.get("name", "?").split() or ["?"])[0]  # first name only
    link = entry.get("link", "")
    if link:
        return f"↗ {name} · {icon} {age} · {link}"
    return f"↗ {name} · {icon} {age}"


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
