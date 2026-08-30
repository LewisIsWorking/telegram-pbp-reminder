"""Player join/leave history logging.

Appends to state["player_history"] on join, leave, and rejoin events.
Each event: {event, pid, user_id, name, username, at}

Also posts an updated roster to the campaign's chat topic on each event.
"""

from datetime import datetime, timezone

import telegram as tg


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


def post_roster(pid: str, config: dict, state: dict) -> None:
    """Post updated campaign roster to its chat topic.

    ⚠️ Public since 2026-08-30 so a caller removing SEVERAL seats in one
    run can announce once at the end instead of once per person. Five
    removals used to mean five roster posts into the campaign's chat,
    four of them showing intermediate states nobody needs. That never
    bit while removals arrived one at a time; the C08 Theria backlog of
    five made it bite immediately.
    """
    if not config:
        return
    pair = next((p for p in config.get("topic_pairs", [])
                 if str(p["pbp_topic_ids"][0]) == pid), None)
    if not pair:
        return
    chat_tid = pair.get("chat_topic_id")
    if not chat_tid:
        return
    from commands.roster import build_roster_campaign
    gid = pair.get("group_id", config.get("group_id"))
    msg = build_roster_campaign(pair, config, state)
    tg.send_message(gid, chat_tid, msg)


def on_rejoin(pid: str, user_id: str, name: str,
              username: str, state: dict,
              config: dict | None = None) -> None:
    """Called when a previously removed player posts again."""
    print(f"Player {name} rejoined pid {pid}")
    _log("join", pid, user_id, name, username, state)
    if config:
        post_roster(pid, config, state)


def on_join(pid: str, user_id: str, name: str,
            username: str, state: dict,
            config: dict | None = None) -> None:
    """Called when a new player is added via /addplayer."""
    _log("join", pid, user_id, name, username, state)
    if config:
        post_roster(pid, config, state)


def on_leave(pid: str, user_id: str, name: str,
             username: str, state: dict,
             config: dict | None = None) -> None:
    """Called when a player is kicked or auto-removed."""
    _log("leave", pid, user_id, name, username, state)
    if config:
        post_roster(pid, config, state)
