"""
GM poll management commands for the bot topic.

/sessionplayed <code> <week> — mark a campaign's session as happened
/swimmingdone <week>         — mark swimming as happened

Both stop poll pings for the rest of the week and reset on Sunday.
"""
from datetime import datetime

import telegram as tg


def poll_week_num(week_iso: str) -> int:
    """Extract ISO week number from a week_iso string like 'sun2026-03-29'."""
    try:
        date_part = week_iso.lstrip("sun").lstrip("sat")
        return datetime.strptime(date_part, "%Y-%m-%d").isocalendar()[1]
    except (ValueError, AttributeError):
        return 0


def handle_sessionplayed(args: str, user_id: str, user_name: str,
                         config: dict, state: dict,
                         group_id: int, bot_topic: int) -> bool:
    """Handle /sessionplayed <code> <week>. Returns True if handled."""
    gm_ids = set(str(g) for g in config.get("gm_user_ids", []))
    if user_id not in gm_ids:
        tg.send_message(group_id, bot_topic, "❌ GMs only.")
        return True
    parts = args.strip().split()
    if len(parts) < 2:
        tg.send_message(group_id, bot_topic,
                        "Usage: /sessionplayed <code> <week>\n"
                        "e.g. /sessionplayed C11 14")
        return True
    code = parts[0].upper()
    try:
        week_num = int(parts[1])
    except ValueError:
        tg.send_message(group_id, bot_topic,
                        "❌ Week must be a number, e.g. /sessionplayed C11 14")
        return True
    sp = state.setdefault("session_poll", {})
    poll = next((p for c, p in sp.items() if c.upper() == code), None)
    if not poll:
        known = ", ".join(sorted(sp.keys()))
        tg.send_message(group_id, bot_topic,
                        f"❌ No active poll for '{code}'.\nKnown: {known}")
        return True
    active_week = poll_week_num(poll.get("week_iso", ""))
    if week_num != active_week:
        tg.send_message(group_id, bot_topic,
                        f"❌ Active poll is week {active_week}, not {week_num}.")
        return True
    poll["session_happened"] = True
    tg.send_message(group_id, bot_topic,
                    f"✅ {code} week {week_num} marked as played — no more pings.")
    print(f"Bot topic: /sessionplayed {code} W{week_num} by {user_name}")
    return True


def handle_swimmingdone(args: str, user_id: str, user_name: str,
                        config: dict, state: dict,
                        group_id: int, bot_topic: int) -> bool:
    """Handle /swimmingdone <week>. Returns True if handled."""
    gm_ids = set(str(g) for g in config.get("gm_user_ids", []))
    if user_id not in gm_ids:
        tg.send_message(group_id, bot_topic, "❌ GMs only.")
        return True
    try:
        week_num = int(args.strip())
    except ValueError:
        tg.send_message(group_id, bot_topic,
                        "Usage: /swimmingdone <week>\ne.g. /swimmingdone 14")
        return True
    sw = state.get("swimming_poll", {})
    if not sw.get("week_iso"):
        tg.send_message(group_id, bot_topic, "❌ No active swimming poll.")
        return True
    active_week = poll_week_num(sw.get("week_iso", ""))
    if week_num != active_week:
        tg.send_message(group_id, bot_topic,
                        f"❌ Active swimming poll is week {active_week}, not {week_num}.")
        return True
    sw["session_happened"] = True
    tg.send_message(group_id, bot_topic,
                    f"✅ Swimming week {week_num} marked as done — no more pings. 🏊")
    print(f"Bot topic: /swimmingdone W{week_num} by {user_name}")
    return True
