"""GM reply queue: track unreplied player messages."""

from datetime import datetime, timezone

import helpers
from commands.queue_scan import scan_transcripts
from commands.queue_format import (
    entry_age_icon, age_str, short_preview, NO_PRIORITY,
)


def build_queue(config: dict, state: dict) -> str:
    """Build /queue: unreplied messages, campaigns sorted by oldest."""
    now = datetime.now(timezone.utc)
    scanned = scan_transcripts(config, state)
    if not scanned:
        return "All caught up! No unreplied player messages."

    total = sum(len(d["entries"]) for d in scanned.values())

    # Build numeric priority map — lower = higher position in queue
    # queue_priority: True (legacy bool) → level 1; int used directly
    priority_map: dict[str, int] = {}
    for pair in config.get("topic_pairs", []):
        qp = pair.get("queue_priority")
        if qp is not None and qp is not False:
            pid_str = str(pair["pbp_topic_ids"][0])
            priority_map[pid_str] = int(qp) if isinstance(qp, int) else 1
    priority_pids = set(priority_map.keys())  # kept for pin-icon display

    def sort_key(pid):
        entries = scanned[pid]["entries"]
        oldest = min(e.get("time", "9999") for e in entries)
        # NO_PRIORITY sorts after every explicit rank. It was 2 until
        # 2026-07-30, which collided with real rank 2 and made a rank-2
        # campaign sort level with unprioritised ones.
        return (priority_map.get(pid, NO_PRIORITY), oldest)

    sorted_pids = sorted(scanned.keys(), key=sort_key)
    lines = [f"📋 GM Reply Queue: {total} unreplied"]

    for pid in sorted_pids:
        data = scanned[pid]
        entries = data["entries"]
        name = data["campaign"]
        code = data.get("code", "")
        label = f"{code}: {name}" if code else name
        scene = state.get("current_scenes", {}).get(pid, "")
        scene_str = f" 🎭 {scene}" if scene else ""
        pin = "📌 " if pid in priority_pids else ""
        lines.append(f"━━ {pin}{label} ({len(entries)}){scene_str} ━━")
        for entry in entries:
            hours = 0.0
            try:
                posted = datetime.strptime(entry["time"], "%Y-%m-%d %H:%M:%S")
                posted = posted.replace(tzinfo=timezone.utc)
                hours = helpers.hours_since(now, posted)
            except (ValueError, KeyError):
                pass
            icon = entry_age_icon(hours)
            user = entry.get("name", "?")
            preview = short_preview(entry.get("preview", ""))
            link = entry.get("link", "")
            line = f"{icon} {age_str(hours)}. {user}: {preview}"
            if link:
                line += f" 🔗 {link}"
            lines.append(line)

    return "\n".join(lines)
