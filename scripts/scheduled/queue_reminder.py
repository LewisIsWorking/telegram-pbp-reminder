"""Daily GM queue reminder posted to bot topic."""

from datetime import datetime, timezone

import helpers
import telegram as tg
from commands.queue_scan import scan_transcripts
from commands.queue_format import entry_age_icon, age_str, short_preview


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

    # Only post if queue changed since last post, OR it's a scheduled reminder hour
    # queue_daily_hours: list of UTC hours to post (e.g. [9, 21])
    # queue_daily_hour: legacy single-hour setting
    raw = config.get("queue_daily_hours") or (
        [config["queue_daily_hour"]] if config.get("queue_daily_hour") is not None else []
    )
    daily_hours = raw if isinstance(raw, list) else [raw]
    is_daily = False
    if now.hour in daily_hours:
        slot_key = f"{now.date().isoformat()}:{now.hour:02d}"
        posted_slots = state.get("last_queue_daily_slots", [])
        if slot_key not in posted_slots:
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
            tg.send_message(group_id, bot_topic, "━━━━━━━━━━━━━━━━\n📋 All caught up! No unreplied messages.")
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
    lines = [f"━━━━━━━━━━━━━━━━\n📋 Unreplied: {total}{streak}", summary]

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
            icon = entry_age_icon(hours)
            user = entry.get("name", "?")
            preview = short_preview(entry.get("preview", ""))
            link = entry.get("link", "")
            line = f"{icon} {age_str(hours)}. {user}: {preview}"
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
            slot_key = f"{now.date().isoformat()}:{now.hour:02d}"
            slots = state.setdefault("last_queue_daily_slots", [])
            if slot_key not in slots:
                slots.append(slot_key)
            # Keep only last 14 slots (7 days × 2 posts/day)
            state["last_queue_daily_slots"] = slots[-14:]
            state["last_queue_daily"] = now.date().isoformat()  # backwards compat
        print(f"Queue reminder: {total} unreplied ({len(msgs)} msg)")

