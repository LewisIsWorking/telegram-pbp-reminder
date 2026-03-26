"""
Weekly session poll for hybrid live campaigns.

Posts a poll on Monday asking players to vote Friday or Saturday.
Daily reminders Mon-Fri, skipping players who already voted.
Final reminder Friday afternoon.
"""

from datetime import datetime, timezone, timedelta

import helpers
import telegram as tg


def _next_friday(now: datetime) -> str:
    """Return the date string of the upcoming Friday."""
    days_until = (4 - now.weekday()) % 7
    if days_until == 0 and now.weekday() == 4:
        days_until = 0  # It's Friday
    friday = now + timedelta(days=days_until)
    return friday.strftime("%A %d %B")


def _next_saturday(now: datetime) -> str:
    """Return the date string of the upcoming Saturday."""
    days_until = (5 - now.weekday()) % 7
    if days_until == 0 and now.weekday() == 5:
        days_until = 0
    saturday = now + timedelta(days=days_until)
    return saturday.strftime("%A %d %B")


def _build_poll_message(config: dict, state: dict, now: datetime) -> str:
    """Build the current poll results message."""
    poll = state.get("session_poll", {})
    friday_label = _next_friday(now)
    saturday_label = _next_saturday(now)

    friday_voters = poll.get("friday", {})
    saturday_voters = poll.get("saturday", {})

    lines = [
        f"━━━━━━━━━━━━━━━━",
        f"🗳️ Session Poll — When are we playing?\n",
        f"🅰️ {friday_label} ({len(friday_voters)} votes)",
    ]
    for uid, name in friday_voters.items():
        lines.append(f"  • {name}")

    lines.append(f"\n🅱️ {saturday_label} ({len(saturday_voters)} votes)")
    for uid, name in saturday_voters.items():
        lines.append(f"  • {name}")

    total = len(friday_voters) + len(saturday_voters)
    if total > 0:
        winner = "Friday" if len(friday_voters) > len(saturday_voters) else "Saturday"
        if len(friday_voters) == len(saturday_voters):
            winner = "Tied"
        lines.append(f"\nLeading: {winner}")

    lines.append("\nTap a button below to vote or change your vote.")
    return "\n".join(lines)


def _get_poll_roster(config: dict, state: dict) -> dict:
    """Get all players who should be polled for the session.

    Uses the campaign's poll_user_ids if set, otherwise all
    players in the roster.
    """
    roster = {}
    for pair in config.get("topic_pairs", []):
        if not pair.get("hybrid_live"):
            continue
        pid = str(pair["pbp_topic_ids"][0])
        poll_uids = pair.get("poll_user_ids")

        if poll_uids:
            for uid in poll_uids:
                uid_str = str(uid)
                p = next((p for p in state.get("players", {}).values()
                          if p.get("user_id") == uid_str), None)
                name = p.get("first_name", uid_str) if p else uid_str
                uname = p.get("username", "") if p else ""
                roster[uid_str] = {"name": name, "username": uname}
        else:
            gm_ids = helpers.gm_ids_for_campaign(config, pid)
            for key, p in state.get("players", {}).items():
                if p.get("pbp_topic_id") == pid:
                    uid = p.get("user_id", "")
                    if uid not in gm_ids:
                        roster[uid] = {
                            "name": p.get("first_name", "?"),
                            "username": p.get("username", ""),
                        }
    return roster


def _unvoted_mentions(config: dict, state: dict) -> str:
    """Build @mentions for players who haven't voted yet."""
    poll = state.get("session_poll", {})
    voted = set(poll.get("friday", {}).keys()) | set(poll.get("saturday", {}).keys())
    roster = _get_poll_roster(config, state)

    mentions = []
    for uid, info in roster.items():
        if uid not in voted:
            uname = info.get("username", "")
            mentions.append(f"@{uname}" if uname else info["name"])
    return " ".join(mentions)


def post_session_poll(config: dict, state: dict, *,
                      now: datetime | None = None, **_kw) -> None:
    """Post or update the weekly session poll."""
    now = now or datetime.now(timezone.utc)
    weekday = now.weekday()  # 0=Mon, 4=Fri

    # Only run Mon-Fri
    if weekday > 4:
        return

    # Find hybrid campaign topic
    poll_topic = None
    group_id = config["group_id"]
    for pair in config.get("topic_pairs", []):
        if pair.get("hybrid_live"):
            poll_topic = pair.get("chat_topic_id")
            break
    if not poll_topic:
        return

    poll = state.get("session_poll", {})
    poll_week = poll.get("week_iso", "")
    current_week = now.strftime("%Y-W%W")

    # New week: reset poll
    if poll_week != current_week:
        state["session_poll"] = {
            "week_iso": current_week,
            "friday": {},
            "saturday": {},
            "last_post_day": -1,
            "message_id": None,
        }
        poll = state["session_poll"]

    # Post once per day
    last_day = poll.get("last_post_day", -1)
    if weekday <= last_day:
        return

    message = _build_poll_message(config, state, now)

    # Add reminder for unvoted players
    unvoted = _unvoted_mentions(config, state)
    if unvoted:
        if weekday == 0:
            message += f"\n\nNew week! {unvoted}"
        elif weekday == 4:
            message += f"\n\n⚠️ Last chance to vote! {unvoted}"
        else:
            message += f"\n\nStill waiting on: {unvoted}"

    buttons = [
        {"text": "🅰️ Friday", "callback_data": "poll:friday"},
        {"text": "🅱️ Saturday", "callback_data": "poll:saturday"},
    ]

    msg_id = tg.send_message_with_buttons(group_id, poll_topic, message, buttons)
    if msg_id:
        poll["last_post_day"] = weekday
        poll["message_id"] = msg_id
        print(f"Session poll posted (day {weekday}, week {current_week})")

