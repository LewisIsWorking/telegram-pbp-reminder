"""Daily GM queue reminder posted to bot topic."""

from datetime import datetime, timezone

import helpers
import telegram as tg


def post_queue_reminder(config: dict, state: dict, *, now: datetime | None = None, **_kw) -> None:
    """Post unreplied player messages to the bot topic once per day."""
    bot_topic = config.get("bot_topic_id")
    if not bot_topic:
        return

    now = now or datetime.now(timezone.utc)

    # Once per day
    last = state.get("last_queue_reminder")
    if last:
        elapsed = helpers.hours_since(now, datetime.fromisoformat(last))
        if elapsed < 22:
            return

    gm_queue = state.get("gm_queue", {})
    if not any(gm_queue.values()):
        state["last_queue_reminder"] = now.isoformat()
        return

    group_id = config["group_id"]
    maps = helpers.build_topic_maps(config)
    # Group username for building links
    group_user = "Path_Wars"

    lines = ["📋 Unreplied messages:\n"]
    total = 0

    for pair in config.get("topic_pairs", []):
        pid = str(pair["pbp_topic_ids"][0])
        name = pair["name"]
        queue = gm_queue.get(pid, [])
        if not queue:
            continue

        total += len(queue)
        lines.append(f"━━ {name} ({len(queue)}) ━━")

        for entry in queue:
            age = ""
            try:
                posted = datetime.fromisoformat(entry["time"])
                hours = helpers.hours_since(now, posted)
                if hours >= 24:
                    age = f"{int(hours // 24)}d"
                else:
                    age = f"{int(hours)}h"
            except (ValueError, KeyError):
                hours = 0

            icon = "🔴" if hours >= 48 else "🟡" if hours >= 24 else "⚪"
            user = entry.get("user_name", "?")
            msg_id = entry.get("message_id", "")
            tid = entry.get("thread_id", "")

            link = ""
            if tid and msg_id:
                link = f" https://t.me/{group_user}/{tid}/{msg_id}"

            preview = entry.get("preview", "")
            if len(preview) > 50:
                preview = preview[:47] + "..."

            lines.append(f"{icon} {user} ({age}): {preview}{link}")

        lines.append("")

    if total == 0:
        state["last_queue_reminder"] = now.isoformat()
        return

    lines.insert(1, f"Total: {total}\n")
    message = "\n".join(lines).rstrip()

    if tg.send_message(group_id, bot_topic, message):
        state["last_queue_reminder"] = now.isoformat()
        print(f"Queue reminder: {total} unreplied messages")
