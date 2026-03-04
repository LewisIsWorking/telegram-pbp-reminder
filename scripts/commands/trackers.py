"""
Tracker display builders.

Read-only commands: /notes, /quests, /pins, /lootlist, /npcs, /conditions.
"""

_MAX_NOTES_PER_CAMPAIGN = 20
_MAX_QUESTS_PER_CAMPAIGN = 20
_MAX_PINS_PER_CAMPAIGN = 30
_MAX_LOOT_PER_CAMPAIGN = 50
_MAX_NPCS_PER_CAMPAIGN = 40


def build_notes(pid: str, campaign_name: str, state: dict) -> str:
    """Build the notes list for /notes command."""
    notes = state.get("campaign_notes", {}).get(pid, [])
    if not notes:
        return f"No GM notes for {campaign_name}.\nGMs can add notes with /note <text>"

    lines = [f"📝 GM Notes — {campaign_name}:", ""]
    for i, note in enumerate(notes, 1):
        created = note.get("created_at", "")[:10]  # YYYY-MM-DD
        lines.append(f"{i}. {note['text']}")
        if created:
            lines.append(f"   ({created})")
    lines.append("")
    lines.append(f"{len(notes)}/20 notes. GMs: /note <text> to add, /delnote <N> to remove.")
    return "\n".join(lines)


def build_quests(pid: str, campaign_name: str, state: dict) -> str:
    """Build the quest list for /quests command."""
    quests = state.get("quests", {}).get(pid, [])
    if not quests:
        return f"No quests tracked for {campaign_name}.\nGMs can add quests with /quest <text>"

    active = [(i, q) for i, q in enumerate(quests, 1) if q.get("status") == "active"]
    completed = [(i, q) for i, q in enumerate(quests, 1) if q.get("status") == "completed"]

    lines = [f"📋 Quests — {campaign_name}:", ""]

    if active:
        lines.append("Active:")
        for i, q in active:
            lines.append(f"  {i}. {q['text']}")
    if completed:
        lines.append("")
        lines.append("Completed:")
        for i, q in completed:
            done_date = (q.get("completed_at") or "")[:10]
            lines.append(f"  ✅ {i}. {q['text']} ({done_date})")

    lines.append("")
    total = len(quests)
    lines.append(f"{len(active)} active, {len(completed)} completed ({total}/{_MAX_QUESTS_PER_CAMPAIGN}).")
    lines.append("GMs: /quest <text>, /done <N>, /delquest <N>")
    return "\n".join(lines)


def build_pins(pid: str, campaign_name: str, state: dict) -> str:
    """Build the pins list for /pins command."""
    pins = state.get("pins", {}).get(pid, [])
    if not pins:
        return f"No pins for {campaign_name}.\nGMs can bookmark moments with /pin <text>"

    lines = [f"📌 Pins — {campaign_name}:", ""]
    for i, pin in enumerate(pins, 1):
        created = pin.get("created_at", "")[:10]
        author = pin.get("author", "")
        author_tag = f" — {author}" if author else ""
        lines.append(f"{i}. {pin['text']}")
        if created:
            lines.append(f"   ({created}{author_tag})")
    lines.append("")
    lines.append(f"{len(pins)}/{_MAX_PINS_PER_CAMPAIGN} pins. GMs: /pin <text>, /delpin <N>")
    return "\n".join(lines)


def build_lootlist(pid: str, campaign_name: str, state: dict) -> str:
    """Build the loot list for /lootlist command."""
    loot = state.get("loot", {}).get(pid, [])
    if not loot:
        return f"No loot tracked for {campaign_name}.\nGMs can add items with /loot <text>"

    lines = [f"💰 Party Loot — {campaign_name}:", ""]
    for i, item in enumerate(loot, 1):
        lines.append(f"  {i}. {item['text']}")
    lines.append("")
    lines.append(f"{len(loot)}/{_MAX_LOOT_PER_CAMPAIGN} items. GMs: /loot <text>, /delloot <N>")
    return "\n".join(lines)


def build_npcs(pid: str, campaign_name: str, state: dict) -> str:
    """Build the NPC list for /npcs command."""
    npcs = state.get("npcs", {}).get(pid, [])
    if not npcs:
        return f"No NPCs tracked for {campaign_name}.\nGMs can add NPCs with /npc <n> — <description>"

    lines = [f"🎭 NPCs — {campaign_name}:", ""]
    for i, npc in enumerate(npcs, 1):
        desc = npc.get("desc", "")
        desc_str = f" — {desc}" if desc else ""
        lines.append(f"  {i}. {npc['name']}{desc_str}")
    lines.append("")
    lines.append(f"{len(npcs)}/{_MAX_NPCS_PER_CAMPAIGN} NPCs. GMs: /npc <n> — <desc>, /delnpc <N>")
    return "\n".join(lines)


def build_conditions(pid: str, campaign_name: str, state: dict, config: dict) -> str:
    """Build the active conditions list for /conditions command."""
    conds = state.get("conditions", {}).get(pid, [])
    if not conds:
        return f"No active conditions in {campaign_name}.\nGMs can add with /condition <target> — <effect>"

    lines = [f"⚡ Active Conditions — {campaign_name}:", ""]
    for i, c in enumerate(conds, 1):
        target = c.get("target", "Unknown")
        effect = c.get("effect", "")
        duration = c.get("duration", "")
        dur_str = f" ({duration})" if duration else ""
        lines.append(f"  {i}. {target}: {effect}{dur_str}")
    lines.append("")
    lines.append(f"{len(conds)} active. GMs: /condition, /endcondition <N>, /clearconditions")
    return "\n".join(lines)
