"""Player-facing queue: shows what the GM owes YOU."""

from datetime import datetime, timezone

import helpers
from commands.queue_scan import scan_transcripts


def _age_str(hours: float) -> str:
    days = int(hours // 24)
    h = int(hours % 24)
    return f"{days}d {h}h" if days > 0 else f"{h}h"


def build_waiting(user_id: str, user_name: str, pid: str,
                  campaign_name: str, config: dict, state: dict) -> str:
    """Build /waiting output for a specific player in a specific campaign."""
    now = datetime.now(timezone.utc)
    scanned = scan_transcripts(config, state)
    data = scanned.get(pid)

    if not data:
        return f"No pending messages in {campaign_name}. The GM is all caught up!"

    # Find this player's entries
    mine = []
    for entry in data["entries"]:
        # Match by name (transcripts don't store user_id)
        # Check all player entries for this user
        player_key = f"{pid}:{user_id}"
        p = state.get("players", {}).get(player_key, {})
        first = p.get("first_name", "")
        if first and entry["name"].startswith(first):
            mine.append(entry)

    if not mine:
        return f"No pending messages from you in {campaign_name}."

    lines = [f"⏳ Waiting on GM in {campaign_name}: {len(mine)}\n"]
    for entry in mine:
        hours = 0
        try:
            posted = datetime.strptime(entry["time"], "%Y-%m-%d %H:%M:%S")
            posted = posted.replace(tzinfo=timezone.utc)
            hours = helpers.hours_since(now, posted)
        except (ValueError, KeyError):
            pass

        preview = entry.get("preview", "").replace("\n", " ").split()[:8]
        preview_str = " ".join(preview)
        if len(entry.get("preview", "").split()) > 8:
            preview_str += "..."
        link = entry.get("link", "")

        line = f"🕐 {_age_str(hours)}: {preview_str}"
        if link:
            line += f" 🔗 {link}"
        lines.append(line)

    return "\n".join(lines)


def build_waiting_all(user_id: str, user_name: str,
                      config: dict, state: dict) -> str:
    """Build /waiting output across all campaigns."""
    now = datetime.now(timezone.utc)
    scanned = scan_transcripts(config, state)

    lines = []
    total = 0

    for pair in config.get("topic_pairs", []):
        pid = str(pair["pbp_topic_ids"][0])
        if pid not in scanned:
            continue

        data = scanned[pid]
        code = data.get("code", "")
        name = data["campaign"]
        label = f"{code}: {name}" if code else name

        # Match player entries
        mine = []
        player_key = f"{pid}:{user_id}"
        p = state.get("players", {}).get(player_key, {})
        first = p.get("first_name", "")
        for entry in data["entries"]:
            if first and entry["name"].startswith(first):
                mine.append(entry)

        if not mine:
            continue

        total += len(mine)
        lines.append(f"━━ {label} ({len(mine)}) ━━")
        for entry in mine:
            hours = 0
            try:
                posted = datetime.strptime(entry["time"], "%Y-%m-%d %H:%M:%S")
                posted = posted.replace(tzinfo=timezone.utc)
                hours = helpers.hours_since(now, posted)
            except (ValueError, KeyError):
                pass
            preview = " ".join(entry.get("preview", "").replace("\n", " ").split()[:5])
            if len(entry.get("preview", "").split()) > 5:
                preview += "..."
            lines.append(f"🕐 {_age_str(hours)}: {preview}")

    if not lines:
        return f"Nothing waiting on you, {user_name}. GM's all caught up!"

    lines.insert(0, f"⏳ {user_name} — waiting on GM: {total}\n")
    return "\n".join(lines)
