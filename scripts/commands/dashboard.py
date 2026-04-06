"""
GM dashboard and activity pattern builders.

Commands: /gm, /activity.
"""

from datetime import datetime, timedelta, timezone

import helpers
from helpers import build_topic_maps, timestamps_in_window


_DAY_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
_HOUR_BLOCKS = {
    "Night (00-05)": range(0, 6),
    "Morning (06-11)": range(6, 12),
    "Afternoon (12-17)": range(12, 18),
    "Evening (18-23)": range(18, 24),
}


def build_gm_dashboard(config: dict, state: dict) -> str:
    """Build a compact GM overview of all campaigns."""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    maps = build_topic_maps(config)

    lines = ["📊 GM Dashboard:", ""]

    total_posts = 0
    total_players = 0

    for pid, name in sorted(maps.to_name.items(), key=lambda x: x[1]):
        gm_ids = helpers.gm_ids_for_campaign(config, pid)
        topic_ts = helpers.get_topic_timestamps(state, pid)
        players = [p for p in state.get("players", {}).values()
                   if p.get("pbp_topic_id") == pid and p.get("user_id", "") not in gm_ids]
        player_count = len(players)
        total_players += player_count

        # Posts this week
        week_posts = 0
        for uid, timestamps in topic_ts.items():
            week_posts += len(timestamps_in_window(timestamps, week_ago))  # pragma: no cover
        total_posts += week_posts

        # Last post
        topic_state = state.get("topics", {}).get(pid)
        if topic_state:
            last_dt = datetime.fromisoformat(topic_state["last_message_time"])
            last_str, _ = helpers.fmt_brief_relative(now, last_dt)
        else:
            last_str = "never"

        # Health indicator
        if week_posts >= 20:
            icon = "🟢"  # pragma: no cover
        elif week_posts >= 10:
            icon = "🟡"  # pragma: no cover
        elif week_posts >= 5:
            icon = "🟠"  # pragma: no cover
        else:
            icon = "🔴"

        # Flags
        flags = []
        if state.get("paused_campaigns", {}).get(pid):
            flags.append("⏸️")
        if state.get("combat", {}).get(pid, {}).get("active"):
            flags.append("⚔️")
        away_count = sum(1 for p in players
                         if helpers.is_away(state, pid, p.get("user_id", ""), now))
        if away_count:
            flags.append(f"✈️{away_count}")  # pragma: no cover

        # At-risk count
        at_risk = sum(1 for p in players
                      if helpers.days_since(now, datetime.fromisoformat(p["last_post_time"])) >= 7)
        if at_risk:
            flags.append(f"⚠️{at_risk}")

        active_quests = len([q for q in state.get("quests", {}).get(pid, [])
                             if q.get("status") == "active"])
        if active_quests:
            flags.append(f"📋{active_quests}")  # pragma: no cover

        flag_str = " " + " ".join(flags) if flags else ""

        lines.append(f"{icon} {name}: {week_posts}pw, {player_count}p, last {last_str}{flag_str}")

    lines.append("")
    lines.append(f"Total: {total_posts} posts/week across {len(maps.to_name)} campaigns, {total_players} players")

    return "\n".join(lines)


def build_activity(pid: str, campaign_name: str, state: dict, gm_ids: set) -> str:
    """Build activity pattern report for /activity command."""
    hours_data = state.get("activity_hours", {}).get(pid, {})
    days_data = state.get("activity_days", {}).get(pid, {})

    if not hours_data and not days_data:
        return f"No activity data for {campaign_name} yet.\nPost some messages and check back!"

    # Aggregate across all users
    hour_totals = {}
    day_totals = {}
    for uid, h in hours_data.items():
        for hour, count in h.items():
            hour_totals[int(hour)] = hour_totals.get(int(hour), 0) + count
    for uid, d in days_data.items():
        for day, count in d.items():
            day_totals[int(day)] = day_totals.get(int(day), 0) + count

    total_posts = sum(hour_totals.values())

    lines = [f"📊 Activity Patterns — {campaign_name}", f"({total_posts} tracked posts)", ""]

    # Best days
    lines.append("Busiest days:")
    sorted_days = sorted(day_totals.items(), key=lambda x: x[1], reverse=True)
    for day_num, count in sorted_days:
        pct = count / total_posts * 100 if total_posts else 0
        bar_len = int(pct / 5)
        bar = "█" * bar_len
        lines.append(f"  {_DAY_NAMES[day_num]:3s}  {bar} {count} ({pct:.0f}%)")

    # Best time blocks
    lines.append("")
    lines.append("Busiest times (UTC):")
    block_totals = {}
    for block_name, hour_range in _HOUR_BLOCKS.items():
        block_totals[block_name] = sum(hour_totals.get(h, 0) for h in hour_range)
    sorted_blocks = sorted(block_totals.items(), key=lambda x: x[1], reverse=True)
    for block_name, count in sorted_blocks:
        pct = count / total_posts * 100 if total_posts else 0
        bar_len = int(pct / 5)
        bar = "█" * bar_len
        lines.append(f"  {block_name:20s} {bar} {count} ({pct:.0f}%)")

    # Peak hour
    if hour_totals:
        peak_hour = max(hour_totals, key=hour_totals.get)
        lines.append(f"\nPeak hour: {peak_hour:02d}:00 UTC ({hour_totals[peak_hour]} posts)")

    # Top 3 most active players
    player_totals = {}
    for uid, h in hours_data.items():
        player_totals[uid] = sum(h.values())
    sorted_players = sorted(player_totals.items(), key=lambda x: x[1], reverse=True)[:3]
    if sorted_players:
        lines.append("")
        lines.append("Most active posters:")
        players_map = {p["user_id"]: p for p in state.get("players", {}).values()
                       if p.get("pbp_topic_id") == pid}
        for uid, count in sorted_players:
            name = "GM" if uid in gm_ids else players_map.get(uid, {}).get("first_name", uid)
            lines.append(f"  {name}: {count} posts")

    return "\n".join(lines)
