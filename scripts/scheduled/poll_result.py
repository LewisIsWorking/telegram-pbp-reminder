"""Session poll result announcement — fires Friday afternoon for each campaign."""

from datetime import datetime, timezone

import telegram as tg
from helpers_pkg.groups import group_id_for_campaign


def announce_poll_result(config: dict, state: dict, *,
                         now: datetime | None = None, **_kw) -> None:
    """Announce poll winner on Friday afternoon (15:00 UTC) for each hybrid camp."""
    now = now or datetime.now(timezone.utc)
    if now.weekday() != 4 or now.hour < 15:
        return

    polls = state.get("session_poll", {})
    week_num = now.isocalendar()[1]

    for pair in config.get("topic_pairs", []):
        if not pair.get("hybrid_live"):
            continue
        code = pair.get("code", "")
        poll = polls.get(code, {})
        if poll.get("result_announced"):
            continue

        pid = str(pair["pbp_topic_ids"][0])
        gid = group_id_for_campaign(config, pid)
        poll_tid = pair.get("chat_topic_id")
        if not poll_tid:
            continue

        votes = poll.get("votes", {})
        fri = len(votes.get("friday", []))
        sat = len(votes.get("saturday", []))
        cant = len(votes.get("cant", []))

        history = state.setdefault("poll_history", {})
        camp_hist = history.setdefault(code, {"friday": 0, "saturday": 0})

        if fri > sat:
            winner = "Friday"
            camp_hist["friday"] += 1
            msg = (f"━━━━━━━━━━━━━━━━\n"
                   f"🎲 {code} Week {week_num}/52 — Friday wins!\n"
                   f"See you Friday night!")
        elif sat > fri:
            winner = "Saturday"
            camp_hist["saturday"] += 1
            msg = (f"━━━━━━━━━━━━━━━━\n"
                   f"🎲 {code} Week {week_num}/52 — Saturday wins!\n"
                   f"See you Saturday night!")
        else:
            winner = "Tie"
            msg = (f"━━━━━━━━━━━━━━━━\n"
                   f"🎲 {code} Week {week_num}/52 — It's a tie!\n"
                   f"Friday: {fri}, Saturday: {sat}. GM's call!")

        if cant:
            msg += f"\n({cant} can't make either)"

        total = camp_hist["friday"] + camp_hist["saturday"]
        if total > 0:
            msg += (f"\n\nAll-time: Fridays {camp_hist['friday']}/{total}, "
                    f"Saturdays {camp_hist['saturday']}/{total}")

        archive = state.setdefault("poll_results", [])
        archive.append({
            "week": f"{now.year}-W{week_num:02d}", "code": code,
            "date": now.strftime("%Y-%m-%d"), "winner": winner,
            "friday": fri, "saturday": sat, "cant": cant,
            "friday_uids": votes.get("friday", []),
            "saturday_uids": votes.get("saturday", []),
            "cant_uids": votes.get("cant", []),
        })

        if tg.send_message(gid, poll_tid, msg):
            poll["result_announced"] = True
            print(f"Poll result: {code} → {winner}")
