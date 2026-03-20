"""Daily GM queue reminder posted to bot topic."""

from datetime import datetime, timezone

import helpers
import telegram as tg
from commands.queue_scan import scan_transcripts


def _gm_mentions(config: dict, state: dict, pid: str) -> str:
    """Build mention string for campaign GMs using their actual names."""
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

    # Scan transcripts for the full picture
    scanned = scan_transcripts(config)
    if not scanned:
        state["last_queue_reminder"] = now.isoformat()
        return

    group_id = config["group_id"]
    lines = ["📋 Unreplied messages:\n"]
    total = 0

    for pair in config.get("topic_pairs", []):
        pid = str(pair["pbp_topic_ids"][0])
        if pid not in scanned:
            continue

        data = scanned[pid]
        entries = data["entries"]
        name = data["campaign"]
        total += len(entries)

        gm = _gm_mentions(config, state, pid)
        lines.append(f"━━ {name} ({len(entries)}) — {gm} ━━")

        for entry in entries:
            hours = 0
            age = ""
            try:
                posted = datetime.strptime(entry["time"], "%Y-%m-%d %H:%M:%S")
                posted = posted.replace(tzinfo=timezone.utc)
                hours = helpers.hours_since(now, posted)
                if hours >= 24:
                    age = f"{int(hours // 24)}d"
                else:
                    age = f"{int(hours)}h"
            except (ValueError, KeyError):
                pass

            icon = "🔴" if hours >= 48 else "🟡" if hours >= 24 else "⚪"
            user = entry.get("name", "?")

            lines.append(f"{icon} {user} ({age}):")
            preview = entry.get("preview", "")
            if preview:
                lines.append(preview)
            link = entry.get("link", "")
            if link:
                lines.append(link)
            lines.append("")

    if total == 0:
        state["last_queue_reminder"] = now.isoformat()
        return

    lines.insert(1, f"Total: {total}\n")
    message = "\n".join(lines).rstrip()

    if tg.send_message(group_id, bot_topic, message):
        state["last_queue_reminder"] = now.isoformat()
        print(f"Queue reminder: {total} unreplied messages")
