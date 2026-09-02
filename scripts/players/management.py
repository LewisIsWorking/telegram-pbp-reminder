"""
Player management: kick and addplayer commands.
"""

import helpers
import telegram as tg
from players.retire import retire_seat


def handle_kick(pid: str, campaign_name: str, target: str,
                state: dict, group_id: int, thread_id: int,
                config: dict | None = None) -> None:
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

    # Remove player. Shares one path with the 4-week inactivity sweep
    # (extracted 2026-08-30): both must pop the record, write the leave
    # event and file removed_players, and a copy that forgets the third
    # makes the player's next message read as a first join.
    removed = retire_seat(match_key, state, config,
                          kicked=True, campaign_name=campaign_name)

    name = helpers.player_full_name(removed)
    tg.send_message(group_id, thread_id,
                    f"\U0001f6aa {name} has been removed from {campaign_name} tracking.\n"
                    f"They can rejoin by posting in PBP again.")
    print(f"Kicked {name} from {campaign_name}")


def handle_addplayer(pid: str, campaign_name: str, raw_args: str,
                     now_iso: str, state: dict, group_id: int, thread_id: int,
                     config: dict | None = None) -> None:
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

    # Merge, for the same reason dispatch/track_player does: a record
    # holds the bot's observations AND a GM's decisions, and only the
    # first set belongs to the writer. Re-running /addplayer over an
    # existing seat must not silently drop its `permanent` or
    # `played_by`. See the 2026-09-02 note in track_player.py.
    record = dict(state["players"].get(player_key, {}))
    record.update({
        "user_id": placeholder_id,
        "first_name": first_name,
        "last_name": last_name,
        "username": username,
        "campaign_name": campaign_name,
        "pbp_topic_id": pid,
        "last_post_time": now_iso,
        "last_warned_week": 0,
    })
    state["players"][player_key] = record

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
    on_join(pid, placeholder_id, first_name, username, state, config)
    print(f"Added {display_name} (@{username}) to {campaign_name}")
