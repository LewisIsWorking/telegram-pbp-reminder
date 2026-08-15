"""Session-poll roster and link helpers.

Extracted from ``scheduled/session_poll.py`` on 2026-08-15, which had
reached 205 lines. These three answer "who should be voting, and where
is the poll"; ``session_poll.py`` keeps the posting flow itself.
"""

import helpers
from helpers_pkg.groups import group_id_for_campaign  # noqa: F401
import telegram as tg  # noqa: F401


def _poll_roster(config: dict, state: dict, pid: str, pair: dict) -> dict:
    """Return {uid: {name, username}} for all players to be polled."""
    from commands.roster import active_poll_uids
    roster = {}
    # Optional {uid_str: username} map for players not in PBP registry
    name_map = {str(k): v for k, v in (pair.get("poll_user_names") or {}).items()}
    # Gate on whether poll_user_ids is *configured*; iterate the filtered set.
    # active_poll_uids honours the optional per-campaign poll_roster_filter:
    # when set, the list is trimmed to the campaign's active roster so players
    # who have left/gone inactive are no longer polled or pinged. (A filtered
    # result of [] yields an empty roster — it must NOT fall through to the
    # pbp-topic player scan, which would re-add the dropped players.)
    if pair.get("poll_user_ids"):
        for uid in active_poll_uids(pair, config, state):
            uid_str = str(uid)
            p = next((p for p in state.get("players", {}).values()
                      if p.get("user_id") == uid_str), None)
            fallback_username = name_map.get(uid_str, "")
            roster[uid_str] = {
                "name": p.get("first_name", fallback_username or uid_str) if p else (fallback_username or uid_str),
                "username": p.get("username", fallback_username) if p else fallback_username,
            }
    else:
        for key, p in state.get("players", {}).items():
            if p.get("pbp_topic_id") == pid:  # pragma: no cover
                uid = p.get("user_id", "")  # pragma: no cover
                roster[uid] = {"name": p.get("first_name", "?"),  # pragma: no cover
                               "username": p.get("username", "")}
    return roster


def _unvoted_mentions(roster: dict, voted_uids: list) -> list[str]:
    voted = set(str(u) for u in voted_uids)
    mentions = []
    for uid, info in roster.items():
        if uid not in voted:
            u = info.get("username", "")
            name = info["name"]
            # If name is just the raw UID (player not in registry), show friendly fallback
            if name == uid:
                name = f"Unknown ({uid})"  # pragma: no cover
            mentions.append(f"@{u}" if u else name)
    return mentions


def _poll_link(config: dict, pair: dict, msg_id: int | None) -> str:
    """Build a t.me link to the poll message."""
    if not msg_id:
        return ""
    pid = str(pair["pbp_topic_ids"][0])
    gid = group_id_for_campaign(config, pid)
    tid = pair.get("chat_topic_id")
    username = pair.get("group_username", config.get("group_username"))
    return tg.message_link(gid, tid, msg_id, username)
