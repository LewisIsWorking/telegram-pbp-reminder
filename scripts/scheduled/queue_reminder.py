"""Daily GM queue reminder posted to bot topic."""

from datetime import datetime, timezone

import helpers
import telegram as tg
from commands.queue_scan import scan_transcripts

def _gm_mentions(config: dict, state: dict, pid: str) -> str:
    gm_ids = helpers.gm_ids_for_campaign(config, pid)
    if not gm_ids:
        return "@PathWars"
    names = []
    for uid in gm_ids:
        match = next((p for p in state.get("players", {}).values()
                       if p.get("user_id") == str(uid)), None)
        if match:
            u = match.get("username", "")
            names.append(f"@{u}" if u else match.get("first_name", "@PathWars"))
        else:
            names.append("@PathWars")
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
    scanned = scan_transcripts(config, state)

    # Build a fingerprint of the current queue state
    fingerprint_parts = []
    for pid in sorted(scanned.keys()):
        data = scanned[pid]
        for entry in data["entries"]:
            fingerprint_parts.append(f"{pid}:{entry['time']}")
    fingerprint = "|".join(fingerprint_parts) if fingerprint_parts else "empty"

    # Only post if queue changed since last post, OR it's the daily reminder hour
    daily_hour = config.get("queue_daily_hour")
    is_daily = False
    if daily_hour is not None and now.hour == daily_hour:
        last_daily = state.get("last_queue_daily", "")
        if last_daily != now.date().isoformat():
            is_daily = True

    if not is_daily and fingerprint == state.get("last_queue_fingerprint", ""):
        return

    if not scanned:
        state["last_queue_fingerprint"] = "empty"
        return

    group_id = config["group_id"]
    total = sum(len(d["entries"]) for d in scanned.values())
    if total == 0:
        if state.get("last_queue_fingerprint", "empty") != "empty":
            tg.send_message(group_id, bot_topic, "📋 All caught up! No unreplied messages.")
        state["last_queue_fingerprint"] = fingerprint
        return

    # Build priority set from config
    priority_pids = set()
    for pair in config.get("topic_pairs", []):
        if pair.get("queue_priority"):
            priority_pids.add(str(pair["pbp_topic_ids"][0]))

    def sort_key(pid):
        entries = scanned[pid]["entries"]
        oldest = min(e.get("time", "9999") for e in entries)
        return (0 if pid in priority_pids else 1, oldest)

    sorted_pids = sorted(scanned.keys(), key=sort_key)
    from commands.queue_stats import get_today_clears
    cleared_today = get_today_clears(state, now)
    streak = f" | ✅ {cleared_today} cleared today" if cleared_today else ""
    # Per-campaign summary line
    summary_parts = []
    for pid in sorted_pids:
        d = scanned[pid]
        c = d.get("code", "")
        summary_parts.append(f"{c}:{len(d['entries'])}" if c else f"{d['campaign']}:{len(d['entries'])}")
    summary = " ".join(summary_parts)
    # Precompute fastest responders per campaign
    from commands.queue_analytics import player_momentum
    state.setdefault("_config_cache", config)
    momentum_lines = player_momentum(state, config)
    momentum_map = {}
    for m in momentum_lines:
        if ": " in m:
            k, v = m.split(": ", 1)
            momentum_map[k] = v
    lines = [f"📋 Unreplied: {total}{streak}", summary]

    for pid in sorted_pids:
        data = scanned[pid]
        entries = data["entries"]
        name = data["campaign"]
        code = data.get("code", "")
        label = f"{code}: {name}" if code else name
        gm = _gm_mentions(config, state, pid)
        scene = state.get("current_scenes", {}).get(pid, "")
        scene_str = f" 🎭 {scene}" if scene else ""
        pin = "📌 " if pid in priority_pids else ""
        fast_key = code if code else name
        fast = f" ⚡{momentum_map[fast_key]}" if fast_key in momentum_map else ""
        lines.append(f"━━ {pin}{label} ({len(entries)}){scene_str} ━━ {gm}{fast}")
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
        state["last_queue_fingerprint"] = fingerprint
        if is_daily:
            state["last_queue_daily"] = now.date().isoformat()
        print(f"Queue reminder: {total} unreplied ({len(msgs)} msg)")

