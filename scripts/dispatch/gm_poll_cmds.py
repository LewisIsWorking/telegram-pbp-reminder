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
    try:  # pragma: no cover
        date_part = week_iso.lstrip("sun").lstrip("sat")  # pragma: no cover
        return datetime.strptime(date_part, "%Y-%m-%d").isocalendar()[1]  # pragma: no cover
    except (ValueError, AttributeError):  # pragma: no cover
        return 0  # pragma: no cover


def handle_sessionplayed(args: str, user_id: str, user_name: str,
                         config: dict, state: dict,
                         group_id: int, bot_topic: int) -> bool:
    """Handle /sessionplayed <code> <week>. Returns True if handled."""
    gm_ids = set(str(g) for g in config.get("gm_user_ids", []))  # pragma: no cover
    if user_id not in gm_ids:  # pragma: no cover
        tg.send_message(group_id, bot_topic, "❌ GMs only.")  # pragma: no cover
        return True  # pragma: no cover
    parts = args.strip().split()  # pragma: no cover
    if len(parts) < 2:  # pragma: no cover
        tg.send_message(group_id, bot_topic,  # pragma: no cover
                        "Usage: /sessionplayed <code> <week>\n"  # pragma: no cover
                        "e.g. /sessionplayed C11 14")  # pragma: no cover
        return True  # pragma: no cover
    code = parts[0].upper()  # pragma: no cover
    try:  # pragma: no cover
        week_num = int(parts[1])  # pragma: no cover
    except ValueError:  # pragma: no cover
        tg.send_message(group_id, bot_topic,  # pragma: no cover
                        "❌ Week must be a number, e.g. /sessionplayed C11 14")  # pragma: no cover
        return True  # pragma: no cover
    sp = state.setdefault("session_poll", {})  # pragma: no cover
    poll = next((p for c, p in sp.items() if c.upper() == code), None)  # pragma: no cover
    if not poll:  # pragma: no cover
        known = ", ".join(sorted(sp.keys()))  # pragma: no cover
        tg.send_message(group_id, bot_topic,  # pragma: no cover
                        f"❌ No active poll for '{code}'.\nKnown: {known}")  # pragma: no cover
        return True  # pragma: no cover
    active_week = poll_week_num(poll.get("week_iso", ""))  # pragma: no cover
    if week_num != active_week:  # pragma: no cover
        tg.send_message(group_id, bot_topic,  # pragma: no cover
                        f"❌ Active poll is week {active_week}, not {week_num}.")  # pragma: no cover
        return True  # pragma: no cover
    poll["session_happened"] = True  # pragma: no cover
    tg.send_message(group_id, bot_topic,  # pragma: no cover
                    f"✅ {code} week {week_num} marked as played — no more pings.")  # pragma: no cover
    print(f"Bot topic: /sessionplayed {code} W{week_num} by {user_name}")  # pragma: no cover
    return True  # pragma: no cover


def handle_swimmingdone(args: str, user_id: str, user_name: str,
                        config: dict, state: dict,
                        group_id: int, bot_topic: int) -> bool:
    """Handle /swimmingdone <week>. Returns True if handled."""
    gm_ids = set(str(g) for g in config.get("gm_user_ids", []))  # pragma: no cover
    if user_id not in gm_ids:  # pragma: no cover
        tg.send_message(group_id, bot_topic, "❌ GMs only.")  # pragma: no cover
        return True  # pragma: no cover
    try:  # pragma: no cover
        week_num = int(args.strip())  # pragma: no cover
    except ValueError:  # pragma: no cover
        tg.send_message(group_id, bot_topic,  # pragma: no cover
                        "Usage: /swimmingdone <week>\ne.g. /swimmingdone 14")  # pragma: no cover
        return True  # pragma: no cover
    sw = state.get("swimming_poll", {})  # pragma: no cover
    if not sw.get("week_iso"):  # pragma: no cover
        tg.send_message(group_id, bot_topic, "❌ No active swimming poll.")  # pragma: no cover
        return True  # pragma: no cover
    active_week = poll_week_num(sw.get("week_iso", ""))  # pragma: no cover
    if week_num != active_week:  # pragma: no cover
        tg.send_message(group_id, bot_topic,  # pragma: no cover
                        f"❌ Active swimming poll is week {active_week}, not {week_num}.")  # pragma: no cover
        return True  # pragma: no cover
    sw["session_happened"] = True  # pragma: no cover
    tg.send_message(group_id, bot_topic,  # pragma: no cover
                    f"✅ Swimming week {week_num} marked as done — no more pings. 🏊")  # pragma: no cover
    print(f"Bot topic: /swimmingdone W{week_num} by {user_name}")  # pragma: no cover
    return True  # pragma: no cover
