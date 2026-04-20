"""
Player management: kick and addplayer commands.
"""

from datetime import datetime, timezone

import helpers
import telegram as tg


def handle_kick(pid: str, campaign_name: str, target: str,
                state: dict, group_id: int, thread_id: int) -> None:
    """Remove a player from the campaign roster by username or name."""
    target_lower = target.lower()

    # Search for matching player in this campaign
    match_key = None
    match_player = None
    for key, player in state["players"].items():
        if not key.startswith(f"{pid}:"):
            continue  # pragma: no cover
        username = player.get("username", "").lower()
        first = player.get("first_name", "").lower()
        full = f"{first} {player.get('last_name', '')}".strip().lower()

        if username == target_lower or first == target_lower or full == target_lower:
            match_key = key
            match_player = player
            break

    if not match_player:
        tg.send_message(group_id, thread_id,
                        f"No player matching '{target}' found in {campaign_name}.")
        return

    # Remove player
    removed = state["players"].pop(match_key)
    from players.history import on_leave
    on_leave(pid, str(removed.get("user_id", "")),
             removed["first_name"], removed.get("username", ""), state)
    state["removed_players"][match_key] = {
        "removed_at": datetime.now(timezone.utc).isoformat(),
        "first_name": removed["first_name"],
        "username": removed.get("username", ""),
        "campaign_name": campaign_name,
        "kicked": True,
    }

    name = helpers.player_full_name(removed)
    tg.send_message(group_id, thread_id,
                    f"\U0001f6aa {name} has been removed from {campaign_name} tracking.\n"
                    f"They can rejoin by posting in PBP again.")
    print(f"Kicked {name} from {campaign_name}")


def handle_addplayer(pid: str, campaign_name: str, raw_args: str,
                     now_iso: str, state: dict, group_id: int, thread_id: int) -> None:
    """Manually register a player who hasn't posted yet.

    Format: /addplayer @username FirstName [LastName]
    Creates a placeholder player entry. The username is stored as-is and
    updated with their real user_id when they first post.
    """
    parts = raw_args.split(None, 1)
    username = parts[0].lstrip("@") if parts else ""
    display_name = parts[1] if len(parts) > 1 else username

    if not username:
        tg.send_message(group_id, thread_id,
                        "Usage: /addplayer @username PlayerName")
        return

    # Check if player already exists in this campaign
    for key, player in state["players"].items():
        if not key.startswith(f"{pid}:"):
            continue  # pragma: no cover
        if player.get("username", "").lower() == username.lower():
            tg.send_message(group_id, thread_id,
                            f"{display_name} (@{username}) is already tracked in {campaign_name}.")
            return

    # Use username as placeholder ID (will be replaced when they post)
    placeholder_id = f"pending_{username}"
    player_key = f"{pid}:{placeholder_id}"

    name_parts = display_name.split(None, 1)
    first_name = name_parts[0]
    last_name = name_parts[1] if len(name_parts) > 1 else ""

    state["players"][player_key] = {
        "user_id": placeholder_id,
        "first_name": first_name,
        "last_name": last_name,
        "username": username,
        "campaign_name": campaign_name,
        "pbp_topic_id": pid,
        "last_post_time": now_iso,
        "last_warned_week": 0,
    }

    # Also clear from removed_players if they were previously removed
    for rkey in list(state["removed_players"].keys()):
        if rkey.startswith(f"{pid}:"):
            removed = state["removed_players"][rkey]
            if removed.get("username", "").lower() == username.lower():
                del state["removed_players"][rkey]
                break

    tg.send_message(group_id, thread_id,
                    f"\u2705 {display_name} (@{username}) added to {campaign_name} roster.\n"
                    f"Their tracking will update with full stats when they first post.")
    from players.history import on_join
    on_join(pid, placeholder_id, first_name, username, state)
    print(f"Added {display_name} (@{username}) to {campaign_name}")
