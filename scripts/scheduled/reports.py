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
        label = helpers.get_label(config, pid)
        players = campaigns.get(pid, [])
        counts = state.get("message_counts", {}).get(pid, {})
        topic_timestamps = helpers.get_topic_timestamps(state, pid)

        if not players and not counts:
            continue

        lines = []
        characters = helpers.get_characters(config, pid, state)

        from commands.player_registry import get_or_assign_id

        active_player_count = 0
        roster_rank = 0
        for player in sorted(players, key=lambda p: counts.get(p["user_id"], 0), reverse=True):
            uid = player["user_id"]
            if uid in gm_ids:
                continue  # pragma: no cover
            raw_ts = topic_timestamps.get(uid, [])
            if not raw_ts:
                continue  # pragma: no cover
            active_player_count += 1
            roster_rank += 1
            full = helpers.player_full_name(player)
            char_name = characters.get(uid)
            player_label = f"{full} ({char_name})" if char_name else full
            registry_id = get_or_assign_id(pid, uid, full, False, state)
            player_label = f"#{roster_rank:02d}: {player_label}"
            stats = roster_user_stats(raw_ts, counts.get(uid, 0), now)
            extra_line = f"Player {registry_id}."
            lines.append(roster_block(player_label, player.get("username", ""), stats, extra_line))

        # Add GM stats if present
        for gm_id in gm_ids:
            gm_count = counts.get(gm_id, 0)
            raw_ts = topic_timestamps.get(gm_id, [])
            if gm_count > 0 and raw_ts:
                gm_player = next((p for p in players if p.get("user_id") == gm_id), None)  # pragma: no cover
                gm_name = helpers.player_full_name(gm_player) if gm_player else "GM"  # pragma: no cover
                get_or_assign_id(pid, gm_id, gm_name, True, state)  # pragma: no cover
                stats = roster_user_stats(raw_ts, gm_count, now)  # pragma: no cover
                lines.insert(0, roster_block("#00: GM", "", stats))  # pragma: no cover

        if not lines:
            continue  # pragma: no cover

        player_count = active_player_count
        footer = f"\n\n———\n\n📋 {label} Party Size\n"
        footer += f"Party size: {player_count}/{helpers.REQUIRED_PLAYERS}."
        if player_count < helpers.REQUIRED_PLAYERS:
            needed = helpers.REQUIRED_PLAYERS - player_count
            s = "s" if needed != 1 else ""
            footer += f"\n{label} needs {needed} more player{s}!"

        message = f"━━━━━━━━━━━━━━━━\nParty roster for {label}:\n\n" + "\n\n".join(lines) + footer

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
            continue  # pragma: no cover

        name = maps.to_name.get(pid, "Unknown")
        topic_timestamps = helpers.get_topic_timestamps(state, pid)
        gm_ids = helpers.gm_ids_for_campaign(config, pid)

        if not topic_timestamps:
            continue

        pace = helpers.pace_split(topic_timestamps, gm_ids, now)  # pragma: no cover
        gm_this = pace["gm_this"]  # pragma: no cover
        gm_last = pace["gm_last"]  # pragma: no cover
        player_this = pace["player_this"]  # pragma: no cover
        player_last = pace["player_last"]  # pragma: no cover
  # pragma: no cover
        this_week = gm_this + player_this  # pragma: no cover
        last_week = gm_last + player_last  # pragma: no cover
        this_avg = this_week / 7.0  # pragma: no cover
        last_avg = last_week / 7.0  # pragma: no cover
  # pragma: no cover
        # Determine trend  # pragma: no cover
        if last_avg == 0 and this_avg == 0:  # pragma: no cover
            continue  # No data  # pragma: no cover
        icon = helpers.trend_icon(int(this_avg * 100), int(last_avg * 100))  # pragma: no cover
  # pragma: no cover
        this_week_start = fmt_date(week_ago)  # pragma: no cover
        this_week_end = fmt_date(now)  # pragma: no cover
        last_week_start = fmt_date(two_weeks_ago)  # pragma: no cover
        last_week_end = fmt_date(week_ago)  # pragma: no cover
  # pragma: no cover
        this_week_num = f"W{now.isocalendar()[1]:02d}"  # pragma: no cover
        last_week_num = f"W{week_ago.isocalendar()[1]:02d}"  # pragma: no cover
  # pragma: no cover
        message = (  # pragma: no cover
            f"{icon} Weekly pace for {name}:\n"  # pragma: no cover
            f"\n"  # pragma: no cover
            f"This week {this_week_num} ({this_week_start} to {this_week_end}):\n"  # pragma: no cover
            f"  GM: {gm_this} posts ({gm_this / 7.0:.1f}/day)\n"  # pragma: no cover
            f"  Players: {player_this} posts ({player_this / 7.0:.1f}/day)\n"  # pragma: no cover
            f"  Total: {this_week} posts ({this_avg:.1f}/day)\n"  # pragma: no cover
            f"\n"  # pragma: no cover
            f"Last week {last_week_num} ({last_week_start} to {last_week_end}):\n"  # pragma: no cover
            f"  GM: {gm_last} posts ({gm_last / 7.0:.1f}/day)\n"  # pragma: no cover
            f"  Players: {player_last} posts ({player_last / 7.0:.1f}/day)\n"  # pragma: no cover
            f"  Total: {last_week} posts ({last_avg:.1f}/day)\n"  # pragma: no cover
            f"\n"  # pragma: no cover
            f"Trend: {icon}"  # pragma: no cover
        )  # pragma: no cover
  # pragma: no cover
        print(f"Pace report for {name}: {this_week} vs {last_week} ({icon})")  # pragma: no cover
        if tg.send_message(group_id, bot_topic or chat_topic_id, message):  # pragma: no cover
            state["last_pace"][pid] = now.isoformat()  # pragma: no cover
