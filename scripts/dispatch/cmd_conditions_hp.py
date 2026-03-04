"""
Condition and HP tracker write commands.
"""

import helpers
import telegram as tg
from commands.mechanics import _MAX_HP_ENTRIES


def handle(ctx: dict) -> bool:
    """Handle condition and HP write commands. Returns True if handled."""
    text = ctx["text"]
    user_id = ctx["user_id"]
    gm_ids = ctx["gm_ids"]
    pid = ctx["pid"]
    campaign_name = ctx["campaign_name"]
    state = ctx["state"]
    group_id = ctx["group_id"]
    thread_id = ctx["thread_id"]
    reply_topic = ctx["reply_topic"]
    now_iso = ctx["now_iso"]
    parsed = ctx["parsed"]
    raw_text = parsed["raw_text"]

    # ---- /condition command (GM only) ----
    if text.startswith("/condition") and not text.startswith("/conditions") and user_id in gm_ids:
        raw_args = parsed["raw_text"][10:].strip()
        if not raw_args:
            tg.send_message(group_id, thread_id,
                            "Usage: /condition <target> — <effect> [| duration]\n"
                            "e.g. /condition Cardigan — Frightened 2 | until end of next turn\n"
                            "e.g. /condition All — Inspired +1")
        else:
            # Parse: target — effect [| duration]
            if " — " in raw_args:
                target, rest = raw_args.split(" — ", 1)
            elif " -- " in raw_args:
                target, rest = raw_args.split(" -- ", 1)
            elif " - " in raw_args:
                target, rest = raw_args.split(" - ", 1)
            else:
                target, rest = raw_args, ""

            if "|" in rest:
                effect, duration = rest.split("|", 1)
            else:
                effect, duration = rest, ""

            conds = state.setdefault("conditions", {}).setdefault(pid, [])
            conds.append({
                "target": target.strip(),
                "effect": effect.strip(),
                "duration": duration.strip(),
                "added_at": now_iso,
            })
            tg.send_message(group_id, thread_id,
                            f"⚡ Condition on {target.strip()}: {effect.strip()}")
            print(f"Condition in {campaign_name}: {target.strip()} — {effect.strip()[:50]}")
        return True

    # ---- /endcondition command (GM only) ----
    if text.startswith("/endcondition") and user_id in gm_ids:
        num_str = parsed["raw_text"][13:].strip()
        conds = state.get("conditions", {}).get(pid, [])
        try:
            idx = int(num_str) - 1
            if 0 <= idx < len(conds):
                removed = conds.pop(idx)
                tg.send_message(group_id, thread_id,
                                f"✅ Ended: {removed['target']} — {removed['effect']}")
            else:
                tg.send_message(group_id, thread_id,
                                f"Condition #{num_str} not found. Use /conditions to see list.")
        except (ValueError, TypeError):
            tg.send_message(group_id, thread_id,
                            "Usage: /endcondition <number>\ne.g. /endcondition 2")
        return True

    # ---- /clearconditions command (GM only) ----
    if text == "/clearconditions" and user_id in gm_ids:
        old = state.get("conditions", {}).get(pid, [])
        count = len(old)
        state.setdefault("conditions", {})[pid] = []
        tg.send_message(group_id, thread_id,
                        f"✅ Cleared {count} condition{'s' if count != 1 else ''} from {campaign_name}.")
        return True

    # ---- /hp command (GM set/damage/heal/remove/clear, everyone view) ----
    if text.startswith("/hp"):
        hp_args = parsed["raw_text"][3:].strip()
        hp_tracker = state.setdefault("hp_tracker", {}).setdefault(pid, {})

        if not hp_args or hp_args == "show":
            # View HP tracker
            report = build_hp_tracker(pid, campaign_name, state)
            tg.send_message(group_id, reply_topic, report)

        elif user_id in gm_ids:
            parts = hp_args.split(None, 1)
            sub = parts[0].lower()
            rest = parts[1] if len(parts) > 1 else ""

            if sub == "set":
                # /hp set <name> <current>/<max>
                set_parts = rest.rsplit(None, 1)
                if len(set_parts) == 2 and "/" in set_parts[1]:
                    name = set_parts[0].strip()
                    try:
                        cur, mx = set_parts[1].split("/", 1)
                        cur, mx = int(cur), int(mx)
                        if mx <= 0 or mx > 9999:
                            tg.send_message(group_id, thread_id, "Max HP must be 1–9999.")
                        elif len(hp_tracker) >= _MAX_HP_ENTRIES and name not in hp_tracker:
                            tg.send_message(group_id, thread_id,
                                            f"Max {_MAX_HP_ENTRIES} entries. Use /hp remove <name> first.")
                        else:
                            hp_tracker[name] = {"current": min(cur, mx), "max": mx}
                            icon = helpers.hp_status_icon(min(cur, mx), mx)
                            bar = helpers.hp_bar(min(cur, mx), mx)
                            tg.send_message(group_id, thread_id,
                                            f"{icon} {name}: {bar}")
                    except ValueError:
                        tg.send_message(group_id, thread_id,
                                        "Usage: /hp set <name> <current>/<max>\ne.g. /hp set Ogre 45/45")
                else:
                    tg.send_message(group_id, thread_id,
                                    "Usage: /hp set <name> <current>/<max>\ne.g. /hp set Ogre 45/45")

            elif sub in ("d", "damage"):
                # /hp d <name> <amount>
                dmg_parts = rest.rsplit(None, 1)
                if len(dmg_parts) == 2:
                    name = dmg_parts[0].strip()
                    try:
                        amount = int(dmg_parts[1])
                        if name in hp_tracker:
                            hp = hp_tracker[name]
                            hp["current"] = max(0, hp["current"] - amount)
                            icon = helpers.hp_status_icon(hp["current"], hp["max"])
                            bar = helpers.hp_bar(hp["current"], hp["max"])
                            status = " 💀 DOWN!" if hp["current"] == 0 else ""
                            tg.send_message(group_id, thread_id,
                                            f"{icon} {name} takes {amount} damage!\n{bar}{status}")
                        else:
                            tg.send_message(group_id, thread_id,
                                            f"No HP entry for '{name}'. Use /hp set {name} <hp>/<max> first.")
                    except ValueError:
                        tg.send_message(group_id, thread_id,
                                        "Usage: /hp d <name> <amount>\ne.g. /hp d Ogre 12")
                else:
                    tg.send_message(group_id, thread_id,
                                    "Usage: /hp d <name> <amount>\ne.g. /hp d Ogre 12")

            elif sub in ("h", "heal"):
                # /hp h <name> <amount>
                heal_parts = rest.rsplit(None, 1)
                if len(heal_parts) == 2:
                    name = heal_parts[0].strip()
                    try:
                        amount = int(heal_parts[1])
                        if name in hp_tracker:
                            hp = hp_tracker[name]
                            hp["current"] = min(hp["max"], hp["current"] + amount)
                            icon = helpers.hp_status_icon(hp["current"], hp["max"])
                            bar = helpers.hp_bar(hp["current"], hp["max"])
                            tg.send_message(group_id, thread_id,
                                            f"{icon} {name} healed {amount}!\n{bar}")
                        else:
                            tg.send_message(group_id, thread_id,
                                            f"No HP entry for '{name}'. Use /hp set {name} <hp>/<max> first.")
                    except ValueError:
                        tg.send_message(group_id, thread_id,
                                        "Usage: /hp h <name> <amount>\ne.g. /hp h Ogre 10")
                else:
                    tg.send_message(group_id, thread_id,
                                    "Usage: /hp h <name> <amount>\ne.g. /hp h Ogre 10")

            elif sub == "remove":
                name = rest.strip()
                if name in hp_tracker:
                    del hp_tracker[name]
                    tg.send_message(group_id, thread_id, f"🗑️ Removed {name} from HP tracker.")
                else:
                    tg.send_message(group_id, thread_id,
                                    f"No HP entry for '{name}'. Use /hp to see entries.")

            elif sub == "clear":
                count = len(hp_tracker)
                state["hp_tracker"][pid] = {}
                tg.send_message(group_id, thread_id,
                                f"✅ Cleared {count} HP entr{'ies' if count != 1 else 'y'}.")

            else:
                tg.send_message(group_id, thread_id,
                                "Usage: /hp set <n> <cur>/<max> | /hp d <n> <amt> | "
                                "/hp h <n> <amt> | /hp remove <n> | /hp clear")
        return True

    return False
