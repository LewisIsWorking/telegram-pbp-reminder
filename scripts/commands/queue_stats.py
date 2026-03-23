"""
Queue statistics: reply streak, history, estimated reply time,
progress bar, peak hours, age heatmap, player momentum.
"""

from datetime import datetime, timezone, timedelta

import helpers

def record_reply(pid: str, state: dict, entry_preview: str = "",
                 player_name: str = "", now: datetime | None = None) -> None:
    """Record a GM reply for streak/history/archive tracking."""
    now = now or datetime.now(timezone.utc)
    history = state.setdefault("queue_history", {}).setdefault(pid, [])
    history.append(now.isoformat())
    if len(history) > 500:
        state["queue_history"][pid] = history[-500:]
    # Archive: store what was cleared
    archive = state.setdefault("queue_archive", [])
    archive.append({
        "pid": pid, "time": now.isoformat(),
        "player": player_name, "preview": entry_preview[:60],
    })
    if len(archive) > 200:
        state["queue_archive"] = archive[-200:]

def get_today_clears(state: dict, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    today = now.date().isoformat()
    return sum(
        1 for pid, h in state.get("queue_history", {}).items()
        for ts in h if ts[:10] == today
    )

def get_week_clears(state: dict, now: datetime | None = None) -> int:
    now = now or datetime.now(timezone.utc)
    cutoff = (now - timedelta(days=7)).isoformat()
    return sum(
        1 for pid, h in state.get("queue_history", {}).items()
        for ts in h if ts >= cutoff
    )

def _get_last_week_clears(state: dict, now: datetime) -> int:
    start = (now - timedelta(days=14)).isoformat()
    end = (now - timedelta(days=7)).isoformat()
    return sum(
        1 for pid, h in state.get("queue_history", {}).items()
        for ts in h if start <= ts < end
    )

def _progress_bar(current: int, previous: int) -> str:
    if previous == 0 and current == 0:
        return "No data yet"
    total = max(current, previous, 1)
    filled = int(current / total * 10)
    bar = "█" * filled + "░" * (10 - filled)
    trend = "📈" if current > previous else "📉" if current < previous else "➡️"
    return f"[{bar}] {current} vs {previous} last week {trend}"

def avg_reply_hours(pid: str, state: dict) -> float | None:
    """Estimate average GM reply time from posting gaps."""
    topic_ts = helpers.get_topic_timestamps(state, pid)
    gm_timestamps = []
    for pair in state.get("_config_cache", {}).get("topic_pairs", []):
        if str(pair.get("pbp_topic_ids", [None])[0]) == pid:
            gm_ids = set(str(u) for u in pair.get("gm_user_ids",
                         state.get("_config_cache", {}).get("gm_user_ids", [])))
            for uid, timestamps in topic_ts.items():
                if uid in gm_ids:
                    gm_timestamps.extend(timestamps)
            break
    if len(gm_timestamps) < 3:
        return None
    gm_timestamps.sort()
    gaps = []
    for i in range(1, len(gm_timestamps)):
        gap = (datetime.fromisoformat(gm_timestamps[i]) -
               datetime.fromisoformat(gm_timestamps[i - 1])).total_seconds() / 3600
        if gap < 168:
            gaps.append(gap)
    return sum(gaps) / len(gaps) if gaps else None




def build_queue_stats(config: dict, state: dict) -> str:
    """Build /queuestats output."""
    now = datetime.now(timezone.utc)
    today = get_today_clears(state, now)
    week = get_week_clears(state, now)
    last_week = _get_last_week_clears(state, now)

    from commands.queue_scan import scan_transcripts
    scanned = scan_transcripts(config, state)

    lines = ["📊 GM Queue Stats\n"]
    lines.append(f"Today: {today} cleared")
    lines.append(f"This week: {_progress_bar(week, last_week)}")

    # Age heatmap
    if scanned:
        from commands.queue_analytics import age_heatmap
        lines.append(f"\n🌡️ Avg age: {age_heatmap(scanned)}")

    # Peak hours
    from commands.queue_analytics import peak_hours
    peaks = peak_hours(state)
    lines.append(f"⏰ Peak player hours: {peaks}")

    # Player momentum
    state.setdefault("_config_cache", config)
    from commands.queue_analytics import player_momentum
    momentum = player_momentum(state, config)
    if momentum:
        lines.append(f"\n⚡ Fastest responders:")
        for m in momentum:
            lines.append(f"  {m}")

    # Avg reply time per campaign
    lines.append("")
    for pair in config.get("topic_pairs", []):
        if pair.get("queue_exclude"):
            continue
        pid = str(pair["pbp_topic_ids"][0])
        code = pair.get("code", "")
        label = code if code else pair["name"]
        avg = avg_reply_hours(pid, state)
        if avg is not None:
            avg_str = f"{avg / 24:.1f}d" if avg >= 24 else f"{avg:.0f}h"
            lines.append(f"{label}: avg reply ~{avg_str}")

    # Recent archive
    archive = state.get("queue_archive", [])
    recent = [a for a in archive if a["time"][:10] == now.date().isoformat()]
    if recent:
        lines.append(f"\n📝 Cleared today:")
        for a in recent[-5:]:
            lines.append(f"  {a.get('player', '?')}: {a.get('preview', '')}")

    return "\n".join(lines)
