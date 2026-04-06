"""
Tracker CRUD commands: pins, loot, NPCs.
"""

import telegram as tg
from commands.trackers import (
    _MAX_PINS_PER_CAMPAIGN, _MAX_LOOT_PER_CAMPAIGN, _MAX_NPCS_PER_CAMPAIGN,
)


def handle(ctx: dict) -> bool:
    """Handle tracker CRUD commands. Returns True if handled."""
    cmd = ctx["cmd_word"]
    text = ctx["text"]
    user_id = ctx["user_id"]
    gm_ids = ctx["gm_ids"]
    pid = ctx["pid"]
    campaign_name = ctx["campaign_name"]
    state = ctx["state"]
    group_id = ctx["group_id"]
    thread_id = ctx["thread_id"]
    now_iso = ctx["now_iso"]
    user_name = ctx["user_name"]
    parsed = ctx["parsed"]
    raw_text = parsed["raw_text"]
    # ---- /pin command (GM only) ----
    if text.startswith("/pin") and not text.startswith("/pins") and user_id in gm_ids:
        pin_text = parsed["raw_text"][4:].strip()
        if not pin_text:
            tg.send_message(group_id, thread_id,  # pragma: no cover
                            "Usage: /pin <text>\ne.g. /pin The party discovered the hidden temple entrance")
        else:
            pins = state.setdefault("pins", {}).setdefault(pid, [])
            if len(pins) >= _MAX_PINS_PER_CAMPAIGN:
                tg.send_message(group_id, thread_id,  # pragma: no cover
                                f"Maximum {_MAX_PINS_PER_CAMPAIGN} pins reached. Use /delpin <N> to remove old ones.")
            else:
                pins.append({"text": pin_text, "created_at": now_iso, "author": user_name})
                tg.send_message(group_id, thread_id,
                                f"📌 Pin #{len(pins)} saved: {pin_text}")
                print(f"Pin added to {campaign_name}: {pin_text[:50]}")
        return True

    # ---- /delpin command (GM only) ----
    if text.startswith("/delpin") and user_id in gm_ids:
        num_str = parsed["raw_text"][7:].strip()
        pins = state.get("pins", {}).get(pid, [])
        try:
            idx = int(num_str) - 1
            if 0 <= idx < len(pins):
                removed = pins.pop(idx)
                tg.send_message(group_id, thread_id,
                                f"🗑️ Deleted pin #{idx + 1}: {removed['text'][:60]}")
            else:
                tg.send_message(group_id, thread_id,  # pragma: no cover
                                f"Pin #{num_str} not found. Use /pins to see current pins.")  # pragma: no cover
        except (ValueError, TypeError):  # pragma: no cover
            tg.send_message(group_id, thread_id,  # pragma: no cover
                            "Usage: /delpin <number>\ne.g. /delpin 3")
        return True

    # ---- /loot command (GM only) ----
    if text.startswith("/loot") and not text.startswith("/lootlist") and user_id in gm_ids:
        loot_text = parsed["raw_text"][5:].strip()
        if not loot_text:
            tg.send_message(group_id, thread_id,  # pragma: no cover
                            "Usage: /loot <item>\ne.g. /loot +1 striking longsword")
        else:
            loot = state.setdefault("loot", {}).setdefault(pid, [])
            if len(loot) >= _MAX_LOOT_PER_CAMPAIGN:
                tg.send_message(group_id, thread_id,  # pragma: no cover
                                f"Maximum {_MAX_LOOT_PER_CAMPAIGN} items. Use /delloot <N> to remove.")
            else:
                loot.append({"text": loot_text, "added_at": now_iso})
                tg.send_message(group_id, thread_id,
                                f"💰 Loot #{len(loot)}: {loot_text}")
                print(f"Loot added to {campaign_name}: {loot_text[:50]}")
        return True

    # ---- /delloot command (GM only) ----
    if text.startswith("/delloot") and user_id in gm_ids:
        num_str = parsed["raw_text"][8:].strip()
        loot = state.get("loot", {}).get(pid, [])
        try:
            idx = int(num_str) - 1
            if 0 <= idx < len(loot):
                removed = loot.pop(idx)
                tg.send_message(group_id, thread_id,
                                f"🗑️ Removed loot #{idx + 1}: {removed['text'][:60]}")
            else:
                tg.send_message(group_id, thread_id,
                                f"Loot #{num_str} not found. Use /lootlist to see items.")
        except (ValueError, TypeError):  # pragma: no cover
            tg.send_message(group_id, thread_id,  # pragma: no cover
                            "Usage: /delloot <number>\ne.g. /delloot 3")
        return True

    # ---- /npc command (GM only) ----
    if text.startswith("/npc") and not text.startswith("/npcs") and user_id in gm_ids:
        raw_args = parsed["raw_text"][4:].strip()
        if not raw_args:
            tg.send_message(group_id, thread_id,  # pragma: no cover
                            "Usage: /npc <name> — <description>\n"
                            "e.g. /npc Gorund — Dwarven blacksmith, owes party a favour")
        else:
            npcs = state.setdefault("npcs", {}).setdefault(pid, [])
            if len(npcs) >= _MAX_NPCS_PER_CAMPAIGN:
                tg.send_message(group_id, thread_id,  # pragma: no cover
                                f"Maximum {_MAX_NPCS_PER_CAMPAIGN} NPCs. Use /delnpc <N> to remove.")
            else:
                # Split on em-dash or double-hyphen
                if " — " in raw_args:
                    name, desc = raw_args.split(" — ", 1)
                elif " -- " in raw_args:
                    name, desc = raw_args.split(" -- ", 1)  # pragma: no cover
                elif " - " in raw_args:
                    name, desc = raw_args.split(" - ", 1)  # pragma: no cover
                else:
                    name, desc = raw_args, ""
                npcs.append({"name": name.strip(), "desc": desc.strip(), "added_at": now_iso})
                tg.send_message(group_id, thread_id,
                                f"🎭 NPC #{len(npcs)}: {name.strip()}")
                print(f"NPC added to {campaign_name}: {name.strip()[:50]}")
        return True

    # ---- /delnpc command (GM only) ----
    if text.startswith("/delnpc") and user_id in gm_ids:
        num_str = parsed["raw_text"][7:].strip()
        npcs = state.get("npcs", {}).get(pid, [])
        try:
            idx = int(num_str) - 1
            if 0 <= idx < len(npcs):
                removed = npcs.pop(idx)
                tg.send_message(group_id, thread_id,
                                f"🗑️ Removed NPC #{idx + 1}: {removed['name']}")
            else:
                tg.send_message(group_id, thread_id,
                                f"NPC #{num_str} not found. Use /npcs to see the list.")
        except (ValueError, TypeError):
            tg.send_message(group_id, thread_id,
                            "Usage: /delnpc <number>\ne.g. /delnpc 3")
        return True

    return False
