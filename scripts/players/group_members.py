"""People who post in the Path Wars group outside every campaign topic.

Added 2026-10-08. KP asked for a C00 sheet in the group, but not in an RP
or combat topic, so the bot dropped every one of his posts: he was never
told to link COO, and COO could not have let him link anyway, because its
list of people who may claim a Telegram identity came only from campaign
topics (``player_registry``).

So a post anywhere else in the group now:
  1. records the poster in ``group_members`` (players.json), which COO
     reads as well, so they can link before joining a campaign;
  2. gets the same link nudge as a campaign post (players/coo_link.py).
"""

from datetime import datetime, timezone

from players import coo_link

STATE_KEY = "group_members"


def on_group_post(msg: dict, config: dict, state: dict, maps,
                  linked=coo_link.linked_ids) -> bool:
    """Record and maybe nudge a human posting in the group. True when nudged."""
    sender = msg.get("from") or {}
    if msg.get("chat", {}).get("id") != config.get("group_id"):
        return False
    if not sender.get("id") or sender.get("is_bot", False):
        return False
    user_id = str(sender["id"])
    if user_id in {str(g) for g in config.get("gm_user_ids", [])}:
        return False
    date = msg.get("date")
    when = (datetime.fromtimestamp(date, tz=timezone.utc) if date
            else datetime.now(timezone.utc)).isoformat()
    name = sender.get("first_name", "") or sender.get("username", "") or user_id
    state.setdefault(STATE_KEY, {})[user_id] = {
        "name": name, "username": sender.get("username", ""), "last": when}
    text = msg.get("text") or msg.get("caption") or ""
    parsed = {"pid": None, "thread_id": msg.get("message_thread_id"),
              "user_id": user_id, "user_name": name,
              "username": sender.get("username", ""),
              "text": text, "raw_text": text, "msg_time_iso": when}
    return coo_link.nudge_if_unlinked(parsed, state, config, maps, linked=linked)
