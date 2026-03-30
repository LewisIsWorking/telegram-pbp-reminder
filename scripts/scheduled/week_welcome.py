"""
Weekly welcome post — fires Sunday morning at poll_post_hour UTC.

Posts a "Welcome to Week X" message to the bot topic, giving a quick
orientation at the start of each new week.
"""

from datetime import datetime, timezone

import telegram as tg
from scheduled.session_poll_build import sunday_week_key


def post_week_welcome(config: dict, state: dict, *,
                      now: datetime | None = None, **_kw) -> None:
    """Post 'Welcome to Week X' to bot topic on Sunday at poll_post_hour."""
    now = now or datetime.now(timezone.utc)

    # Only fires on Sunday
    if now.weekday() != 6:
        return

    post_hour = config.get("poll_post_hour", 7)
    if now.hour < post_hour:
        return

    week_key = sunday_week_key(now)
    if state.get("last_week_welcome") == week_key:
        return

    bot_topic = config.get("bot_topic_id")
    group_id  = config["group_id"]
    if not bot_topic:
        return

    week_num  = now.isocalendar()[1]
    year      = now.year
    legend = (
        "🟢 < 6h  ⚪ same day  🟡 1–2d  🟠 2–3d\n"
        "🔴 3–5d  🟣 5–7d  🔵 7–14d  🟤 14–30d  ⚫ 30d+"
    )
    msg = (
        f"━━━━━━━━━━━━━━━━\n"
        f"🗓️ Welcome to Week {week_num}/{year}!\n\n"
        f"Session polls are up — check your campaign chats.\n"
        f"New week, new stories. Let's go! 🎲\n\n"
        f"📋 Queue age icons:\n{legend}"
    )

    if tg.send_message(group_id, bot_topic, msg):
        state["last_week_welcome"] = week_key
        print(f"Week welcome posted (W{week_num})")
