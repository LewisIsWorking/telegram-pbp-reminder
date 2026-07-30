"""
Shared formatting helpers for GM reply queue display.

Used by commands/queue.py and scheduled/queue_reminder.py.
"""

# Sort rank given to campaigns with no ``queue_priority``. Must stay above
# every rank anyone would plausibly assign, so unprioritised campaigns always
# sort last.
#
# Hardcoded as 2 until 2026-07-30, which silently capped the usable range at a
# single level: assigning a real rank of 2 put that campaign level with the
# unprioritised ones rather than above them. Ranks 1..98 are now free.
NO_PRIORITY = 99


def build_priority_map(config: dict) -> dict[str, int]:
    """Map pid -> numeric queue rank. Lower rank sorts higher in the queue.

    ``queue_priority: true`` is a legacy alias for rank 1; an integer is used
    directly. Campaigns absent from the map sort at NO_PRIORITY.

    Shared by commands/queue.py and scheduled/queue_reminder.py, which built
    this identically before 2026-07-30.
    """
    priority_map: dict[str, int] = {}
    for pair in config.get("topic_pairs", []):
        qp = pair.get("queue_priority")
        if qp is not None and qp is not False:
            pid_str = str(pair["pbp_topic_ids"][0])
            priority_map[pid_str] = int(qp) if isinstance(qp, int) else 1
    return priority_map


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

def format_queue_line(entry_num: int, entry: dict, hours: float) -> str:
    """Format a single GM queue entry line with message ID prefix."""
    icon = entry_age_icon(hours)
    age = age_str(hours)
    user = entry.get("name", "?")
    preview = short_preview(entry.get("preview", ""))
    mid = entry.get("message_id") or ""
    # Fallback: extract ID from link if transcript didn't have msg# tag
    if not mid:
        link_val = entry.get("link", "")
        if link_val and "/" in link_val:
            mid = link_val.rstrip("/").rsplit("/", 1)[-1]
    pfx = f"{entry_num:02d} [{mid}]" if mid else f"{entry_num:02d}"
    line = f"{pfx} {icon} {age}. {user}: {preview}"
    link = entry.get("link", "")
    if link:
        line += f" 🔗 {link}"
    return line
