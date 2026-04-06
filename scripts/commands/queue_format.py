"""
Shared formatting helpers for GM reply queue display.

Used by commands/queue.py and scheduled/queue_reminder.py.
"""


def entry_age_icon(hours: float) -> str:
    """Return an icon showing how long a message has been unreplied.

    Under 24h — growth sequence:
      🆕  < 1h    — just posted
      🌱  1–6h    — seedling
      🌿  6–12h   — growing
      🌳  12–24h  — established

    Days 1–16 — colour circle then square, one icon per day:
      🟢  day 1   🟩  day 2
      🟡  day 3   🟨  day 4
      🟠  day 5   🟧  day 6
      🔴  day 7   🟥  day 8
      🟣  day 9   🟪  day 10
      🔵  day 11  🟦  day 12
      🟤  day 13  🟫  day 14
      ⚫  day 15  ⬛  day 16

    Beyond day 16:
      💀  day 17–25
      ☠️   day 25+
    """
    if hours < 1:
        return "🆕"
    if hours < 6:
        return "🌱"
    if hours < 12:
        return "🌿"
    if hours < 24:
        return "🌳"
    # Days 1–16: one icon per day
    days = hours / 24
    if days < 2:   return "🟢"
    if days < 3:   return "🟩"
    if days < 4:   return "🟡"
    if days < 5:   return "🟨"
    if days < 6:   return "🟠"
    if days < 7:   return "🟧"
    if days < 8:   return "🔴"
    if days < 9:   return "🟥"
    if days < 10:  return "🟣"
    if days < 11:  return "🟪"
    if days < 12:  return "🔵"
    if days < 13:  return "🟦"
    if days < 14:  return "🟤"
    if days < 15:  return "🟫"
    if days < 16:  return "⚫"
    if days < 17:  return "⬛"
    if days < 25:  return "💀"
    return "☠️"


def age_str(hours: float) -> str:
    """Format an age in hours as '2d 3h' or '5h'."""
    days = int(hours // 24)
    h = int(hours % 24)
    if days > 0:
        return f"{days}d {h}h"
    return f"{h}h"


def short_preview(text: str, words: int = 15) -> str:
    """Return the first N words of text, with '...' if truncated."""
    w = text.replace("\n", " ").split()[:words]
    result = " ".join(w)
    if len(text.split()) > words:
        result += "..."
    return result
