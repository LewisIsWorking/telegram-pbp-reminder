"""GM reply queue: track unreplied player messages."""

from datetime import datetime, timezone

import helpers


def build_queue(config: dict, state: dict) -> str:
    """Build /queue output: unreplied player messages across all campaigns.

    Each entry is a specific message a player sent that the GM has not
    replied to (using Telegram's reply feature). Sorted oldest first.
    """
    now = datetime.now(timezone.utc)
    gm_queue = state.get("gm_queue", {})

    if not any(gm_queue.values()):
        return "All caught up! No unreplied player messages."

    group_user = "Path_Wars"
    lines = ["📋 GM Reply Queue:\n"]
    total = 0

    for pair in config.get("topic_pairs", []):
        pid = str(pair["pbp_topic_ids"][0])
        name = pair["name"]
        queue = gm_queue.get(pid, [])
        if not queue:
            continue

        total += len(queue)
        lines.append(f"\n━━ {name} ({len(queue)}) ━━")

        for entry in queue:
            hours = 0
            age = ""
            try:
                posted = datetime.fromisoformat(entry["time"])
                hours = helpers.hours_since(now, posted)
                if hours >= 24:
                    age = f"{int(hours // 24)}d ago"
                elif hours >= 1:
                    age = f"{int(hours)}h ago"
                else:
                    age = "just now"
            except (ValueError, KeyError):
                pass

            icon = "🔴" if hours >= 48 else "🟡" if hours >= 24 else "⚪"
            user = entry.get("user_name", "?")
            msg_id = entry.get("message_id", "")
            preview = entry.get("preview", "")

            link = ""
            if msg_id:
                link = f" https://t.me/{group_user}/{pid}/{msg_id}"

            lines.append(f"{icon} {user} ({age}): {preview}{link}")

    lines.insert(1, f"Total: {total} unreplied\n")
    return "\n".join(lines)
