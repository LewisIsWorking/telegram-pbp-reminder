"""GM queue: track unreplied player messages."""

from datetime import datetime, timezone

import helpers


def build_queue(config: dict, state: dict) -> str:
    """Build /queue output: all player messages awaiting GM reply, across campaigns."""
    now = datetime.now(timezone.utc)
    gm_queue = state.get("gm_queue", {})

    if not gm_queue:
        return "All caught up! No unreplied player messages."

    maps = helpers.build_topic_maps(config)
    entries = []

    for pid, players in sorted(gm_queue.items()):
        name = maps.to_name.get(pid, pid)
        if not players:
            continue
        for uid, info in sorted(players.items(), key=lambda x: x[1]["time"]):
            posted = datetime.fromisoformat(info["time"])
            elapsed = helpers.hours_since(now, posted)
            days = int(elapsed) // 24
            hours = int(elapsed) % 24
            time_str = f"{days}d {hours}h" if days > 0 else f"{hours}h"
            preview = info.get("preview", "")
            if len(preview) > 60:
                preview = preview[:57] + "..."
            entries.append({
                "campaign": name,
                "player": info["name"],
                "elapsed": elapsed,
                "time_str": time_str,
                "preview": preview,
            })

    if not entries:
        return "All caught up! No unreplied player messages."

    # Sort by oldest first
    entries.sort(key=lambda e: -e["elapsed"])

    lines = [f"📋 GM Queue: {len(entries)} unreplied\n"]

    current_campaign = None
    for e in entries:
        if e["campaign"] != current_campaign:
            current_campaign = e["campaign"]
            lines.append(f"\n━━ {current_campaign} ━━")
        icon = "🔴" if e["elapsed"] >= 48 else "🟡" if e["elapsed"] >= 24 else "⚪"
        lines.append(f"{icon} {e['player']} ({e['time_str']} ago)")
        if e["preview"]:
            lines.append(f"   {e['preview']}")

    return "\n".join(lines)
