"""Roster and pace reports."""

from datetime import datetime, timedelta, timezone

import helpers
from helpers import build_topic_maps, fmt_date, posts_str
from commands.campaign import roster_user_stats, roster_block
import telegram as tg


def post_roster_summary(config: dict, state: dict, *, now: datetime | None = None, maps=None) -> None:
    """Post a summary of all tracked players per campaign to CHAT topics."""
    group_id = config["group_id"]
    bot_topic = config.get("bot_topic_id")
    now = now or datetime.now(timezone.utc)

    maps = maps or build_topic_maps(config)
    campaigns = helpers.players_by_campaign(state)

    for pid, chat_topic_id in maps.to_chat.items():
        if not helpers.feature_enabled(config, pid, "roster"):
            continue
        if not helpers.interval_elapsed(state["last_roster"].get(pid), helpers.ROSTER_INTERVAL_DAYS, now):
            continue

        gm_ids = helpers.gm_ids_for_campaign(config, pid)

        name = maps.to_name.get(pid, "Unknown")
        players = campaigns.get(pid, [])
        counts = state.get("message_counts", {}).get(pid, {})
        topic_timestamps = helpers.get_topic_timestamps(state, pid)

        if not players and not counts:
            continue

        lines = []
        characters = helpers.get_characters(config, pid)

        from commands.player_registry import get_or_assign_id, format_id

        active_player_count = 0
        for player in sorted(players, key=lambda p: counts.get(p["user_id"], 0), reverse=True):
            uid = player["user_id"]
            if uid in gm_ids:
                continue
            raw_ts = topic_timestamps.get(uid, [])
            if not raw_ts:
                continue
            active_player_count += 1
            full = helpers.player_full_name(player)
            char_name = characters.get(uid)
            label = f"{full} ({char_name})" if char_name else full
            pid_num = get_or_assign_id(pid, uid, full, False, state)
            label = f"{format_id(pid_num)}: {label}"
            stats = roster_user_stats(raw_ts, counts.get(uid, 0), now)
            lines.append(roster_block(label, player.get("username", ""), stats))

        # Add GM stats if present
        for gm_id in gm_ids:
            gm_count = counts.get(gm_id, 0)
            raw_ts = topic_timestamps.get(gm_id, [])
            if gm_count > 0 and raw_ts:
                gm_player = next((p for p in players if p.get("user_id") == gm_id), None)
                gm_name = helpers.player_full_name(gm_player) if gm_player else "GM"
                get_or_assign_id(pid, gm_id, gm_name, True, state)
                stats = roster_user_stats(raw_ts, gm_count, now)
                lines.insert(0, roster_block(f"{format_id(0)}: GM", "", stats))

        if not lines:
            continue

        player_count = active_player_count
        footer = f"\n\n———\n\n📋 {name} Party Size\n"
        footer += f"Party size: {player_count}/{helpers.REQUIRED_PLAYERS}."
        if player_count < helpers.REQUIRED_PLAYERS:
            needed = helpers.REQUIRED_PLAYERS - player_count
            s = "s" if needed != 1 else ""
            footer += f"\n{name} needs {needed} more player{s}!"

        message = f"━━━━━━━━━━━━━━━━\nParty roster for {name}:\n\n" + "\n\n".join(lines) + footer

        print(f"Posting roster for {name}")
        if tg.send_message(group_id, bot_topic or chat_topic_id, message):
            state["last_roster"][pid] = now.isoformat()


def post_pace_report(config: dict, state: dict, *, now: datetime | None = None, maps=None) -> None:
    """Post weekly pace comparison: posts/day this week vs last week, split GM/players."""
    group_id = config["group_id"]
    bot_topic = config.get("bot_topic_id")
    now = now or datetime.now(timezone.utc)

    maps = maps or build_topic_maps(config)

    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    for pid, chat_topic_id in maps.to_chat.items():
        if not helpers.feature_enabled(config, pid, "pace"):
            continue
        if not helpers.interval_elapsed(state["last_pace"].get(pid), helpers.PACE_INTERVAL_DAYS, now):
            continue

        name = maps.to_name.get(pid, "Unknown")
        topic_timestamps = helpers.get_topic_timestamps(state, pid)
        gm_ids = helpers.gm_ids_for_campaign(config, pid)

        if not topic_timestamps:
            continue

        pace = helpers.pace_split(topic_timestamps, gm_ids, now)
        gm_this = pace["gm_this"]
        gm_last = pace["gm_last"]
        player_this = pace["player_this"]
        player_last = pace["player_last"]

        this_week = gm_this + player_this
        last_week = gm_last + player_last
        this_avg = this_week / 7.0
        last_avg = last_week / 7.0

        # Determine trend
        if last_avg == 0 and this_avg == 0:
            continue  # No data
        icon = helpers.trend_icon(int(this_avg * 100), int(last_avg * 100))

        this_week_start = fmt_date(week_ago)
        this_week_end = fmt_date(now)
        last_week_start = fmt_date(two_weeks_ago)
        last_week_end = fmt_date(week_ago)

        this_week_num = f"W{now.isocalendar()[1]:02d}"
        last_week_num = f"W{week_ago.isocalendar()[1]:02d}"

        message = (
            f"{icon} Weekly pace for {name}:\n"
            f"\n"
            f"This week {this_week_num} ({this_week_start} to {this_week_end}):\n"
            f"  GM: {gm_this} posts ({gm_this / 7.0:.1f}/day)\n"
            f"  Players: {player_this} posts ({player_this / 7.0:.1f}/day)\n"
            f"  Total: {this_week} posts ({this_avg:.1f}/day)\n"
            f"\n"
            f"Last week {last_week_num} ({last_week_start} to {last_week_end}):\n"
            f"  GM: {gm_last} posts ({gm_last / 7.0:.1f}/day)\n"
            f"  Players: {player_last} posts ({player_last / 7.0:.1f}/day)\n"
            f"  Total: {last_week} posts ({last_avg:.1f}/day)\n"
            f"\n"
            f"Trend: {icon}"
        )

        print(f"Pace report for {name}: {this_week} vs {last_week} ({icon})")
        if tg.send_message(group_id, bot_topic or chat_topic_id, message):
            state["last_pace"][pid] = now.isoformat()
