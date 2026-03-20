"""Daily GM queue reminder posted to bot topic."""

from datetime import datetime, timezone

import helpers
import telegram as tg
from commands.queue_scan import scan_transcripts


def _gm_mentions(config: dict, state: dict, pid: str) -> str:
    """Build mention string for campaign GMs."""
    gm_ids = helpers.gm_ids_for_campaign(config, pid)
    if not gm_ids:
        return "GM"
    names = []
    for uid in gm_ids:
        name = None
        for key, p in state.get("players", {}).items():
            if p.get("user_id") == str(uid):
                uname = p.get("username", "")
                name = f"@{uname}" if uname else p.get("first_name", "GM")
                break
        if not name:
            name = "GM"
        names.append(name)
    return ", ".join(names)


def _age_str(hours: float) -> str:
    days = int(hours // 24)
    remaining_h = int(hours % 24)
    return f"{days}d {remaining_h}h" if days > 0 else f"{remaining_h}h"


def post_queue_reminder(config: dict, state: dict, *, now: datetime | None = None, **_kw) -> None:
    """Post unreplied player messages to the bot topic once per day."""
    bot_topic = config.get("bot_topic_id")
    if not bot_topic:
        return

    now = now or datetime.now(timezone.utc)

    last = state.get("last_queue_reminder")
    if last:
        elapsed = helpers.hours_since(now, datetime.fromisoformat(last))
        if elapsed < 22:
            return

    scanned = scan_transcripts(config)
    if not scanned:
        state["last_queue_reminder"] = now.isoformat()
        return

    group_id = config["group_id"]
    total = sum(len(d["entries"]) for d in scanned.values())
    if total == 0:
        state["last_queue_reminder"] = now.isoformat()
        return

    # Sort campaigns by oldest unreplied message
    def oldest_time(pid):
        entries = scanned[pid]["entries"]
        return min(e.get("time", "9999") for e in entries) if entries else "9999"

    sorted_pids = sorted(scanned.keys(), key=oldest_time)

    blocks = []
    for pid in sorted_pids:
        data = scanned[pid]
        entries = data["entries"]
        name = data["campaign"]
        gm = _gm_mentions(config, state, pid)

        lines = [f"━━ {name} ({len(entries)}) ━━", gm]

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
            if len(preview) > 200:
                preview = preview[:197] + "..."
            link = entry.get("link", "")

            lines.append(f"{icon} {user} ({_age_str(hours)}):")
            if preview:
                lines.append(preview)
            if link:
                lines.append(link)

        blocks.append("\n".join(lines))

    header = f"📋 Unreplied messages: {total}\n"

    # Split into messages under 3900 chars
    messages = []
    current = header
    for block in blocks:
        if len(current) + len(block) + 2 > 3900:
            messages.append(current.rstrip())
            current = ""
        current += "\n" + block + "\n"
    if current.strip():
        messages.append(current.rstrip())

    sent = False
    for msg in messages:
        if tg.send_message(group_id, bot_topic, msg):
            sent = True

    if sent:
        state["last_queue_reminder"] = now.isoformat()
        print(f"Queue reminder: {total} unreplied ({len(messages)} msg)")
