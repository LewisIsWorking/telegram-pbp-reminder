"""Daily GM queue reminder posted to bot topic."""

from datetime import datetime, timezone

import helpers
import telegram as tg
from commands.queue_scan import scan_transcripts
from commands.queue_format import entry_age_icon, age_str, short_preview, format_queue_line
from scheduled.topic_queue_poster import post_topic_queues
from scheduled.queue_silence import silent_campaigns
from scheduled.gm_queue_history import post_and_persist
from scheduled.queue_caught_up import post_caught_up as _post_caught_up


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
    bot_topic = config.get("gm_queue_topic_id") or config.get("bot_topic_id")
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
        # Queue is empty AND no silent campaigns to display. If we're
        # transitioning from a non-empty fingerprint, post a one-time
        # "All caught up!" notification so GMs see the state change;
        # otherwise stay silent so we don't spam the topic with the
        # same message every cron tick.
        #
        # Note: the scanner (queue_scan.py:185-197) omits campaigns
        # with zero entries, so this branch — not the total==0 branch
        # below — is the one that actually fires when every queue is
        # clean.
        if state.get("last_queue_fingerprint", "empty") != "empty":
            # See _post_caught_up docstring — routes via batch
            # machinery so the previous GM queue gets evicted.
            _post_caught_up(state, group_id, bot_topic)
        state["last_queue_fingerprint"] = "empty"
        return

    total = sum(len(d["entries"]) for d in scanned.values())
    if total == 0 and not silent_lines:
        if state.get("last_queue_fingerprint", "empty") != "empty":
            # Defensive path (current scanner doesn't produce this
            # shape but might in the future). Same fix as line-68.
            _post_caught_up(state, group_id, bot_topic)
        state["last_queue_fingerprint"] = fingerprint
        return

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
    from commands.queue_stats import get_today_clears, get_alltime_clears
    cleared_today = get_today_clears(state, now)
    cleared_alltime = get_alltime_clears()
    streak = f" | ✅ {cleared_today} today" if cleared_today else ""
    streak += f" | 🏆 {cleared_alltime} all-time" if cleared_alltime else ""
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
            line = format_queue_line(entry_num, entry, hours)
            lines.append(line)
            entry_num += 1

    if silent_lines:
        lines.append("━━ 💤 Silent campaigns ━━")
        lines.extend(silent_lines)

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

    sent, _first_msg_id = post_and_persist(state, group_id, bot_topic, msgs)
    if sent:
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

