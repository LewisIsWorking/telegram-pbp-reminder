"""
Session poll message builders.

Pure functions for constructing poll questions, ping messages, and
history strings. Shared by session_poll.py and poll_result.py.
"""

from datetime import datetime, timedelta


def next_weekday_date(now: datetime, weekday: int) -> str:
    """Return 'DD Month' string for the next occurrence of weekday (0=Mon)."""
    days_until = (weekday - now.weekday()) % 7
    return (now + timedelta(days=days_until)).strftime("%d %B")


def poll_options_for(pair: dict, now: datetime) -> list[str]:
    """Return poll answer options for a campaign pair.

    If the pair defines static ``poll_options``, use them verbatim.
    Otherwise generate dynamic Friday/Saturday options with dates.
    """
    static = pair.get("poll_options")
    if static:
        return list(static)
    friday = next_weekday_date(now, 4)
    saturday = next_weekday_date(now, 5)
    return [f"Friday {friday}", f"Saturday {saturday}", "Can't make either"]


def build_history_str(history: dict) -> str:
    """Build 'History: Fridays X/N, Saturdays Y/N' string or ''."""
    total = history.get("friday", 0) + history.get("saturday", 0)
    if total == 0:
        return ""
    return (f"\n\nHistory: Fridays {history['friday']}/{total}, "
            f"Saturdays {history['saturday']}/{total}")


def build_ping_message(pair: dict, poll: dict, unvoted: list[str],
                       voted: int, total: int,
                       weekday: int, week_num: int,
                       any_day: bool) -> str:
    """Build the daily ping message for unvoted players."""
    code = pair.get("code", "")
    if any_day:
        header = f"🗳️ {code} Week {week_num}/52 — Vote in the poll above!"
    elif weekday == 4:
        header = f"⚠️ {code} Week {week_num}/52 — Last chance to vote!"
    elif weekday == 0:
        header = f"🗳️ {code} Week {week_num}/52 — New session poll is up!"
    else:
        header = f"🗳️ {code} Week {week_num}/52 — Vote in the poll above!"
    unvoted_list = "\n".join(unvoted)
    return (f"━━━━━━━━━━━━━━━━\n{header}\n"
            f"{voted}/{total} voted.\n\nWaiting on:\n{unvoted_list}")


def build_all_voted_message(code: str, total: int, week_num: int) -> str:
    return (f"━━━━━━━━━━━━━━━━\n"
            f"✅ {code} Week {week_num}/52 — All {total} players have voted!")


def votes_to_option_label(option_ids: list[int], pair: dict,
                          now: datetime) -> str:
    """Map Telegram option index(es) to a human-readable label."""
    options = poll_options_for(pair, now)
    labels = []
    for idx in option_ids:
        if idx < len(options):
            labels.append(options[idx].split()[0])  # first word only
    return " & ".join(labels) if labels else "?"
