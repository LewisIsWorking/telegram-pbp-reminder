"""
Session poll message builders.

Pure functions for constructing poll questions, ping messages, and
history strings. Shared by session_poll.py and poll_result.py.
"""

from datetime import datetime, timedelta


def sunday_week_key(now: datetime) -> str:
    """Return an ISO-style week key anchored to Sunday (YYYY-WsunNN).

    Both polls start on Sunday so the week is Sunday→Saturday.
    """
    # Find this week's Sunday (weekday 6)
    days_since_sunday = (now.weekday() + 1) % 7
    sunday = now - timedelta(days=days_since_sunday)
    return sunday.strftime("sun%Y-%m-%d")


def is_poll_day(now: datetime, pair: dict) -> bool:
    """Return True if the poll should be active today.

    C11 (poll_any_day) runs Mon–Sun.
    C01 runs Sun–Sat (all week once started Sunday).
    Both start posting on Sunday.
    """
    return True  # Both run all week; gate is handled by week key + start hour


def poll_options_for(pair: dict, now: datetime) -> list[str]:
    """Return poll answer options. Static if configured, else Fri/Sat.

    When static options contain bare 'Friday' or 'Saturday', the upcoming
    date is appended automatically (e.g. '2026-04-10 Friday').
    """
    static = pair.get("poll_options")
    if static:
        friday = _next_weekday_date(now, 4)
        saturday = _next_weekday_date(now, 5)
        day_map = {"Friday": f"{friday} Friday", "Saturday": f"{saturday} Saturday"}
        return [day_map.get(opt, opt) for opt in static]
    from scheduled.session_poll_build import _next_weekday_date as _nwd
    friday = _nwd(now, 4)
    saturday = _nwd(now, 5)
    return [f"{friday} Friday", f"{saturday} Saturday", "Can't make either"]


def _next_weekday_date(now: datetime, weekday: int) -> str:
    days_until = (weekday - now.weekday()) % 7
    return (now + timedelta(days=days_until)).strftime("%Y-%m-%d")


def build_history_str(history: dict, options: list[str]) -> str:
    """Build history line using option labels and win counts."""
    wins = history.get("wins", {})
    total = sum(wins.values())
    if total == 0:
        return ""
    parts = [f"{opts}: {wins.get(str(i), 0)}/{total}"
             for i, opts in enumerate(options) if wins.get(str(i), 0)]
    return "\n\nHistory: " + ", ".join(parts) if parts else ""


def build_ping_message(pair: dict, unvoted: list[str],
                       voted: int, total: int,
                       week_num: int, poll_link: str) -> str:
    """Build the daily ping message for unvoted players."""
    code = pair.get("code", "")
    header = f"🗳️ {code} Week {week_num}/52 — Vote in the poll above!"
    unvoted_list = "\n".join(unvoted)
    link_line = f"\n🔗 {poll_link}" if poll_link else ""
    return (f"━━━━━━━━━━━━━━━━\n{header}\n"
            f"{voted}/{total} voted.{link_line}\n\nWaiting on:\n{unvoted_list}")


def build_all_voted_message(code: str, total: int, week_num: int) -> str:
    return (f"━━━━━━━━━━━━━━━━\n"
            f"✅ {code} Week {week_num}/52 — All {total} players have voted!")


def votes_to_option_label(option_ids: list[int], pair: dict,
                          now: datetime) -> str:
    """Map Telegram option index(es) to a human-readable label."""
    options = poll_options_for(pair, now)
    labels = [options[idx].split()[0] for idx in option_ids if idx < len(options)]
    return " & ".join(labels) if labels else "?"


def option_tally(votes: dict, options: list[str]) -> list[str]:
    """Return ['Friday: 3', 'Saturday: 1', ...] for non-zero options."""
    parts = []
    for i, label in enumerate(options):
        uids = votes.get(str(i), [])
        if uids:
            parts.append(f"{label.split()[0]}: {len(uids)}")
    return parts
