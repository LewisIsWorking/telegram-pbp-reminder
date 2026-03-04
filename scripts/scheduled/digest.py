"""Weekly digest newsletter."""

from datetime import datetime, timedelta, timezone

import helpers
from helpers import (
    build_topic_maps, fmt_date, posts_str, timestamps_in_window,
)
import telegram as tg


def _build_weekly_digest(config: dict, state: dict, now: datetime) -> str:
    """Build a compact one-line-per-campaign weekly digest."""
    maps = build_topic_maps(config)
    week_ago = now - timedelta(days=7)

    campaign_lines = []
    all_campaigns = helpers.players_by_campaign(state)

    for pid, name in maps.to_name.items():
        topic_ts = helpers.get_topic_timestamps(state, pid)
        gm_ids = helpers.gm_ids_for_campaign(config, pid)
        pace = helpers.pace_split(topic_ts, gm_ids, now)
        total = pace["gm_this"] + pace["player_this"]
        total_last = pace["gm_last"] + pace["player_last"]
        trend = helpers.trend_icon(total, total_last)
        health = helpers.health_icon(total)

        # Top contributor this week
        player_week_counts = {}
        for uid, timestamps in topic_ts.items():
            if uid in gm_ids:
                continue
            count = len(timestamps_in_window(timestamps, week_ago))
            if count > 0:
                player = helpers.get_player(state, pid, uid)
                name_str = player.get("first_name", "?") if player else "?"
                player_week_counts[name_str] = count

        top_name = ""
        if player_week_counts:
            top_name = max(player_week_counts, key=player_week_counts.get)

        # Party size (excluding GMs)
        players = all_campaigns.get(pid, [])
        party = f"{len([p for p in players if p['user_id'] not in gm_ids])}/{helpers.REQUIRED_PLAYERS}"

        # Combat?
        combat = state.get("combat", {}).get(pid, {})
        combat_str = " ⚔️" if combat.get("active") else ""

        line = f"{health} {name}: {posts_str(total)} {trend} ({party}){combat_str}"
        if top_name:
            line += f" — MVP: {top_name}"

        campaign_lines.append((total, line))

    # Sort by post count descending
    campaign_lines.sort(key=lambda x: x[0], reverse=True)

    date_str = fmt_date(now)
    header = f"📰 Weekly Digest — {date_str}"
    body = "\n".join(line for _, line in campaign_lines)

    legend = "\n\n🟢 20+ posts | 🟡 10-19 | 🟠 5-9 | 🔴 <5"

    return f"{header}\n\n{body}{legend}"


def post_weekly_digest(config: dict, state: dict, *, now: datetime | None = None, **_kw) -> None:
    """Post a compact weekly digest to the leaderboard topic."""
    group_id = config["group_id"]
    leaderboard_topic = config.get("leaderboard_topic_id")
    if not leaderboard_topic:
        return

    now = now or datetime.now(timezone.utc)

    # Weekly interval (separate from leaderboard)
    if not helpers.interval_elapsed(state.get("last_weekly_digest"), 7, now):
        return

    message = _build_weekly_digest(config, state, now)

    print(f"Posting weekly digest")
    if tg.send_message(group_id, leaderboard_topic, message):
        state["last_weekly_digest"] = now.isoformat()
