"""
Shared formatting helpers for GM reply queue display.

Used by commands/queue.py and scheduled/queue_reminder.py.
"""


def entry_age_icon(hours: float) -> str:
    """Return a colour-coded circle for how long a message has been unreplied.

    🟢  < 6 h   — just posted
    ⚪  6–24 h  — same day, still fresh
    🟡  1–2 d   — getting old
    🟠  2–3 d   — overdue
    🔴  3–5 d   — stalled
    🟣  5–7 d   — critically overdue
    🔵  7–14 d  — alarming
    🟤  14–30 d — abandoned
    ⚫  30 d +  — ancient
    """
    if hours < 6:
        return "🟢"
    if hours < 24:
        return "⚪"
    if hours < 48:
        return "🟡"
    if hours < 72:
        return "🟠"
    if hours < 120:
        return "🔴"
    if hours < 168:
        return "🟣"
    if hours < 336:
        return "🔵"
    if hours < 720:
        return "🟤"
    return "⚫"


def age_str(hours: float) -> str:
    """Format an age in hours as '2d 3h' or '5h'."""
    days = int(hours // 24)
    h = int(hours % 24)
    if days > 0:
        return f"{days}d {h}h"
    return f"{h}h"


def short_preview(text: str, words: int = 5) -> str:
    """Return the first N words of text, with '...' if truncated."""
    w = text.replace("\n", " ").split()[:words]
    result = " ".join(w)
    if len(text.split()) > words:
        result += "..."
    return result
