"""
Combat display builders.

Read-only commands that display combat state: /whosturn, /combatlog.
"""

from datetime import datetime, timezone

import helpers


def format_elapsed(hours: float) -> str:
    """Format elapsed hours as a readable string."""
    if hours < 1:
        return f"{int(hours * 60)}m"
    elif hours < 24:
        return f"{int(hours)}h"
    else:
        days = int(hours / 24)
        remaining = int(hours % 24)
        return f"{days}d {remaining}h"


def build_whosturn(pid: str, campaign_name: str, state: dict) -> str:
    """Build combat status for /whosturn command."""
    combat = state.get("combat", {}).get(pid)

    if not combat or not combat.get("active"):
        return f"No active combat in {campaign_name}."

    round_num = combat.get("round", 1)
    phase = combat.get("current_phase", "unknown")
    phase_label = "Players" if phase == "players" else "Enemies"

    phase_start = datetime.fromisoformat(combat["phase_started_at"])
    now = datetime.now(timezone.utc)
    elapsed = helpers.hours_since(now, phase_start)

    lines = [
        f"⚔️ {campaign_name} — Round {round_num}, {phase_label}' turn",
        f"Phase started: {format_elapsed(elapsed)} ago",
    ]

    # Enemy roster
    enemies = combat.get("enemies", [])
    if enemies:
        lines.append(f"Enemies: {', '.join(enemies)}")

    lines.append("")

    if phase == "players":
        acted_dict = combat.get("players_acted", {})
        # Migrate old list format
        if isinstance(acted_dict, list):
            acted_dict = {uid: combat.get("phase_started_at", "") for uid in acted_dict}

        acted_ids = set(acted_dict.keys())
        players = [
            p for p in state.get("players", {}).values()
            if p.get("pbp_topic_id") == pid
        ]

        acted_list = []
        waiting_list = []
        for p in sorted(players, key=lambda x: x["first_name"]):
            uid = p["user_id"]
            if helpers.is_away(state, pid, uid, now):
                continue  # Skip away players entirely
            if uid in acted_ids:
                ts = acted_dict[uid]
                if ts:
                    acted_time = datetime.fromisoformat(ts)
                    ago = helpers.hours_since(now, acted_time)
                    acted_list.append(f"  ✅ {p['first_name']} ({format_elapsed(ago)} ago)")
                else:
                    acted_list.append(f"  ✅ {p['first_name']}")
            else:
                # How long have they been holding things up?
                wait_h = helpers.hours_since(now, phase_start)
                wait_str = f" — waiting {format_elapsed(wait_h)}" if wait_h >= 1 else ""
                waiting_list.append(f"  ⏳ {p['first_name']}{wait_str}")

        if waiting_list:
            lines.append("Waiting on:")
            lines.extend(waiting_list)
        if acted_list:
            lines.append("Acted:")
            lines.extend(acted_list)
        if not waiting_list and acted_list:
            lines.append("✅ Everyone has acted! GM can use /next")
    else:
        lines.append("Waiting for GM to resolve enemy turns.")
        lines.append("Use /next when done.")

    return "\n".join(lines)


def build_combatlog(pid: str, campaign_name: str, state: dict) -> str:
    """Build the combat log for /combatlog command."""
    combat = state.get("combat", {}).get(pid)
    if not combat or not combat.get("active"):
        return f"No active combat in {campaign_name}."

    log = combat.get("combat_log", [])
    if not log:
        return f"No combat log entries yet.\nGMs: /clog <event> to add entries."

    lines = [f"📝 Combat Log — {campaign_name} (Round {combat['round']}):", ""]
    for entry in log:
        lines.append(f"  R{entry['round']}: {entry['text']}")
    return "\n".join(lines)
