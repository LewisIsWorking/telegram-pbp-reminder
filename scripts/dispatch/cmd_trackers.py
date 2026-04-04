"""
Tracker CRUD commands: notes, quests, pins, loot, NPCs.
"""

import telegram as tg
from commands.trackers import (
    _MAX_NOTES_PER_CAMPAIGN, _MAX_QUESTS_PER_CAMPAIGN,
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

    # ---- /note command (GM only) ----
    if text.startswith("/note") and not text.startswith("/notes") and user_id in gm_ids:
        note_text = parsed["raw_text"][5:].strip()
        if not note_text:
            tg.send_message(group_id, thread_id,
                            "Usage: /note <text>\ne.g. /note Party agreed to meet the informant at dawn")
        else:
            notes = state.setdefault("campaign_notes", {}).setdefault(pid, [])
            if len(notes) >= _MAX_NOTES_PER_CAMPAIGN:
                tg.send_message(group_id, thread_id,
                                f"Maximum {_MAX_NOTES_PER_CAMPAIGN} notes reached. Use /delnote <N> to remove old ones.")
            else:
                notes.append({"text": note_text, "created_at": now_iso})
                tg.send_message(group_id, thread_id,
                                f"📝 Note #{len(notes)} saved.")
                print(f"Note added to {campaign_name}: {note_text[:50]}")
        return True

    # ---- /delnote command (GM only) ----
    if text.startswith("/delnote") and user_id in gm_ids:
        num_str = parsed["raw_text"][8:].strip()
        notes = state.get("campaign_notes", {}).get(pid, [])
        try:
            idx = int(num_str) - 1
            if 0 <= idx < len(notes):
                removed = notes.pop(idx)
                tg.send_message(group_id, thread_id,
                                f"🗑️ Deleted note #{idx + 1}: {removed['text'][:60]}")
                print(f"Note deleted from {campaign_name}: {removed['text'][:50]}")
            else:
                tg.send_message(group_id, thread_id,
                                f"Note #{num_str} not found. Use /notes to see current notes.")
        except (ValueError, TypeError):  # pragma: no cover
            tg.send_message(group_id, thread_id,  # pragma: no cover
                            "Usage: /delnote <number>\ne.g. /delnote 3")
        return True

    # ---- /quest command (GM only) ----
    if text.startswith("/quest") and not text.startswith("/quests") and user_id in gm_ids:
        quest_text = parsed["raw_text"][6:].strip()
        if not quest_text:
            tg.send_message(group_id, thread_id,  # pragma: no cover
                            "Usage: /quest <text>\ne.g. /quest Find the missing merchant")
        else:
            quests = state.setdefault("quests", {}).setdefault(pid, [])
            if len(quests) >= _MAX_QUESTS_PER_CAMPAIGN:
                tg.send_message(group_id, thread_id,  # pragma: no cover
                                f"Maximum {_MAX_QUESTS_PER_CAMPAIGN} quests reached. Use /delquest <N> to remove old ones.")
            else:
                quests.append({"text": quest_text, "status": "active", "created_at": now_iso, "completed_at": None})
                tg.send_message(group_id, thread_id,
                                f"📋 Quest #{len(quests)} added: {quest_text}")
                print(f"Quest added to {campaign_name}: {quest_text[:50]}")
        return True

    # ---- /done command (GM only) ----
    if text.startswith("/done") and user_id in gm_ids:
        num_str = parsed["raw_text"][5:].strip()
        quests = state.get("quests", {}).get(pid, [])
        try:
            idx = int(num_str) - 1
            if 0 <= idx < len(quests):
                quests[idx]["status"] = "completed"
                quests[idx]["completed_at"] = now_iso
                tg.send_message(group_id, thread_id,
                                f"✅ Quest #{idx + 1} completed: {quests[idx]['text']}")
                print(f"Quest completed in {campaign_name}: {quests[idx]['text'][:50]}")
            else:
                tg.send_message(group_id, thread_id,
                                f"Quest #{num_str} not found. Use /quests to see current quests.")
        except (ValueError, TypeError):  # pragma: no cover
            tg.send_message(group_id, thread_id,  # pragma: no cover
                            "Usage: /done <number>\ne.g. /done 2")
        return True

    # ---- /delquest command (GM only) ----
    if text.startswith("/delquest") and user_id in gm_ids:
        num_str = parsed["raw_text"][9:].strip()
        quests = state.get("quests", {}).get(pid, [])
        try:
            idx = int(num_str) - 1
            if 0 <= idx < len(quests):
                removed = quests.pop(idx)
                tg.send_message(group_id, thread_id,
                                f"🗑️ Deleted quest #{idx + 1}: {removed['text'][:60]}")
                print(f"Quest deleted from {campaign_name}: {removed['text'][:50]}")
            else:
                tg.send_message(group_id, thread_id,  # pragma: no cover
                                f"Quest #{num_str} not found. Use /quests to see current quests.")
        except (ValueError, TypeError):
            tg.send_message(group_id, thread_id,
                            "Usage: /delquest <number>\ne.g. /delquest 3")
        return True

    return False
