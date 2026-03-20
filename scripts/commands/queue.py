"""GM reply queue: track unreplied player messages."""

from datetime import datetime, timezone

import helpers
from commands.queue_scan import scan_transcripts


def _age_str(hours: float) -> str:
    days = int(hours // 24)
    remaining_h = int(hours % 24)
    if days > 0:
        return f"{days}d {remaining_h}h ago"
    elif hours >= 1:
        return f"{int(hours)}h ago"
    return "just now"


def build_queue(config: dict, state: dict) -> str:
    """Build /queue output: unreplied messages grouped by campaign.

    Campaigns sorted by their oldest unreplied message (most overdue first).
    """
    now = datetime.now(timezone.utc)
    scanned = scan_transcripts(config)

    if not scanned:
        return "All caught up! No unreplied player messages."

    total = sum(len(d["entries"]) for d in scanned.values())

    # Sort campaigns by oldest unreplied message
    def oldest_time(pid):
        entries = scanned[pid]["entries"]
        return min(e.get("time", "9999") for e in entries) if entries else "9999"

    sorted_pids = sorted(scanned.keys(), key=oldest_time)

    lines = [f"📋 GM Reply Queue: {total} unreplied\n"]

    for pid in sorted_pids:
        data = scanned[pid]
        entries = data["entries"]
        name = data["campaign"]
        code = data.get("code", "")
        label = f"{code}: {name}" if code else name
        lines.append(f"\n━━ {label} ({len(entries)}) ━━")

        for entry in entries:
            hours = 0
            try:
                posted = datetime.strptime(entry["time"], "%Y-%m-%d %H:%M:%S")
                posted = posted.replace(tzinfo=timezone.utc)
                hours = helpers.hours_since(now, posted)
            except (ValueError, KeyError):
                pass

            icon = "🔴" if hours >= 48 else "🟡" if hours >= 24 else "⚪"
            user = entry.get("name", "?")
            preview = entry.get("preview", "")
            link = entry.get("link", "")

            line = f"{icon} {user} ({_age_str(hours)}):"
            if preview:
                line += f"\n{preview}"
            if link:
                line += f"\n{link}"
            lines.append(line)

    return "\n".join(lines)
