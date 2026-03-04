"""Campaign and player inactivity alerts."""

from datetime import datetime, timezone

import helpers
from helpers import build_topic_maps, fmt_date
import telegram as tg


def check_and_alert(config: dict, state: dict, *, now: datetime | None = None, maps=None) -> None:
    """Send alerts to campaigns inactive beyond alert_after_hours."""
    group_id = config["group_id"]
    alert_hours = config.get("alert_after_hours", 4)
    now = now or datetime.now(timezone.utc)

    maps = maps or build_topic_maps(config)

    for pid, chat_topic_id in maps.to_chat.items():
        name = maps.to_name[pid]

        if not helpers.feature_enabled(config, pid, "alerts"):
            continue

        if pid in state.get("paused_campaigns", {}):
            continue

        if pid not in state.get("topics", {}):
            continue
            print(f"No messages tracked yet for {name}, skipping")
            continue

        topic_state = state["topics"][pid]
        last_time = datetime.fromisoformat(topic_state["last_message_time"])
        elapsed_hours = helpers.hours_since(now, last_time)

        if elapsed_hours < alert_hours:
            continue

        # Don't re-alert within alert_hours
        last_alert_str = state["last_alerts"].get(pid)
        if last_alert_str:
            since_last = helpers.hours_since(now, datetime.fromisoformat(last_alert_str))
            if since_last < alert_hours:
                print(f"{name}: Already alerted {since_last:.1f}h ago, skipping")
                continue

        hours_int = int(elapsed_hours)
        days = hours_int // 24
        remaining_hours = hours_int % 24
        last_user = topic_state.get("last_user", "someone")
        last_user_id = topic_state.get("last_user_id", "")

        time_str = f"{days}d {remaining_hours}h" if days > 0 else f"{hours_int}h"

        # Look up total message count for last poster
        count = state.get("message_counts", {}).get(pid, {}).get(last_user_id, 0)
        count_str = f" ({count} total posts)" if count > 0 else ""

        last_date = fmt_date(last_time)

        message = (
            f"No new posts in {name} PBP for {time_str}.\n"
            f"Last post was from {last_user}{count_str} on {last_date}."
        )

        print(f"Sending alert for {name}: {time_str} inactive")
        if tg.send_message(group_id, chat_topic_id, message):
            state["last_alerts"][pid] = now.isoformat()

_INACTIVITY_TEMPLATES = {
    1: "{mention} hasn't posted in {campaign} PBP for {days} days (last: {date}). Everything okay?",
    2: "{mention} still no post in {campaign} PBP. It's been {days} days now (last: {date}).",
    3: "{mention} it's been {days} days without a post in {campaign} PBP (last: {date}). 1 week until auto-removal from the campaign.",
}


def check_player_activity(config: dict, state: dict, *, now: datetime | None = None, maps=None) -> None:
    """Warn inactive players at 1/2/3 weeks, remove at 4 weeks."""
    group_id = config["group_id"]
    now = now or datetime.now(timezone.utc)

    # Build lookup: canonical pbp_topic_id -> chat_topic_id
    maps = maps or build_topic_maps(config)

    players_to_remove = []

    for player_key, player in state["players"].items():
        pbp_topic_id = player["pbp_topic_id"]
        chat_topic_id = maps.to_chat.get(pbp_topic_id)
        if not chat_topic_id:
            continue
        if not helpers.feature_enabled(config, pbp_topic_id, "warnings"):
            continue
        if pbp_topic_id in state.get("paused_campaigns", {}):
            continue
        # Skip players who are marked as away
        user_id = player.get("user_id", "")
        if helpers.is_away(state, pbp_topic_id, user_id, now):
            continue
        # Skip GMs (per-campaign or global)
        gm_ids = helpers.gm_ids_for_campaign(config, pbp_topic_id)
        if user_id in gm_ids:
            continue

        last_post = datetime.fromisoformat(player["last_post_time"])
        elapsed_days = helpers.days_since(now, last_post)
        current_week = int(elapsed_days / 7)
        last_warned = player.get("last_warned_week", 0)

        first_name = player["first_name"]
        campaign = player["campaign_name"]
        mention = helpers.player_mention(player)
        days_inactive = int(elapsed_days)
        last_date = fmt_date(last_post)

        # 4+ weeks: remove
        if current_week >= helpers.PLAYER_REMOVE_WEEKS:
            if last_warned < helpers.PLAYER_REMOVE_WEEKS:
                message = (
                    f"{mention} has not posted in {campaign} PBP for "
                    f"{days_inactive} days (last: {last_date}). They are no longer tracked "
                    f"as an active player in this campaign."
                )
                print(f"Removing {first_name} from {campaign} ({days_inactive}d)")
                tg.send_message(group_id, chat_topic_id, message)
                players_to_remove.append(player_key)
            continue

        # 1, 2, 3 week warnings
        for week_mark in helpers.PLAYER_WARN_WEEKS:
            if current_week >= week_mark and last_warned < week_mark:
                template = _INACTIVITY_TEMPLATES.get(week_mark, _INACTIVITY_TEMPLATES[3])
                message = template.format(
                    mention=mention, campaign=campaign,
                    days=days_inactive, date=last_date,
                )
                print(f"Warning {first_name} in {campaign}: week {week_mark}")
                if tg.send_message(group_id, chat_topic_id, message):
                    player["last_warned_week"] = week_mark
                break  # One warning per player per run

    # Move removed players out
    for key in players_to_remove:
        removed = state["players"].pop(key)
        state["removed_players"][key] = {
            "removed_at": now.isoformat(),
            "first_name": removed["first_name"],
            "username": removed.get("username", ""),
            "campaign_name": removed["campaign_name"],
        }
