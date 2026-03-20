"""GM reply queue: track unreplied player messages."""

from datetime import datetime, timezone

import helpers
from commands.queue_scan import scan_transcripts


def build_queue(config: dict, state: dict) -> str:
    """Build /queue output: unreplied player messages across all campaigns.

    Uses transcript scanning as the primary source. Includes links
    when message_ids are available in transcripts (msg#12345 tags).
    """
    now = datetime.now(timezone.utc)
    scanned = scan_transcripts(config)

    if not scanned:
        return "All caught up! No unreplied player messages."

    lines = ["📋 GM Reply Queue:\n"]
    total = 0

    for pair in config.get("topic_pairs", []):
        pid = str(pair["pbp_topic_ids"][0])
        if pid not in scanned:
            continue

        data = scanned[pid]
        entries = data["entries"]
        name = data["campaign"]
        total += len(entries)
        lines.append(f"\n━━ {name} ({len(entries)}) ━━")

        for entry in entries:
            hours = 0
            age = "?"
            try:
                posted = datetime.strptime(entry["time"], "%Y-%m-%d %H:%M:%S")
                posted = posted.replace(tzinfo=timezone.utc)
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
            user = entry.get("name", "?")
            preview = entry.get("preview", "")
            link = entry.get("link", "")

            line = f"{icon} {user} ({age}):"
            if preview:
                line += f"\n{preview}"
            if link:
                line += f"\n{link}"
            lines.append(line)

    lines.insert(1, f"Total: {total} unreplied\n")
    return "\n".join(lines)
