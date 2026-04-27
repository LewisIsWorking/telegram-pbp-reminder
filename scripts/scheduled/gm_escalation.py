"""GM escalation: nudge the GM when their queue goes unreplied for 12h+.

Every 12h an unreplied entry sits in the queue, the bot escalates:
  Level 1 (12h)  → bot topic only, gentle reminder
  Level 2 (24h)  → bot topic + DM, more urgent
  Level 3 (36h)  → bot topic + DM, very urgent
  Level 4+ (48h+)→ bot topic + DM, maximum urgency

State tracked in state["gm_escalation"][pid] = {"level": N, "last_at": iso}
"""

from datetime import datetime, timezone

import helpers
import telegram as tg
from commands.queue_scan import scan_transcripts

_INTERVAL_H = 12

_MESSAGES = [
    "📋 Hey — {label} has replies waiting for {hours}h. Don't let it slip! 🙂",
    "⚠️ {label} queue is {hours}h old. Players are waiting on you, GM!",
    "🔴 {label} queue is really stale now ({hours}h). Get on it! 🚨",
    "🚨🚨 {label} — {hours}h and still unreplied. SORT IT OUT, GM! 🚨🚨",
]


def _oldest_hours(entries: list, now: datetime) -> float:
    oldest = 0.0
    for entry in entries:
        try:
            posted = datetime.strptime(entry["time"], "%Y-%m-%d %H:%M:%S")
            posted = posted.replace(tzinfo=timezone.utc)
            h = helpers.hours_since(now, posted)
            if h > oldest:
                oldest = h
        except (ValueError, KeyError):
            pass
    return oldest


def check_gm_escalation(config: dict, state: dict,
                         *, now: datetime | None = None, **_kw) -> None:
    """Escalate GM nudges every 12h while queue has unreplied entries >12h old."""
    now = now or datetime.now(timezone.utc)
    gm_uid = config.get("gm_user_id")
    bot_topic = config.get("gm_queue_topic_id") or config.get("bot_topic_id")
    group_id = config.get("group_id")
    if not gm_uid or not bot_topic or not group_id:
        return

    scanned = scan_transcripts(config, state)
    if not scanned:
        return

    esc = state.setdefault("gm_escalation", {})

    for pid, data in scanned.items():
        if not data.get("entries"):
            esc.pop(pid, None)
            continue

        oldest_h = _oldest_hours(data["entries"], now)
        if oldest_h < _INTERVAL_H:
            esc.pop(pid, None)
            continue

        entry = esc.get(pid, {})
        last_at_str = entry.get("last_at")
        level = entry.get("level", 0)

        # Check if 12h have elapsed since last nudge
        if last_at_str:
            try:
                last = datetime.fromisoformat(last_at_str)
                elapsed_h = (now - last).total_seconds() / 3600
                if elapsed_h < _INTERVAL_H:
                    continue
            except (ValueError, TypeError):
                pass

        level = min(level + 1, len(_MESSAGES))
        code = data.get("code", "")
        name = data["campaign"]
        label = f"{code}: {name}" if code else name
        msg_tmpl = _MESSAGES[level - 1]
        msg = msg_tmpl.format(label=label, hours=int(oldest_h))

        tg.send_message(group_id, bot_topic, msg)
        if level >= 2:
            tg.send_message(gm_uid, None, msg)  # DM

        esc[pid] = {"level": level, "last_at": now.isoformat()}
        print(f"GM escalation L{level}: {label} ({int(oldest_h)}h)")
