"""
Campaign player registry.

Assigns permanent per-campaign IDs to every player who joins.
GM is always #00. Players get sequential IDs (#01, #02, etc.)
in the order they first post. IDs persist even if a player leaves.

State key: "player_registry" → {pid: {uid: {"id": int, "name": str, "joined": str}}}
"""

from datetime import datetime, timezone

import helpers


def get_or_assign_id(pid: str, user_id: str, user_name: str,
                     is_gm: bool, state: dict) -> int:
    """Get existing player ID or assign the next available one."""
    registry = state.setdefault("player_registry", {})
    campaign = registry.setdefault(pid, {})

    if user_id in campaign:
        # Update name if changed
        campaign[user_id]["name"] = user_name
        return campaign[user_id]["id"]

    # Assign new ID
    if is_gm:
        player_id = 0
    else:
        existing_ids = [entry["id"] for entry in campaign.values()]
        # Next available non-zero ID
        player_id = 1
        while player_id in existing_ids:
            player_id += 1

    campaign[user_id] = {
        "id": player_id,
        "name": user_name,
        "joined": datetime.now(timezone.utc).isoformat(),
    }

    return player_id


def get_player_id(pid: str, user_id: str, state: dict) -> int | None:
    """Look up a player's campaign ID, or None if not registered."""
    return state.get("player_registry", {}).get(pid, {}).get(
        user_id, {}).get("id")


def format_id(player_id: int) -> str:
    """Format a player ID as #00, #01, etc."""
    return f"#{player_id:02d}"


def build_registry(pid: str, campaign_name: str, config: dict,
                   state: dict) -> str:
    """Build /registry output showing all players ever in a campaign."""
    registry = state.get("player_registry", {}).get(pid, {})
    if not registry:
        return f"No players registered yet for {campaign_name}."

    label = helpers.get_label(config, pid)
    lines = [f"📋 {label} — Player Registry\n"]

    # Sort by ID
    sorted_players = sorted(registry.items(),
                            key=lambda x: x[1]["id"])

    for uid, entry in sorted_players:
        pid_str = format_id(entry["id"])
        name = entry["name"]
        # Check if still active
        player_key = f"{pid}:{uid}"
        is_active = player_key in state.get("players", {})
        is_removed = player_key in state.get("removed_players", {})
        status = ""
        if is_removed:
            status = " [removed]"
        elif not is_active:
            status = " [inactive]"
        lines.append(f"{pid_str}: {name}{status}")

    lines.append(f"\n{len(sorted_players)} players registered.")
    return "\n".join(lines)
