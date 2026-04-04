"""
Progress clock commands.
"""

import helpers
import telegram as tg
from commands.mechanics import _MAX_CLOCKS


def handle(ctx: dict) -> bool:
    """Handle clock commands. Returns True if handled."""
    text = ctx["text"]
    user_id = ctx["user_id"]
    gm_ids = ctx["gm_ids"]
    pid = ctx["pid"]
    campaign_name = ctx["campaign_name"]
    state = ctx["state"]
    group_id = ctx["group_id"]
    thread_id = ctx["thread_id"]
    parsed = ctx["parsed"]
    raw_text = parsed["raw_text"]

    # ---- /clock command (GM only) ----
    if text.startswith("/clock") and not text.startswith("/clocks") and user_id in gm_ids:
        clock_args = parsed["raw_text"][6:].strip()
        if not clock_args:
            tg.send_message(group_id, thread_id,
                            "Usage: /clock <name> <segments>\ne.g. /clock Investigation 6\ne.g. /clock Ritual 4")
        else:
            clock_parts = clock_args.rsplit(None, 1)
            if len(clock_parts) == 2:
                name = clock_parts[0].strip()
                try:
                    segments = int(clock_parts[1])
                    if segments < 2 or segments > 12:
                        tg.send_message(group_id, thread_id, "Segments must be 2–12.")
                    else:
                        clocks = state.setdefault("clocks", {}).setdefault(pid, {})
                        if len(clocks) >= _MAX_CLOCKS and name not in clocks:
                            tg.send_message(group_id, thread_id,  # pragma: no cover
                                            f"Max {_MAX_CLOCKS} clocks. Use /delclock <name> first.")
                        else:
                            clocks[name] = {"filled": 0, "segments": segments}
                            display = helpers.clock_display(0, segments)
                            tg.send_message(group_id, thread_id,
                                            f"⏱️ Clock: {name}\n{display}")
                except ValueError:
                    tg.send_message(group_id, thread_id,
                                    "Usage: /clock <name> <segments>\ne.g. /clock Investigation 6")
            else:
                tg.send_message(group_id, thread_id,
                                "Usage: /clock <name> <segments>\ne.g. /clock Investigation 6")
        return True

    # ---- /tick command (GM only) ----
    if text.startswith("/tick") and not text.startswith("/ticker") and user_id in gm_ids:
        tick_args = parsed["raw_text"][5:].strip()
        clocks = state.get("clocks", {}).get(pid, {})
        if not tick_args:
            tg.send_message(group_id, thread_id,  # pragma: no cover
                            "Usage: /tick <name> [N]\ne.g. /tick Investigation 2")
        else:
            tick_parts = tick_args.rsplit(None, 1)
            amount = 1
            name = tick_args
            if len(tick_parts) == 2:
                try:
                    amount = int(tick_parts[1])
                    name = tick_parts[0]
                except ValueError:
                    name = tick_args
                    amount = 1
            name = name.strip()
            if name in clocks:
                clock = clocks[name]
                clock["filled"] = min(clock["segments"], clock["filled"] + amount)
                display = helpers.clock_display(clock["filled"], clock["segments"])
                complete = " ✅ COMPLETE!" if clock["filled"] >= clock["segments"] else ""
                tg.send_message(group_id, thread_id,
                                f"⏱️ {name}\n{display}{complete}")
            else:
                tg.send_message(group_id, thread_id,
                                f"No clock named '{name}'. Use /clocks to see all.")
        return True

    # ---- /untick command (GM only) ----
    if text.startswith("/untick") and user_id in gm_ids:
        tick_args = parsed["raw_text"][7:].strip()
        clocks = state.get("clocks", {}).get(pid, {})
        if not tick_args:
            tg.send_message(group_id, thread_id,  # pragma: no cover
                            "Usage: /untick <name> [N]\ne.g. /untick Investigation 1")
        else:
            tick_parts = tick_args.rsplit(None, 1)
            amount = 1
            name = tick_args
            if len(tick_parts) == 2:
                try:
                    amount = int(tick_parts[1])
                    name = tick_parts[0]
                except ValueError:
                    name = tick_args
                    amount = 1
            name = name.strip()
            if name in clocks:
                clock = clocks[name]
                clock["filled"] = max(0, clock["filled"] - amount)
                display = helpers.clock_display(clock["filled"], clock["segments"])
                tg.send_message(group_id, thread_id, f"⏱️ {name}\n{display}")
            else:
                tg.send_message(group_id, thread_id,
                                f"No clock named '{name}'. Use /clocks to see all.")
        return True

    # ---- /delclock command (GM only) ----
    if text.startswith("/delclock") and user_id in gm_ids:
        name = parsed["raw_text"][9:].strip()
        clocks = state.get("clocks", {}).get(pid, {})
        if name in clocks:
            del clocks[name]
            tg.send_message(group_id, thread_id, f"🗑️ Removed clock: {name}")
        else:
            tg.send_message(group_id, thread_id,
                            f"No clock named '{name}'. Use /clocks to see all.")
        return True

    return False
