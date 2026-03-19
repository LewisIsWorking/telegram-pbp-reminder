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

    maps = helpers.build_topic_maps(config)
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
            age = ""
            try:
                posted = datetime.fromisoformat(entry["time"])
                hours = helpers.hours_since(now, posted)
                if hours >= 24:
                    age = f" ({int(hours // 24)}d ago)"
                elif hours >= 1:
                    age = f" ({int(hours)}h ago)"
            except (ValueError, KeyError):
                pass

            icon = "🔴" if hours >= 48 else "🟡" if hours >= 24 else "⚪"
            user = entry.get("user_name", "?")
            preview = entry.get("preview", "")
            if len(preview) > 60:
                preview = preview[:57] + "..."
            lines.append(f"{icon} {user}{age}: {preview}")

    lines.insert(1, f"Total: {total} unreplied\n")
    return "\n".join(lines)
