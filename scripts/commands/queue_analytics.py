"""Queue analytics: peak hours, age heatmap, player momentum."""

from datetime import datetime, timezone

import helpers


def peak_hours(state: dict) -> str:
    """Find when players are most active across all campaigns."""
    hour_totals = {}
    for pid, users in state.get("activity_hours", {}).items():
        for uid, hours in users.items():
            for h, count in hours.items():
                hour_totals[int(h)] = hour_totals.get(int(h), 0) + count
    if not hour_totals:
        return "No data yet"
    top = sorted(hour_totals.items(), key=lambda x: -x[1])[:3]
    return ", ".join(f"{h:02d}:00 ({c})" for h, c in top)


def age_heatmap(scanned: dict) -> str:
    """Average age per campaign, sorted worst first."""
    now = datetime.now(timezone.utc)
    ages = []
    for pid, data in scanned.items():
        entries = data["entries"]
        if not entries:
            continue
        total_h = sum(
            helpers.hours_since(now, datetime.strptime(
                e["time"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc))
            for e in entries if e.get("time")
        )
        avg_h = total_h / len(entries)
        code = data.get("code", "")
        label = code if code else data["campaign"]
        days = int(avg_h // 24)
        h = int(avg_h % 24)
        ages.append((label, avg_h, f"{days}d {h}h"))
    ages.sort(key=lambda x: -x[1])
    return "  ".join(f"{a[0]}:{a[2]}" for a in ages)


def player_momentum(state: dict, config: dict) -> list[str]:
    """Find fastest-responding players per campaign."""
    lines = []
    for pair in config.get("topic_pairs", []):
        pid = str(pair["pbp_topic_ids"][0])
        if pair.get("queue_exclude"):
            continue
        code = pair.get("code", "")
        gm_ids = helpers.gm_ids_for_campaign(config, pid)
        topic_ts = helpers.get_topic_timestamps(state, pid)
        all_posts = []
        for uid, timestamps in topic_ts.items():
            for ts in timestamps:
                all_posts.append((ts, uid, uid in gm_ids))
        all_posts.sort()
        player_gaps = {}
        last_gm_time = None
        for ts, uid, is_gm in all_posts:
            if is_gm:
                last_gm_time = ts
            elif last_gm_time:
                gap = (datetime.fromisoformat(ts) -
                       datetime.fromisoformat(last_gm_time)).total_seconds() / 3600
                if gap < 168:
                    p = helpers.get_player(state, pid, uid)
                    name = p.get("first_name", uid) if p else uid
                    player_gaps.setdefault(name, []).append(gap)
        if player_gaps:
            fastest = min(player_gaps.items(),
                          key=lambda x: sum(x[1]) / len(x[1]))
            avg = sum(fastest[1]) / len(fastest[1])
            avg_str = f"{avg:.0f}h" if avg < 24 else f"{avg/24:.1f}d"
            label = code if code else pair["name"]
            lines.append(f"{label}: {fastest[0]} (~{avg_str})")
    return lines
