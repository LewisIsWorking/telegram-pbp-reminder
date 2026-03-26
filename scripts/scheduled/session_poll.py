"""
Weekly session poll for hybrid live campaigns.

Uses Telegram's native sendPoll for voting. Sends ping
messages Mon-Fri reminding unvoted players.
"""

from datetime import datetime, timezone, timedelta

import helpers
import telegram as tg


def _next_friday(now: datetime) -> str:
    """Return the date string of the upcoming Friday."""
    days_until = (4 - now.weekday()) % 7
    if days_until == 0:
        days_until = 0
    friday = now + timedelta(days=days_until)
    return friday.strftime("%d %B")


def _next_saturday(now: datetime) -> str:
    """Return the date string of the upcoming Saturday."""
    days_until = (5 - now.weekday()) % 7
    if days_until == 0 and now.weekday() != 5:
        days_until = 7
    saturday = now + timedelta(days=days_until)
    return saturday.strftime("%d %B")


def _get_poll_roster(config: dict, state: dict) -> dict:
    """Get all players who should be polled.

    Uses poll_user_ids if set, otherwise all players in roster.
    """
    roster = {}
    for pair in config.get("topic_pairs", []):
        if not pair.get("hybrid_live"):
            continue
        pid = str(pair["pbp_topic_ids"][0])
        poll_uids = pair.get("poll_user_ids")
        gm_ids = helpers.gm_ids_for_campaign(config, pid)

        if poll_uids:
            for uid in poll_uids:
                uid_str = str(uid)
                p = next((p for p in state.get("players", {}).values()
                          if p.get("user_id") == uid_str), None)
                name = p.get("first_name", uid_str) if p else uid_str
                uname = p.get("username", "") if p else ""
                roster[uid_str] = {"name": name, "username": uname}
        else:
            for key, p in state.get("players", {}).items():
                if p.get("pbp_topic_id") == pid:
                    uid = p.get("user_id", "")
                    if uid not in gm_ids:
                        roster[uid] = {
                            "name": p.get("first_name", "?"),
                            "username": p.get("username", ""),
                        }
    return roster


def _unvoted_mentions(config: dict, state: dict) -> list[str]:
    """Build list of @mentions for players who haven't voted yet."""
    poll = state.get("session_poll", {})
    voted = set(str(uid) for uid in poll.get("voted_uids", []))
    roster = _get_poll_roster(config, state)

    mentions = []
    for uid, info in roster.items():
        if uid not in voted:
            uname = info.get("username", "")
            mentions.append(f"@{uname}" if uname else info["name"])
    return mentions


def _vote_count(config: dict, state: dict) -> tuple[int, int]:
    """Return (voted, total) for the current poll."""
    poll = state.get("session_poll", {})
    voted = len(poll.get("voted_uids", []))
    total = len(_get_poll_roster(config, state))
    return voted, total


def post_session_poll(config: dict, state: dict, *,
                      now: datetime | None = None, **_kw) -> None:
    """Post or update the weekly session poll."""
    now = now or datetime.now(timezone.utc)
    weekday = now.weekday()  # 0=Mon, 4=Fri

    if weekday > 4:
        return

    poll_topic = None
    group_id = config["group_id"]
    for pair in config.get("topic_pairs", []):
        if pair.get("hybrid_live"):
            poll_topic = pair.get("chat_topic_id")
            break
    if not poll_topic:
        return

    poll = state.get("session_poll", {})
    current_week = now.strftime("%Y-W%W")

    # New week: reset and send fresh poll
    if poll.get("week_iso") != current_week:
        friday = _next_friday(now)
        saturday = _next_saturday(now)
        week_num = now.isocalendar()[1]

        msg_id = tg.send_poll(
            group_id, poll_topic,
            f"🗳️ Week {week_num}/52 — When are we playing?",
            [f"Friday {friday}", f"Saturday {saturday}"],
            is_anonymous=False,
            allows_multiple_answers=False,
        )

        state["session_poll"] = {
            "week_iso": current_week,
            "poll_message_id": msg_id,
            "voted_uids": [],
            "last_ping_day": -1,
        }
        poll = state["session_poll"]
        print(f"Session poll created (week {current_week})")

    # Daily ping for unvoted players (once per day)
    last_ping = poll.get("last_ping_day", -1)
    if weekday <= last_ping:
        return

    unvoted = _unvoted_mentions(config, state)
    voted, total = _vote_count(config, state)
    week_num = now.isocalendar()[1]

    if not unvoted:
        # Everyone voted — post confirmation once
        if not poll.get("all_voted_posted"):
            tg.send_message(group_id, poll_topic,
                            f"━━━━━━━━━━━━━━━━\n"
                            f"✅ Week {week_num}/52 — All {total} players have voted!")
            poll["all_voted_posted"] = True
            print(f"Session poll: all {total} voted")
        return

    unvoted_list = "\n".join(unvoted)

    if weekday == 4:
        header = f"⚠️ Week {week_num}/52 — Last chance to vote!"
    elif weekday == 0:
        header = f"🗳️ Week {week_num}/52 — New session poll is up!"
    else:
        header = f"🗳️ Week {week_num}/52 — Vote in the poll above!"

    ping_msg = (
        f"━━━━━━━━━━━━━━━━\n"
        f"{header}\n"
        f"{voted}/{total} voted.\n\n"
        f"Waiting on:\n{unvoted_list}"
    )

    if tg.send_message(group_id, poll_topic, ping_msg):
        poll["last_ping_day"] = weekday
        print(f"Session poll ping (day {weekday})")
