"""Daily GM queue reminder posted to bot topic."""

from datetime import datetime, timezone

import helpers
import telegram as tg
from commands.queue_scan import scan_transcripts


def _gm_mentions(config: dict, state: dict, pid: str) -> str:
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
        names.append(name or "GM")
    return ", ".join(names)


def _short_preview(text: str, words: int = 5) -> str:
    w = text.replace("\n", " ").split()[:words]
    result = " ".join(w)
    if len(text.split()) > words:
        result += "..."
    return result


def _age_str(hours: float) -> str:
    days = int(hours // 24)
    h = int(hours % 24)
    return f"{days}d {h}h" if days > 0 else f"{h}h"


def post_queue_reminder(config: dict, state: dict, *, now: datetime | None = None, **_kw) -> None:
    bot_topic = config.get("bot_topic_id")
    if not bot_topic:
        return
    now = now or datetime.now(timezone.utc)
    last = state.get("last_queue_reminder")
    if last:
        if helpers.hours_since(now, datetime.fromisoformat(last)) < 22:
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

    def oldest_time(pid):
        entries = scanned[pid]["entries"]
        return min(e.get("time", "9999") for e in entries)

    sorted_pids = sorted(scanned.keys(), key=oldest_time)
    lines = [f"📋 Unreplied: {total}"]

    for pid in sorted_pids:
        data = scanned[pid]
        entries = data["entries"]
        name = data["campaign"]
        code = data.get("code", "")
        label = f"{code}: {name}" if code else name
        gm = _gm_mentions(config, state, pid)
        lines.append(f"━━ {label} ({len(entries)}) ━━ {gm}")
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
            line = f"{icon} {user} ({_age_str(hours)}): {preview}"
            if link:
                line += f" {link}"
            lines.append(line)

    message = "\n".join(lines)

    # Split if needed
    if len(message) <= 4000:
        msgs = [message]
    else:
        msgs = []
        current = ""
        for line in lines:
            if len(current) + len(line) + 1 > 3900:
                msgs.append(current)
                current = ""
            current += line + "\n"
        if current.strip():
            msgs.append(current.rstrip())

    sent = False
    for msg in msgs:
        if tg.send_message(group_id, bot_topic, msg):
            sent = True
    if sent:
        state["last_queue_reminder"] = now.isoformat()
        print(f"Queue reminder: {total} unreplied ({len(msgs)} msg)")
