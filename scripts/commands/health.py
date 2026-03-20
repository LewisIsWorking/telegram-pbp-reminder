"""
Campaign health dashboard.

Color-coded overview of all campaigns at a glance.
Green = healthy, yellow = slowing, red = stalled.
"""

from datetime import datetime, timezone, timedelta

import helpers


def build_health(config: dict, state: dict) -> str:
    """Build /health output: color-coded overview of all campaigns."""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    lines = ["🏥 Campaign Health Dashboard\n"]

    for pair in config.get("topic_pairs", []):
        pid = str(pair["pbp_topic_ids"][0])
        name = pair["name"]
        code = pair.get("code", "")
        label = f"{code}: {name}" if code else name

        # Last post
        topic = state.get("topics", {}).get(pid, {})
        last_time = topic.get("last_message_time")
        if not last_time:
            lines.append(f"⚫ {label} — no data")
            continue

        last_dt = datetime.fromisoformat(last_time)
        hours_since = helpers.hours_since(now, last_dt)
        days_since = hours_since / 24

        # Count this week's posts
        topic_ts = helpers.get_topic_timestamps(state, pid)
        week_posts = 0
        for uid, timestamps in topic_ts.items():
            for ts in timestamps:
                try:
                    if datetime.fromisoformat(ts) > week_ago:
                        week_posts += 1
                except (ValueError, TypeError):
                    pass

        # Count active players
        player_count = sum(
            1 for key, p in state.get("players", {}).items()
            if p.get("pbp_topic_id") == pid
        )

        # Queue count
        from commands.queue_scan import scan_transcripts
        scanned = scan_transcripts(config, state)
        queue_count = len(scanned.get(pid, {}).get("entries", []))

        # Session count
        session = state.get("session_counts", {}).get(pid, 0)
        session_str = f" S{session}" if session else ""

        # Health color
        if days_since < 1 and week_posts >= 10:
            icon = "🟢"  # healthy
        elif days_since < 2 and week_posts >= 5:
            icon = "🟢"
        elif days_since < 3 and week_posts >= 3:
            icon = "🟡"  # slowing
        elif days_since < 5:
            icon = "🟠"  # concerning
        else:
            icon = "🔴"  # stalled

        # Time since last post
        if days_since >= 1:
            age = f"{int(days_since)}d"
        else:
            age = f"{int(hours_since)}h"

        # Queue indicator
        q_str = f" 📋{queue_count}" if queue_count else ""

        lines.append(
            f"{icon} {label}{session_str} — "
            f"{week_posts}/wk, {player_count}p, last {age}{q_str}"
        )

    return "\n".join(lines)
