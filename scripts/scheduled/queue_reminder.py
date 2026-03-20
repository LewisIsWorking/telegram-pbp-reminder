"""Daily GM queue reminder posted to bot topic."""

from datetime import datetime, timezone

import helpers
import telegram as tg


def _gm_mention(config: dict, pid: str) -> str:
    """Build HTML mention tags for campaign GMs."""
    gm_ids = helpers.gm_ids_for_campaign(config, pid)
    mentions = []
    for uid in gm_ids:
        mentions.append(f'<a href="tg://user?id={uid}">GM</a>')
    return ", ".join(mentions) if mentions else "GM"


def _html_escape(text: str) -> str:
    """Escape HTML special characters."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


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
    group_user = "Path_Wars"

    lines = ["📋 <b>Unreplied messages</b>\n"]
    total = 0

    for pair in config.get("topic_pairs", []):
        pid = str(pair["pbp_topic_ids"][0])
        name = pair["name"]
        queue = gm_queue.get(pid, [])
        if not queue:
            continue

        total += len(queue)
        gm = _gm_mention(config, pid)
        lines.append(f"\n━━ {_html_escape(name)} ({len(queue)}) — {gm} ━━")

        for entry in queue:
            hours = 0
            age = ""
            try:
                posted = datetime.fromisoformat(entry["time"])
                hours = helpers.hours_since(now, posted)
                if hours >= 24:
                    age = f"{int(hours // 24)}d"
                else:
                    age = f"{int(hours)}h"
            except (ValueError, KeyError):
                pass

            icon = "🔴" if hours >= 48 else "🟡" if hours >= 24 else "⚪"
            user = _html_escape(entry.get("user_name", "?"))
            msg_id = entry.get("message_id", "")

            # Build link using pid as thread_id (they're the same)
            link = ""
            if msg_id:
                link = f"https://t.me/{group_user}/{pid}/{msg_id}"

            preview = _html_escape(entry.get("preview", ""))

            if link:
                lines.append(f'{icon} <a href="{link}">{user}</a> ({age})')
            else:
                lines.append(f"{icon} {user} ({age})")
            if preview:
                lines.append(f"   {preview}")

        lines.append("")

    if total == 0:
        state["last_queue_reminder"] = now.isoformat()
        return

    lines.insert(1, f"Total: {total}\n")
    message = "\n".join(lines).rstrip()

    if tg.send_message(group_id, bot_topic, message, parse_mode="HTML"):
        state["last_queue_reminder"] = now.isoformat()
        print(f"Queue reminder: {total} unreplied messages")
