"""
Player commands: away, back, chooseboon, roll.
"""

from datetime import datetime, timedelta, timezone

import helpers
import telegram as tg


def handle(ctx: dict) -> bool:
    """Handle player commands. Returns True if handled."""
    text = ctx["text"]
    user_id = ctx["user_id"]
    user_name = ctx["user_name"]
    pid = ctx["pid"]
    campaign_name = ctx["campaign_name"]
    state = ctx["state"]
    config = ctx["config"]
    group_id = ctx["group_id"]
    thread_id = ctx["thread_id"]
    now_iso = ctx["now_iso"]
    parsed = ctx["parsed"]
    raw_text = parsed["raw_text"]

    # ---- /away command (everyone) ----
    if text.startswith("/away"):
        args = parsed["raw_text"][5:].strip()
        now_dt = datetime.fromisoformat(now_iso)
        until_dt, reason = helpers.parse_away_duration(args, now_dt)
        away_key = f"{pid}:{user_id}"
        state.setdefault("away", {})[away_key] = {
            "until": until_dt.isoformat() if until_dt else None,
            "reason": reason,
            "set_at": now_iso,
        }
        if until_dt:
            until_str = f"{until_dt.strftime('%b %d')} (W{until_dt.isocalendar()[1]})"
            msg = f"✈️ {user_name} marked as away until {until_str}.\nReason: {reason}"
        else:
            msg = f"✈️ {user_name} marked as away (indefinite).\nReason: {reason}"
        msg += "\nUse /back when you return."
        print(f"Away: {user_name} in {campaign_name} — {reason}")
        tg.send_message(group_id, thread_id, msg)
        return True

    # ---- /back command (everyone) ----
    if text == "/back":
        away_key = f"{pid}:{user_id}"
        if away_key in state.get("away", {}):
            del state["away"][away_key]
            char_name = helpers.character_name(config, pid, user_id)
            char_tag = f" ({char_name})" if char_name else ""
            tg.send_message(group_id, thread_id,
                            f"👋 {user_name}{char_tag} is back!")
            print(f"Back: {user_name} in {campaign_name}")
        else:
            tg.send_message(group_id, thread_id,
                            f"You're not currently marked as away.")
        return True

    # ---- /available command (everyone) ----
    if text.startswith("/available"):
        args = parsed["raw_text"][10:].strip().lower()
        avail = state.setdefault("availability", {}).setdefault(pid, {})

        if not args or args == "show":
            # Show this campaign's availability
            if not avail:
                tg.send_message(group_id, thread_id,
                                f"No availability set in {campaign_name}.\n"
                                f"Set yours: /available mon wed fri")
            else:
                lines = [f"📅 Availability for {campaign_name}:\n"]
                day_order = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
                for uid, data in sorted(avail.items(), key=lambda x: x[1].get("name", "")):
                    days = data.get("days", [])
                    day_str = ", ".join(d.capitalize() for d in day_order if d in days)
                    lines.append(f"  {data['name']}: {day_str or 'not set'}")
                tg.send_message(group_id, thread_id, "\n".join(lines))
        elif args == "clear":
            avail.pop(user_id, None)
            tg.send_message(group_id, thread_id,
                            f"Cleared availability for {user_name}.")
        else:
            day_map = {
                "mon": "mon", "monday": "mon", "tue": "tue", "tuesday": "tue",
                "wed": "wed", "wednesday": "wed", "thu": "thu", "thursday": "thu",
                "fri": "fri", "friday": "fri", "sat": "sat", "saturday": "sat",
                "sun": "sun", "sunday": "sun",
            }
            days = []
            for word in args.split():
                d = day_map.get(word.rstrip(","))
                if d and d not in days:
                    days.append(d)
            if not days:
                tg.send_message(group_id, thread_id,
                                "Usage: /available mon wed fri\n"
                                "Or: /available clear")
            else:
                avail[user_id] = {"name": user_name, "days": days}
                day_str = ", ".join(d.capitalize() for d in days)
                tg.send_message(group_id, thread_id,
                                f"📅 {user_name} available: {day_str}")
        return True

    # ---- /chooseboon command (POTW winner fallback for broken buttons) ----
    if text.startswith("/chooseboon"):
        num_str = parsed["raw_text"][11:].strip()
        try:
            choice = int(num_str)
        except ValueError:
            tg.send_message(group_id, thread_id, "Usage: /chooseboon <number>")
        else:
            result = choose_boon_by_text(pid, user_id, choice, config, state)
            tg.send_message(group_id, thread_id, result)
        return True

    # ---- /roll command (everyone) ----
    if text.startswith("/roll"):
        import re
        raw = re.sub(r"^/roll(@\S+)?", "", parsed["raw_text"]).strip()
        dice_expr = raw
        if not dice_expr:
            tg.send_message(group_id, thread_id,
                            "Usage: /roll <dice> [label]\n"
                            "e.g. /roll 1d20+5 Stealth\n"
                            "e.g. /roll 2d6+3\n"
                            "e.g. /roll 4d6kh3 (keep highest 3)")
        else:
            result = helpers.roll_dice(dice_expr)
            if result.get("error"):
                tg.send_message(group_id, thread_id, result["error"])
            else:
                char_name = helpers.character_name(config, pid, user_id)
                roller = char_name or user_name
                label = result["label"]

                lines = []
                grand_total = 0
                for r in result["results"]:
                    grand_total += r["total"]
                    lines.append(f"  {r['expr']}: {r['detail']} = {r['total']}")

                header = f"🎲 {roller}"
                if label:
                    header += f" — {label}"
                header += ":"

                if len(result["results"]) == 1:
                    r = result["results"][0]
                    msg = f"{header}\n  {r['detail']} = {r['total']}"
                else:
                    msg = header + "\n" + "\n".join(lines) + f"\n  Total: {grand_total}"

                tg.send_message(group_id, thread_id, msg)
        return True

    return False
