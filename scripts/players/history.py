"""Player join/leave history logging.

Appends to state["player_history"] on join, leave, and rejoin events.
Each event: {event, pid, user_id, name, username, at}
"""

from datetime import datetime, timezone


def _log(event: str, pid: str, user_id: str,
         name: str, username: str, state: dict) -> None:
    """Append one history event."""
    state.setdefault("player_history", []).append({
        "event":    event,
        "pid":      pid,
        "user_id":  user_id,
        "name":     name,
        "username": username,
        "at":       datetime.now(timezone.utc).isoformat(),
    })
    print(f"Player history: {event} — {name} in pid {pid}")


def on_rejoin(pid: str, user_id: str, name: str,
              username: str, state: dict) -> None:
    """Called when a previously removed player posts again."""
    print(f"Player {name} rejoined pid {pid}")
    _log("join", pid, user_id, name, username, state)


def on_join(pid: str, user_id: str, name: str,
            username: str, state: dict) -> None:
    """Called when a new player is added via /addplayer."""
    _log("join", pid, user_id, name, username, state)


def on_leave(pid: str, user_id: str, name: str,
             username: str, state: dict) -> None:
    """Called when a player is kicked or auto-removed."""
    _log("leave", pid, user_id, name, username, state)
