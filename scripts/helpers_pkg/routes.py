"""Where each family of GM-facing bot messages is posted.

Added 2026-09-22 at Lewis's request. The Path Wars bot topic (137393) had
become a dumping ground: player-facing replies (/roll, /mystats, boons,
POTW) were buried under health alerts, inactivity reports, pin digests
and poll admin. Those four families now each get their own topic in the
Nudge Bot Notifications group, configured under ``notification_routes``:

    "notification_routes": {
      "bot_health": {"chat_id": -1004303231713, "thread_id": 767},
      ...
    }

⭐ A route that is not configured falls back to the bot topic, exactly
where these messages went before. So a missing or half-filled config
moves nothing rather than silencing anything.

⭐ Returns a CHAT and a thread, never just a thread, for the reason
``schedule_post.schedule_destination`` gives: a caller handed only a
topic id has to invent the chat, and invents the main group, which is
wrong the moment the destination is elsewhere.
"""

# The families that can be routed. A config entry naming anything else is
# a typo that would otherwise silently fall back to the bot topic.
ROUTES = {
    "bot_health": "CI failures, posting paused, delete refusals, daily diagnostic",
    "activity": "Campaign silence, party roster, recruitment, pace-drop and campaign-table reports",
    "pace_report": "The weekly pace report, one per campaign (Lewis, 2026-09-23)",
    "roster_overview": "The Campaign Roster post, target vs active players (Lewis, 2026-09-23)",
    "pins": "The daily pin digest and the non-bot pin alert",
    "poll_admin": "Unknown voters, identified voters, polls closed",
}


def route(config: dict, name: str) -> tuple[int | None, int | None]:
    """``(chat_id, thread_id)`` for the ``name`` family of messages.

    Configured -> that chat and topic. Otherwise the main group's bot
    topic, and either half may be None when the config lacks it, which
    callers already test for before sending.
    """
    if name not in ROUTES:
        raise KeyError(f"unknown notification route {name!r}")
    entry = (config.get("notification_routes") or {}).get(name) or {}
    if entry.get("chat_id"):
        return int(entry["chat_id"]), entry.get("thread_id")
    return config.get("group_id"), config.get("bot_topic_id")
