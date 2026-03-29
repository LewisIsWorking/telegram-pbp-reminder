"""GM reply queue: track unreplied player messages."""

from datetime import datetime, timezone

import helpers
from commands.queue_scan import scan_transcripts
from commands.queue_format import entry_age_icon, age_str, short_preview


def build_queue(config: dict, state: dict) -> str:
    """Build /queue: unreplied messages, campaigns sorted by oldest."""
    now = datetime.now(timezone.utc)
    scanned = scan_transcripts(config, state)
    if not scanned:
        return "All caught up! No unreplied player messages."

    total = sum(len(d["entries"]) for d in scanned.values())

    # Priority campaigns always sort first
    priority_pids = set()
    for pair in config.get("topic_pairs", []):
        if pair.get("queue_priority"):
            priority_pids.add(str(pair["pbp_topic_ids"][0]))

    def sort_key(pid):
        entries = scanned[pid]["entries"]
        oldest = min(e.get("time", "9999") for e in entries)
        return (0 if pid in priority_pids else 1, oldest)

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
