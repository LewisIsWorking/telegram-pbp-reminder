"""
Vote and timer commands.
"""

from datetime import datetime, timedelta, timezone

import helpers
import telegram as tg


def handle(ctx: dict) -> bool:
    """Handle vote and timer commands. Returns True if handled."""
    text = ctx["text"]
    user_id = ctx["user_id"]
    user_name = ctx["user_name"]
    gm_ids = ctx["gm_ids"]
    pid = ctx["pid"]
    campaign_name = ctx["campaign_name"]
    state = ctx["state"]
    group_id = ctx["group_id"]
    thread_id = ctx["thread_id"]
    now_iso = ctx["now_iso"]
    parsed = ctx["parsed"]
    raw_text = parsed["raw_text"]

    # ---- /vote command (GM only) ----
    if text.startswith("/vote") and not text.startswith("/votes") and user_id in gm_ids:
        raw_args = parsed["raw_text"][5:].strip()
        if not raw_args:
            tg.send_message(group_id, thread_id,
                            "Usage: /vote <question> | <option1> | <option2> [| ...]\n"
                            "e.g. /vote Where do we go? | North gate | Sewers | Stay and rest")
        else:
            parts = [p.strip() for p in raw_args.split("|")]
            if len(parts) < 3:
                tg.send_message(group_id, thread_id,
                                "Need a question and at least 2 options, separated by |\n"
                                "e.g. /vote Left or right? | Left | Right")
            else:
                question = parts[0]
                options = parts[1:]
                if len(options) > 6:
                    tg.send_message(group_id, thread_id, "Maximum 6 options per vote.")
                else:
                    state.setdefault("votes", {})[pid] = {
                        "question": question,
                        "options": options,
                        "results": {str(i): [] for i in range(1, len(options) + 1)},
                        "closed": False,
                        "created_at": now_iso,
                    }
                    # Build display
                    option_lines = "\n".join(f"  {i}. {opt}" for i, opt in enumerate(options, 1))
                    tg.send_message(group_id, thread_id,
                                    f"🗳️ Vote started!\n\n❓ {question}\n\n{option_lines}\n\n"
                                    f"Use /pick <N> to cast your vote.")
                    print(f"Vote started in {campaign_name}: {question}")
        return True

    # ---- /pick command (everyone) ----
    if text.startswith("/pick"):
        pick_str = parsed["raw_text"][5:].strip()
        vote = state.get("votes", {}).get(pid)
        if not vote or vote.get("closed"):
            tg.send_message(group_id, thread_id, "No active vote. GMs can start one with /vote")
        else:
            try:
                choice = int(pick_str)
                if 1 <= choice <= len(vote["options"]):
                    # Remove previous vote by this user
                    for key in vote["results"]:
                        vote["results"][key] = [n for n in vote["results"][key] if n != user_name]
                    # Add new vote
                    vote["results"][str(choice)].append(user_name)
                    tg.send_message(group_id, thread_id,
                                    f"✅ {user_name} voted for: {vote['options'][choice - 1]}")
                else:
                    tg.send_message(group_id, thread_id,
                                    f"Pick a number 1–{len(vote['options'])}.")
            except (ValueError, TypeError):
                tg.send_message(group_id, thread_id,
                                f"Usage: /pick <number>\ne.g. /pick 2")
        return True

    # ---- /endvote command (GM only) ----
    if text == "/endvote" and user_id in gm_ids:
        vote = state.get("votes", {}).get(pid)
        if not vote or vote.get("closed"):
            tg.send_message(group_id, thread_id, "No active vote to close.")
        else:
            vote["closed"] = True
            # Find winner
            results = vote["results"]
            best_count = max(len(v) for v in results.values())
            total = sum(len(v) for v in results.values())
            winners = [vote["options"][int(k) - 1] for k, v in results.items() if len(v) == best_count]

            lines = [f"🗳️ Vote closed — {vote['question']}", ""]
            for i, option in enumerate(vote["options"], 1):
                voters = results.get(str(i), [])
                count = len(voters)
                marker = " 👑" if count == best_count and count > 0 else ""
                voter_names = ", ".join(voters) if voters else "—"
                lines.append(f"  {i}. {option}: {count} ({voter_names}){marker}")
            lines.append("")
            if len(winners) == 1:
                lines.append(f"Winner: {winners[0]} ({best_count}/{total} votes)")
            elif best_count > 0:
                lines.append(f"Tied: {', '.join(winners)} ({best_count} each)")
            else:
                lines.append("No votes were cast.")
            tg.send_message(group_id, thread_id, "\n".join(lines))
        return True

    # ---- /timer command (GM only) ----
    if text.startswith("/timer") and not text.startswith("/timers") and user_id in gm_ids:
        raw_args = parsed["raw_text"][6:].strip()
        if not raw_args:
            tg.send_message(group_id, thread_id,
                            "Usage: /timer <duration> [reason]\n"
                            "e.g. /timer 24h Post your combat actions\n"
                            "e.g. /timer 2d\n"
                            "Durations: Nh (hours), Nm (minutes), Nd (days)")
        else:
            now_dt = datetime.fromisoformat(now_iso)
            deadline, reason = helpers.parse_timer_duration(raw_args, now_dt)
            if deadline is None:
                tg.send_message(group_id, thread_id,
                                "Couldn't parse duration. Use Nh, Nm, or Nd.\n"
                                "e.g. /timer 24h Post your actions")
            else:
                state.setdefault("timers", {})[pid] = {
                    "deadline": deadline.isoformat(),
                    "reason": reason,
                    "set_at": now_iso,
                    "set_by": user_name,
                }
                time_fmt = deadline.strftime("%b %d %H:%M UTC")
                reason_str = f"\n📝 {reason}" if reason else ""
                tg.send_message(group_id, thread_id,
                                f"⏳ Timer set! Deadline: {time_fmt}{reason_str}\n"
                                f"Use /showtimer to check remaining time.")
                print(f"Timer set in {campaign_name}: deadline {time_fmt}")
        return True

    # ---- /canceltimer command (GM only) ----
    if text == "/canceltimer" and user_id in gm_ids:
        if state.get("timers", {}).get(pid):
            del state["timers"][pid]
            tg.send_message(group_id, thread_id, f"⏳ Timer cancelled for {campaign_name}.")
        else:
            tg.send_message(group_id, thread_id, "No active timer to cancel.")
        return True

    return False
