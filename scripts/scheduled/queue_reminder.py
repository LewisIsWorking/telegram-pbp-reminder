"""Daily GM queue reminder posted to bot topic."""

from datetime import datetime, timezone

import helpers
import telegram as tg
from commands.queue_scan import scan_transcripts
from commands.queue_format import entry_age_icon, age_str, short_preview
from scheduled.topic_queue_poster import post_topic_queues
from scheduled.queue_silence import silent_campaigns


def _gm_mentions(config: dict, state: dict, pid: str) -> str:
    gm_ids = helpers.gm_ids_for_campaign(config, pid)
    if not gm_ids:
        return "@PathWars"  # pragma: no cover
    names = []
    for uid in gm_ids:
        match = next((p for p in state.get("players", {}).values()
                       if p.get("user_id") == str(uid)), None)
        if match:
            u = match.get("username", "")  # pragma: no cover
            names.append(f"@{u}" if u else match.get("first_name", "@PathWars"))  # pragma: no cover
        else:
            names.append("@PathWars")
    return ", ".join(names)

def post_queue_reminder(config: dict, state: dict, *, now: datetime | None = None, **_kw) -> None:
    bot_topic = config.get("bot_topic_id")
    if not bot_topic:
        return  # pragma: no cover
    now = now or datetime.now(timezone.utc)
    scanned = scan_transcripts(config, state)

    # Maintain per-topic pinned queues — always runs, independent of bot-topic posting
    post_topic_queues(config, scanned, now)

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

    group_id = config["group_id"]
    silent_lines = silent_campaigns(config, state, scanned, now)
    if silent_lines:
        fingerprint += "|silent:" + "|".join(silent_lines)
    if not is_daily and fingerprint == state.get("last_queue_fingerprint", ""):
        return

    if not scanned and not silent_lines:
        state["last_queue_fingerprint"] = "empty"
        return

    total = sum(len(d["entries"]) for d in scanned.values())
    if total == 0 and not silent_lines:
        if state.get("last_queue_fingerprint", "empty") != "empty":  # pragma: no cover
            tg.send_message(group_id, bot_topic, "━━━━━━━━━━━━━━━━\n📋 All caught up! No unreplied messages.")  # pragma: no cover
        state["last_queue_fingerprint"] = fingerprint  # pragma: no cover
        return  # pragma: no cover

    # Build priority map from config — lower number = higher priority
    # queue_priority: True (legacy) → level 1; numeric value used directly
    # C11 uses level 0 (highest), C06 uses level 1, rest use level 2
    priority_map: dict[str, int] = {}
    for pair in config.get("topic_pairs", []):
        qp = pair.get("queue_priority")
        if qp is not None and qp is not False:
            pid_str = str(pair["pbp_topic_ids"][0])
            priority_map[pid_str] = int(qp) if isinstance(qp, int) else 1
    priority_pids = set(priority_map.keys())  # kept for pin-icon display

    def sort_key(pid):
        entries = scanned[pid]["entries"]
        oldest = min(e.get("time", "9999") for e in entries)
        return (priority_map.get(pid, 2), oldest)

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
    queue_num = state.get("queue_post_count", 0) + 1
    lines = [f"━━━━━━━━━━━━━━━━\n📋 GM Queue #{queue_num} — Unreplied: {total}{streak}\n{summary}\nAge: 🆕<1h 🌱6h 🌿12h 🌳1d 🟢2d 🟩3d 🟡4d 🟨5d 🟠6d 🟧7d 🔴8d 🟥9d 🟣10d 🟪11d 🔵12d 🟦13d 🟤14d 🟫15d ⚫16d ⬛17d 💀21d ☠️25d"]

    entry_num = 1
    for pid in sorted_pids:
        data = scanned[pid]
        entries = data["entries"]
        name = data["campaign"]
        code = data.get("code", "")
        # Look up campaign emoji from config
        emoji = next((p.get("emoji", "") for p in config.get("topic_pairs", [])
                      if p.get("code") == code), "")
        label = f"{code}: {name}" if code else name
        gm = _gm_mentions(config, state, pid)
        scene = state.get("current_scenes", {}).get(pid, "")
        scene_str = f" 🎭 {scene}" if scene else ""
        pin = "📌 " if pid in priority_pids else ""
        fast_key = code if code else name
        fast = f" ⚡{momentum_map[fast_key]}" if fast_key in momentum_map else ""
        emoji_prefix = f"{emoji} " if emoji else ""
        lines.append(f"━━ {pin}{emoji_prefix}{label} ({len(entries)}){scene_str} ━━ {gm}{fast}")
        for entry in entries:
            hours = 0
            try:
                posted = datetime.strptime(entry["time"], "%Y-%m-%d %H:%M:%S")
                posted = posted.replace(tzinfo=timezone.utc)
                hours = helpers.hours_since(now, posted)
            except (ValueError, KeyError):  # pragma: no cover
                pass  # pragma: no cover
            icon = entry_age_icon(hours)
            user = entry.get("name", "?")
            preview = short_preview(entry.get("preview", ""))
            link = entry.get("link", "")
            line = f"{entry_num:02d} {icon} {age_str(hours)}. {user}: {preview}"
            if link:
                line += f" 🔗 {link}"  # pragma: no cover
            lines.append(line)
            entry_num += 1

    message = "\n".join(lines)

    if silent_lines:
        lines.append("━━ 💤 Silent campaigns ━━")
        lines.extend(silent_lines)

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
    first_msg_id = None
    for i, msg in enumerate(msgs):
        result = tg.send_message_id(group_id, bot_topic, msg)
        if result:
            sent = True
            if i == 0:
                first_msg_id = result
    if sent:
        # Pin the new message, unpin the previous one
        if first_msg_id:
            prev_pin = state.get("last_queue_pin_id")
            if prev_pin:
                tg.unpin_message(group_id, prev_pin)
            tg.pin_message(group_id, first_msg_id)
            state["last_queue_pin_id"] = first_msg_id
        state["last_queue_fingerprint"] = fingerprint
        state["queue_post_count"] = queue_num
        if is_daily:
            slot_key = f"{now.date().isoformat()}:{now.hour:02d}"
            slots = state.setdefault("last_queue_daily_slots", [])
            if slot_key not in slots:
                slots.append(slot_key)
            # Keep only last 14 slots (7 days × 2 posts/day)
            state["last_queue_daily_slots"] = slots[-14:]
            state["last_queue_daily"] = now.date().isoformat()  # backwards compat
        print(f"Queue reminder: {total} unreplied ({len(msgs)} msg)")

