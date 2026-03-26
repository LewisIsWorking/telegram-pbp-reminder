"""Session poll result announcement — fires Friday afternoon."""

from datetime import datetime, timezone

import telegram as tg


def announce_poll_result(config: dict, state: dict, *,
                         now: datetime | None = None, **_kw) -> None:
    """Announce poll winner on Friday afternoon (15:00 UTC / ~4pm BST)."""
    now = now or datetime.now(timezone.utc)

    if now.weekday() != 4 or now.hour < 15:
        return

    poll = state.get("session_poll", {})
    if poll.get("result_announced"):
        return

    poll_topic = None
    group_id = config["group_id"]
    for pair in config.get("topic_pairs", []):
        if pair.get("hybrid_live"):
            poll_topic = pair.get("chat_topic_id")
            break
    if not poll_topic:
        return

    votes = poll.get("votes", {})
    friday_count = len(votes.get("friday", []))
    saturday_count = len(votes.get("saturday", []))
    cant_count = len(votes.get("cant", []))
    week_num = now.isocalendar()[1]

    history = state.setdefault("poll_history", {"friday": 0, "saturday": 0})
    winner = "Tie"

    if friday_count > saturday_count:
        winner = "Friday"
        history["friday"] += 1
        msg = (f"━━━━━━━━━━━━━━━━\n"
               f"🎲 Week {week_num}/52 — Friday wins!\n"
               f"See you Friday night!")
    elif saturday_count > friday_count:
        winner = "Saturday"
        history["saturday"] += 1
        msg = (f"━━━━━━━━━━━━━━━━\n"
               f"🎲 Week {week_num}/52 — Saturday wins!\n"
               f"See you Saturday night!")
    else:
        msg = (f"━━━━━━━━━━━━━━━━\n"
               f"🎲 Week {week_num}/52 — It's a tie!\n"
               f"Friday: {friday_count}, Saturday: {saturday_count}.\n"
               f"GM's call!")

    # Archive this week's result
    archive = state.setdefault("poll_results", [])
    archive.append({
        "week": f"{now.year}-W{week_num:02d}",
        "date": now.strftime("%Y-%m-%d"),
        "winner": winner,
        "friday": friday_count,
        "saturday": saturday_count,
        "cant": cant_count,
        "friday_uids": votes.get("friday", []),
        "saturday_uids": votes.get("saturday", []),
        "cant_uids": votes.get("cant", []),
    })

    if cant_count:
        msg += f"\n({cant_count} can't make either)"

    total = history["friday"] + history["saturday"]
    if total > 0:
        msg += (f"\n\nAll-time: Fridays {history['friday']}/{total}, "
                f"Saturdays {history['saturday']}/{total}")

    if tg.send_message(group_id, poll_topic, msg):
        poll["result_announced"] = True
        print(f"Poll result: {winner}")
