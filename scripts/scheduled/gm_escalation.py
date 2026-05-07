"""GM escalation: nudge the GM when queues go unreplied for 12h+.

Every 12h, one combined message lists ALL currently stale campaigns.
Escalation level increases globally with each nudge.

State: state["gm_escalation"] = {"level": N, "last_at": iso, "per_pid": {pid: level}}
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
    """Send one combined escalation message per 12h interval for all stale queues."""
    now = now or datetime.now(timezone.utc)
    gm_uid = config.get("gm_user_id")
    bot_topic = config.get("gm_queue_topic_id") or config.get("bot_topic_id")
    group_id = config.get("group_id")
    if not gm_uid or not bot_topic or not group_id:
        return

    scanned = scan_transcripts(config, state)
    if not scanned:
        return

    # Collect all currently stale campaigns
    stale = []
    for pid, data in scanned.items():
        if not data.get("entries"):
            continue
        oldest_h = _oldest_hours(data["entries"], now)
        if oldest_h >= _INTERVAL_H:
            code = data.get("code", "")
            name = data["campaign"]
            label = f"{code}: {name}" if code else name
            stale.append((label, int(oldest_h)))

    if not stale:
        state["gm_escalation"] = {"level": 0, "last_at": None}
        return

    # Check global 12h interval
    esc = state.setdefault("gm_escalation", {})
    last_str = esc.get("last_at")
    if last_str:
        try:
            elapsed_h = (now - datetime.fromisoformat(last_str)).total_seconds() / 3600
            if elapsed_h < _INTERVAL_H:
                return
        except (ValueError, TypeError):
            pass

    level = min(esc.get("level", 0) + 1, len(_HEADERS))
    header = _HEADERS[level - 1]
    lines = [header, ""]
    for label, hours in sorted(stale, key=lambda x: -x[1]):
        lines.append(f"  {label} — {hours}h")
    msg = "\n".join(lines)

    tg.send_message(group_id, bot_topic, msg)
    if level >= 2:
        tg.send_message(gm_uid, None, msg)

    esc["level"] = level
    esc["last_at"] = now.isoformat()
    print(f"GM escalation L{level}: {len(stale)} stale campaigns")
