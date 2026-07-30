"""Rendering helpers for the GM queue post.

Extracted from ``queue_reminder.py`` on 2026-07-30 to bring that module back
under the 200-line rule after the focus message and the caught-up age lines
were added. Everything here turns already-gathered data into text; the
orchestration, state writes and posting stay in ``queue_reminder``.
"""

AGE_LEGEND = ("Age: 🆕<1h 🌱6h 🌿12h 🌳1d 🟢2d 🟩3d 🟡4d 🟨5d 🟠6d 🟧7d "
              "🔴8d 🟥9d 🟣10d 🟪11d 🔵12d 🟦13d 🟤14d 🟫15d ⚫16d ⬛17d "
              "💀21d ☠️25d")


def build_streak(state: dict, now) -> str:
    """Return the ' | ✅ N today | 🏆 N all-time' header suffix.

    Either half is omitted when its count is zero, so a fresh day shows no
    empty counters.
    """
    from commands.queue_stats import get_today_clears, get_alltime_clears
    cleared_today = get_today_clears(state, now)
    cleared_alltime = get_alltime_clears()
    streak = f" | ✅ {cleared_today} today" if cleared_today else ""
    streak += f" | 🏆 {cleared_alltime} all-time" if cleared_alltime else ""
    return streak


def build_summary(scanned: dict, sorted_pids: list) -> str:
    """Return the per-campaign count line, e.g. 'C01:3 C07:9 C05:6'."""
    parts = []
    for pid in sorted_pids:
        d = scanned[pid]
        code = d.get("code", "")
        label = code if code else d["campaign"]
        parts.append(f"{label}:{len(d['entries'])}")
    return " ".join(parts)


def build_momentum_map(state: dict, config: dict) -> dict:
    """Return {campaign code or name: fastest-responder blurb}.

    ``player_momentum`` returns display strings; this splits them back into a
    lookup so the queue can append ⚡ markers per campaign section.
    """
    from commands.queue_analytics import player_momentum
    state.setdefault("_config_cache", config)
    momentum_map = {}
    for line in player_momentum(state, config):
        if ": " in line:
            key, value = line.split(": ", 1)
            momentum_map[key] = value
    return momentum_map


def build_header(queue_num: int, total: int, streak: str, summary: str) -> str:
    """Return the queue post's first block."""
    return (f"━━━━━━━━━━━━━━━━\n"
            f"📋 GM Queue #{queue_num} — Unreplied: {total}{streak}\n"
            f"{summary}\n{AGE_LEGEND}")


def chunk_messages(lines: list, message: str) -> list:
    """Split a rendered queue into Telegram-sized messages.

    Telegram caps a message at 4096 characters. Short queues stay a single
    message; longer ones are split on line boundaries at 3900 so a chunk never
    lands mid-line.
    """
    if len(message) <= 4000:
        return [message]
    msgs = []
    current = ""
    for line in lines:
        if len(current) + len(line) + 1 > 3900:
            msgs.append(current)
            current = ""
        current += line + "\n"
    if current.strip():
        msgs.append(current.rstrip())
    return msgs
