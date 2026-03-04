"""
Campaign summary and party builders.

Commands: /summary, /party.
"""

from datetime import datetime, timezone

import helpers


def build_party(pid: str, campaign_name: str, config: dict, state: dict) -> str:
    """Build the in-fiction party composition for /party command."""
    characters = helpers.get_characters(config, pid)

    if not characters:
        return (f"No characters configured for {campaign_name}.\n"
                f"Ask your GM to add a 'characters' mapping in the bot config.")

    now = datetime.now(timezone.utc)
    players = [
        p for p in state.get("players", {}).values()
        if p.get("pbp_topic_id") == pid
    ]

    lines = [f"The party of {campaign_name}:", ""]

    # Map active players to their characters
    active_chars = []
    orphan_chars = []

    for uid, char_name in sorted(characters.items(), key=lambda x: x[1]):
        player = None
        for p in players:
            if p.get("user_id") == uid:
                player = p
                break

        if player:
            player_name = helpers.player_full_name(player)
            last_post = datetime.fromisoformat(player["last_post_time"])
            days_ago = helpers.days_since(now, last_post)
            away_record = helpers.is_away(state, pid, uid, now)
            if away_record:
                reason = away_record.get("reason", "Away")
                active_str = f"✈️ away ({reason})"
            elif days_ago < 1:
                active_str = "active today"
            elif days_ago < 7:
                active_str = f"active {int(days_ago)}d ago"
            else:
                active_str = f"last seen {int(days_ago)}d ago"
            active_chars.append(f"  ⚔️ {char_name} ({player_name}) — {active_str}")
        else:
            orphan_chars.append(f"  🔇 {char_name} — no recent posts")

    for line in active_chars:
        lines.append(line)
    for line in orphan_chars:
        lines.append(line)

    lines.append("")
    lines.append(f"{len(active_chars)} active, {len(orphan_chars)} inactive")

    return "\n".join(lines)


def build_summary(pid: str, campaign_name: str, state: dict, config: dict) -> str:
    """Build a one-stop campaign state summary."""
    lines = [f"📖 Summary — {campaign_name}", ""]

    # Current scene
    scene = state.get("current_scene", {}).get(pid)
    if scene:
        lines.append(f"🎬 Scene: {scene}")

    # Combat state
    combat = state.get("combat", {}).get(pid, {})
    if combat.get("active"):
        phase = combat.get("phase", "?")
        round_num = combat.get("round", "?")
        lines.append(f"⚔️ Combat: Round {round_num} — {phase}")

    # Timer
    timer = state.get("timers", {}).get(pid)
    if timer:
        now = datetime.now(timezone.utc)
        deadline = datetime.fromisoformat(timer["deadline"])
        remaining = deadline - now
        if remaining.total_seconds() > 0:
            hours = int(remaining.total_seconds() // 3600)
            mins = int((remaining.total_seconds() % 3600) // 60)
            time_str = f"{hours}h {mins}m" if hours > 0 else f"{mins}m"
            reason = timer.get("reason", "")
            lines.append(f"⏳ Timer: {time_str} left" + (f" — {reason}" if reason else ""))
        else:
            lines.append("⏰ Timer EXPIRED!")

    # Active vote
    vote = state.get("votes", {}).get(pid)
    if vote and not vote.get("closed"):
        total = sum(len(v) for v in vote.get("results", {}).values())
        lines.append(f"🗳️ Vote: {vote['question']} ({total} votes)")

    # Away players
    away_count = 0
    for key in state.get("away", {}):
        if key.startswith(f"{pid}:"):
            uid = key.split(":")[1]
            if helpers.is_away(state, pid, uid):
                away_count += 1
    if away_count:
        lines.append(f"✈️ {away_count} player{'s' if away_count != 1 else ''} away")

    if len(lines) == 2:
        lines.append("Nothing special happening right now.")

    lines.append("")

    # Active quests
    quests = [q for q in state.get("quests", {}).get(pid, []) if q.get("status") == "active"]
    if quests:
        lines.append(f"📋 Quests ({len(quests)} active):")
        for i, q in enumerate(quests[:5], 1):
            lines.append(f"  {i}. {q['text']}")
        if len(quests) > 5:
            lines.append(f"  ... and {len(quests) - 5} more (/quests)")
        lines.append("")

    # Active conditions
    conds = state.get("conditions", {}).get(pid, [])
    if conds:
        lines.append(f"⚡ Conditions ({len(conds)}):")
        for c in conds[:5]:
            dur = f" ({c['duration']})" if c.get("duration") else ""
            lines.append(f"  • {c['target']}: {c['effect']}{dur}")
        if len(conds) > 5:
            lines.append(f"  ... and {len(conds) - 5} more (/conditions)")
        lines.append("")

    # NPC count
    npcs = state.get("npcs", {}).get(pid, [])
    if npcs:
        lines.append(f"🎭 {len(npcs)} NPC{'s' if len(npcs) != 1 else ''} tracked (/npcs)")

    # Loot count
    loot = state.get("loot", {}).get(pid, [])
    if loot:
        lines.append(f"💰 {len(loot)} loot item{'s' if len(loot) != 1 else ''} (/lootlist)")

    # Pins count
    pins = state.get("pins", {}).get(pid, [])
    if pins:
        lines.append(f"📌 {len(pins)} pin{'s' if len(pins) != 1 else ''} (/pins)")

    # HP tracker
    hp_entries = state.get("hp_tracker", {}).get(pid, {})
    if hp_entries:
        lines.append("")
        lines.append(f"❤️ HP Tracker ({len(hp_entries)}):")
        for name, hp in sorted(hp_entries.items()):
            icon = helpers.hp_status_icon(hp["current"], hp["max"])
            bar = helpers.hp_bar(hp["current"], hp["max"], 8)
            lines.append(f"  {icon} {name}: {bar}")

    # Progress clocks
    clocks = state.get("clocks", {}).get(pid, {})
    if clocks:
        lines.append("")
        lines.append(f"⏱️ Clocks ({len(clocks)}):")
        for name, clock in sorted(clocks.items()):
            display = helpers.clock_display(clock["filled"], clock["segments"])
            lines.append(f"  {name}: {display}")

    return "\n".join(lines)
