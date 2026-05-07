"""GM escalation: nudge the GM when queues go unreplied for 12h+.

Every 12h, one combined message lists ALL currently stale campaigns.
Level is derived from the worst (oldest) queue age, not a counter:
  12–24h → level 1  📋 gentle reminder
  24–48h → level 2  ⚠️ more urgent + DM
  48–72h → level 3  🔴 very urgent + DM
  72h+   → level 4  🚨🚨 maximum + DM

State: state["gm_escalation"] = {"last_at": iso}
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

_LEVEL_THRESHOLDS = [12, 24, 48, 72]  # hours → level 1, 2, 3, 4


def _level_for_hours(hours: float) -> int:
    level = 0
    for threshold in _LEVEL_THRESHOLDS:
        if hours >= threshold:
            level += 1
    return min(level, len(_HEADERS))


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
    """Send one combined escalation message per 12h for all stale queues."""
    now = now or datetime.now(timezone.utc)
    gm_uid = config.get("gm_user_id")
    bot_topic = config.get("gm_queue_topic_id") or config.get("bot_topic_id")
    group_id = config.get("group_id")
    if not gm_uid or not bot_topic or not group_id:
        return

    scanned = scan_transcripts(config, state)
    if not scanned:
        return

    stale = []
    max_hours = 0.0
    for pid, data in scanned.items():
        if not data.get("entries"):
            continue
        oldest_h = _oldest_hours(data["entries"], now)
        if oldest_h >= _LEVEL_THRESHOLDS[0]:
            code = data.get("code", "")
            name = data["campaign"]
            label = f"{code}: {name}" if code else name
            stale.append((label, int(oldest_h)))
            if oldest_h > max_hours:
                max_hours = oldest_h

    if not stale:
        state.setdefault("gm_escalation", {})["last_at"] = None
        return

    esc = state.setdefault("gm_escalation", {})
    last_str = esc.get("last_at")
    if last_str:
        try:
            elapsed_h = (now - datetime.fromisoformat(last_str)).total_seconds() / 3600
            if elapsed_h < _INTERVAL_H:
                return
        except (ValueError, TypeError):
            pass

    level = _level_for_hours(max_hours)
    header = _HEADERS[level - 1]
    lines = [header, ""]
    for label, hours in sorted(stale, key=lambda x: -x[1]):
        lines.append(f"  {label} — {hours}h")
    msg = "\n".join(lines)

    tg.send_message(group_id, bot_topic, msg)
    if level >= 2:
        tg.send_message(gm_uid, None, msg)

    esc["last_at"] = now.isoformat()
    print(f"GM escalation L{level} ({int(max_hours)}h worst): {len(stale)} campaigns")
