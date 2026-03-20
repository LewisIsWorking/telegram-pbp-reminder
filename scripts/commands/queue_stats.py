"""
Queue statistics: reply streak, history, estimated reply time.

Tracks GM reply activity for productivity stats and player expectations.
"""

from datetime import datetime, timezone, timedelta

import helpers


def record_reply(pid: str, state: dict, now: datetime | None = None) -> None:
    """Record a GM reply for streak/history tracking."""
    now = now or datetime.now(timezone.utc)
    history = state.setdefault("queue_history", {}).setdefault(pid, [])
    history.append(now.isoformat())
    # Keep last 500
    if len(history) > 500:
        state["queue_history"][pid] = history[-500:]


def get_today_clears(state: dict, now: datetime | None = None) -> int:
    """Count total replies cleared today across all campaigns."""
    now = now or datetime.now(timezone.utc)
    today = now.date().isoformat()
    total = 0
    for pid, history in state.get("queue_history", {}).items():
        for ts in history:
            if ts[:10] == today:
                total += 1
    return total


def get_week_clears(state: dict, now: datetime | None = None) -> int:
    """Count total replies cleared this week."""
    now = now or datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).isoformat()
    total = 0
    for pid, history in state.get("queue_history", {}).items():
        for ts in history:
            if ts >= week_ago:
                total += 1
    return total


def avg_reply_hours(pid: str, state: dict) -> float | None:
    """Estimate average GM reply time for a campaign.

    Uses timestamps of queue clears vs the posts they replied to.
    Falls back to average gap between GM posts.
    """
    topic_ts = helpers.get_topic_timestamps(state, pid)
    gm_ids_set = set()
    # Find GM timestamps
    for pair in state.get("_config_cache", {}).get("topic_pairs", []):
        if str(pair.get("pbp_topic_ids", [None])[0]) == pid:
            gm_ids_set = set(str(u) for u in pair.get("gm_user_ids", []))
            break

    gm_timestamps = []
    for uid, timestamps in topic_ts.items():
        if uid in gm_ids_set:
            gm_timestamps.extend(timestamps)

    if len(gm_timestamps) < 3:
        return None

    gm_timestamps.sort()
    gaps = []
    for i in range(1, len(gm_timestamps)):
        a = datetime.fromisoformat(gm_timestamps[i - 1])
        b = datetime.fromisoformat(gm_timestamps[i])
        gap = (b - a).total_seconds() / 3600
        if gap < 168:  # ignore 7+ day gaps (breaks)
            gaps.append(gap)

    return sum(gaps) / len(gaps) if gaps else None


def build_queue_stats(config: dict, state: dict) -> str:
    """Build /queuestats output."""
    now = datetime.now(timezone.utc)
    today = get_today_clears(state, now)
    week = get_week_clears(state, now)

    lines = [f"📊 GM Queue Stats\n"]
    lines.append(f"Cleared today: {today}")
    lines.append(f"Cleared this week: {week}")

    # Per-campaign avg reply time
    lines.append("")
    for pair in config.get("topic_pairs", []):
        pid = str(pair["pbp_topic_ids"][0])
        name = pair["name"]
        code = pair.get("code", "")
        label = f"{code}: {name}" if code else name

        # Cache config for avg_reply_hours
        state.setdefault("_config_cache", config)
        avg = avg_reply_hours(pid, state)
        if avg is not None:
            if avg >= 24:
                avg_str = f"{avg / 24:.1f}d"
            else:
                avg_str = f"{avg:.0f}h"
            lines.append(f"{label}: avg reply ~{avg_str}")

    return "\n".join(lines)
