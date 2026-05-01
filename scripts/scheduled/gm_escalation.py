"""GM escalation: nudge the GM when queues go unreplied for 12h+.

Every 12h any unreplied entry sits in the queue, the bot escalates.
All stale campaigns are batched into a single message per run.

State tracked in state["gm_escalation"][pid] = {"level": N, "last_at": iso}
"""

from datetime import datetime, timezone

import helpers
import telegram as tg
from commands.queue_scan import scan_transcripts

_INTERVAL_H = 12

_HEADERS = [
    "📋 Hey — some campaigns have replies waiting. Don't let them slip! 🙂",
    "⚠️ GM queue alert — players are waiting on you!",
    "🔴 These queues are getting really stale. Get on it! 🚨",
    "🚨🚨 SORT IT OUT, GM! 🚨🚨",
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
    """Batch all stale campaigns into a single escalation message per run."""
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
    due = []  # campaigns ready for a nudge this run

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

        if last_at_str:
            try:
                elapsed_h = (now - datetime.fromisoformat(last_at_str)).total_seconds() / 3600
                if elapsed_h < _INTERVAL_H:
                    continue
            except (ValueError, TypeError):
                pass

        level = min(level + 1, len(_HEADERS))
        code = data.get("code", "")
        name = data["campaign"]
        label = f"{code}: {name}" if code else name
        due.append((pid, label, int(oldest_h), level))

    if not due:
        return

    # Use the highest level among due campaigns for the header
    max_level = max(d[3] for d in due)
    header = _HEADERS[max_level - 1]
    lines = [header, ""]
    for _, label, hours, _ in sorted(due, key=lambda x: -x[2]):
        lines.append(f"  {label} — {hours}h")
    msg = "\n".join(lines)

    tg.send_message(group_id, bot_topic, msg)
    if max_level >= 2:
        tg.send_message(gm_uid, None, msg)

    for pid, _, _, level in due:
        esc[pid] = {"level": level, "last_at": now.isoformat()}
        print(f"GM escalation L{level}: {pid}")
