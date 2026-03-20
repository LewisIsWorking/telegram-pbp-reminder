"""GM reply queue: track unreplied player messages."""

from datetime import datetime, timezone

import helpers
from commands.queue_scan import scan_transcripts


def _short_preview(text: str, words: int = 5) -> str:
    w = text.replace("\n", " ").split()[:words]
    result = " ".join(w)
    if len(text.split()) > words:
        result += "..."
    return result


def _age_str(hours: float) -> str:
    days = int(hours // 24)
    h = int(hours % 24)
    if days > 0:
        return f"{days}d {h}h"
    return f"{h}h"


def build_queue(config: dict, state: dict) -> str:
    """Build /queue: unreplied messages, campaigns sorted by oldest."""
    now = datetime.now(timezone.utc)
    scanned = scan_transcripts(config, state)
    if not scanned:
        return "All caught up! No unreplied player messages."

    total = sum(len(d["entries"]) for d in scanned.values())

    def oldest_time(pid):
        entries = scanned[pid]["entries"]
        return min(e.get("time", "9999") for e in entries)

    sorted_pids = sorted(scanned.keys(), key=oldest_time)
    lines = [f"📋 GM Reply Queue: {total} unreplied"]

    for pid in sorted_pids:
        data = scanned[pid]
        entries = data["entries"]
        name = data["campaign"]
        code = data.get("code", "")
        label = f"{code}: {name}" if code else name
        lines.append(f"━━ {label} ({len(entries)}) ━━")
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
            preview = _short_preview(entry.get("preview", ""))
            link = entry.get("link", "")
            line = f"{icon} {_age_str(hours)}. {user}: {preview}"
            if link:
                line += f" 🔗 {link}"
            lines.append(line)

    return "\n".join(lines)
