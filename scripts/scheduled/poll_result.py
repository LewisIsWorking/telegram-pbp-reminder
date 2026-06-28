"""Session poll result announcement — fires Friday afternoon for each campaign."""

from datetime import datetime, timezone

import telegram as tg
from helpers_pkg.groups import group_id_for_campaign
from scheduled.session_poll_build import poll_options_for, option_tally


def announce_poll_result(config: dict, state: dict, *,
                         now: datetime | None = None, **_kw) -> None:
    """Announce poll winner Friday 15:00 UTC for each hybrid campaign."""
    now = now or datetime.now(timezone.utc)
    if now.weekday() != 4 or now.hour < 15:
        return

    polls = state.get("session_poll", {})
    week_num = now.isocalendar()[1]

    for pair in config.get("topic_pairs", []):
        if not pair.get("hybrid_live") or pair.get("session_poll_disabled"):
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

        options = poll_options_for(pair, now)
        votes = poll.get("votes", {})

        # Find winner: option with most votes
        counts = {i: len(votes.get(str(i), [])) for i in range(len(options))}
        max_votes = max(counts.values(), default=0)
        winners = [i for i, c in counts.items() if c == max_votes and c > 0]
        tally_parts = option_tally(votes, options)
        tally_str = " / ".join(tally_parts) if tally_parts else "No votes"

        history = state.setdefault("poll_history", {})
        camp_hist = history.setdefault(code, {"wins": {}})

        if len(winners) == 1:
            w_label = options[winners[0]].split()[0]
            camp_hist["wins"][str(winners[0])] = camp_hist["wins"].get(str(winners[0]), 0) + 1
            msg = (f"━━━━━━━━━━━━━━━━\n"
                   f"🎲 {code} Week {week_num}/52 — {w_label} wins!\n"
                   f"{tally_str}")
        else:
            msg = (f"━━━━━━━━━━━━━━━━\n"
                   f"🎲 {code} Week {week_num}/52 — It's a tie!\n"
                   f"{tally_str}\nGM's call!")

        # All-time summary
        wins = camp_hist.get("wins", {})
        total_wins = sum(wins.values())
        if total_wins > 0:
            win_parts = [f"{options[int(i)].split()[0]}: {w}"
                         for i, w in sorted(wins.items()) if w]
            msg += f"\n\nAll-time: {', '.join(win_parts)}"

        archive = state.setdefault("poll_results", [])
        archive.append({
            "week": f"{now.year}-W{week_num:02d}", "code": code,
            "date": now.strftime("%Y-%m-%d"),
            "votes": {options[int(i)]: len(uids)
                      for i, uids in votes.items()},
        })

        if tg.send_message(gid, poll_tid, msg):
            poll["result_announced"] = True
            print(f"Poll result announced: {code} week {week_num}")
