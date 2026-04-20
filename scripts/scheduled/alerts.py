"""Campaign and player inactivity alerts."""

from datetime import datetime, timezone

import helpers
from helpers import build_topic_maps, fmt_date
import telegram as tg


def _gm_last_post(config: dict, state: dict, pid: str) -> datetime | None:
    """Return the most recent GM post time for a campaign, or None."""
    gm_ids = helpers.gm_ids_for_campaign(config, pid)
    topic_ts = helpers.get_topic_timestamps(state, pid)
    gm_last = None
    for gm_id in gm_ids:
        gm_stamps = topic_ts.get(gm_id, [])
        if gm_stamps:
            gm_dt = datetime.fromisoformat(gm_stamps[-1])  # pragma: no cover
            if gm_last is None or gm_dt > gm_last:  # pragma: no cover
                gm_last = gm_dt  # pragma: no cover
    return gm_last


def _gm_note(config: dict, state: dict, pid: str, now: datetime) -> str:
    """Return a GM inactivity note if the GM isn't the last poster, else ''."""
    topic_state = state.get("topics", {}).get(pid, {})
    last_user_id = topic_state.get("last_user_id", "")
    gm_ids = helpers.gm_ids_for_campaign(config, pid)
    if last_user_id in gm_ids:
        return ""  # pragma: no cover
    gm_last = _gm_last_post(config, state, pid)
    if not gm_last:
        return ""
    gm_elapsed = helpers.hours_since(now, gm_last)  # pragma: no cover
    gm_days = int(gm_elapsed) // 24  # pragma: no cover
    gm_hours = int(gm_elapsed) % 24  # pragma: no cover
    gm_time = f"{gm_days}d {gm_hours}h" if gm_days > 0 else f"{gm_hours}h"  # pragma: no cover
    return f"\n\nGM hasn't posted in {gm_time}."  # pragma: no cover


def check_and_alert(config: dict, state: dict, *, now: datetime | None = None, maps=None) -> None:
    """Send alerts to campaigns inactive beyond alert_after_hours."""
    group_id = config["group_id"]
    bot_topic = config.get("bot_topic_id")
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

        topic_state = state["topics"][pid]
        last_time = datetime.fromisoformat(topic_state["last_message_time"])
        elapsed_hours = helpers.hours_since(now, last_time)

        if elapsed_hours < alert_hours:
            continue

        # Don't re-alert within 24 hours (once per day max)
        last_alert_str = state["last_alerts"].get(pid)
        if last_alert_str:
            since_last = helpers.hours_since(now, datetime.fromisoformat(last_alert_str))
            if since_last < 24:
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
            f"━━━━━━━━━━━━━━━━\n"
            f"No new posts in {name} PBP for {time_str}.\n"
            f"Last post was from {last_user}{count_str} on {last_date}."
        )
        message += _gm_note(config, state, pid, now)

        print(f"Sending alert for {name}: {time_str} inactive")
        if tg.send_message(group_id, bot_topic or chat_topic_id, message):
            state["last_alerts"][pid] = now.isoformat()

_INACTIVITY_TEMPLATES = {
    1: "{mention} hasn't posted in {campaign} PBP for {days} days (last: {date}). Everything okay?",
    2: "{mention} still no post in {campaign} PBP. It's been {days} days now (last: {date}).",
    3: "{mention} it's been {days} days without a post in {campaign} PBP (last: {date}). 1 week until auto-removal from the campaign.",
}


def check_player_activity(config: dict, state: dict, *, now: datetime | None = None, maps=None) -> None:
    """Warn inactive players at 1/2/3 weeks, remove at 4 weeks."""
    group_id = config["group_id"]
    bot_topic = config.get("bot_topic_id")
    now = now or datetime.now(timezone.utc)

    # Build lookup: canonical pbp_topic_id -> chat_topic_id
    maps = maps or build_topic_maps(config)

    # Cache GM last-post per campaign to avoid repeated lookups
    _gm_bottleneck = {}

    players_to_remove = []

    for player_key, player in state["players"].items():
        pbp_topic_id = player["pbp_topic_id"]
        chat_topic_id = maps.to_chat.get(pbp_topic_id)
        if not chat_topic_id:
            continue  # pragma: no cover
        if not helpers.feature_enabled(config, pbp_topic_id, "warnings"):
            continue
        if pbp_topic_id in state.get("paused_campaigns", {}):
            continue
        # Skip players who are marked as away
        user_id = player.get("user_id", "")
        if helpers.is_away(state, pbp_topic_id, user_id, now):
            continue
        # Cache GM bottleneck status (3+ days inactive)
        if pbp_topic_id not in _gm_bottleneck:
            gm_last = _gm_last_post(config, state, pbp_topic_id)
            _gm_bottleneck[pbp_topic_id] = (
                gm_last is not None and helpers.days_since(now, gm_last) >= 3
            )

        last_post = datetime.fromisoformat(player["last_post_time"])
        elapsed_days = helpers.days_since(now, last_post)
        current_week = int(elapsed_days / 7)
        last_warned = player.get("last_warned_week", 0)

        first_name = player["first_name"]
        campaign = player["campaign_name"]
        mention = helpers.player_mention(player)
        days_inactive = int(elapsed_days)
        last_date = fmt_date(last_post)

        # 4+ weeks: remove (ALWAYS fires, even when GM is bottleneck)
        # Permanent players are never removed — skip the removal block entirely
        if player.get("permanent"):
            pass  # fall through to warnings below (week 3 skipped separately)
        elif current_week >= helpers.PLAYER_REMOVE_WEEKS:
            if last_warned < helpers.PLAYER_REMOVE_WEEKS:
                message = (
                    f"{mention} has not posted in {campaign} PBP for "
                    f"{days_inactive} days (last: {last_date}). They are no longer tracked "
                    f"as an active player in this campaign."
                )
                message += _gm_note(config, state, pbp_topic_id, now)
                print(f"Removing {first_name} from {campaign} ({days_inactive}d)")
                tg.send_message(group_id, bot_topic or chat_topic_id, message)
                players_to_remove.append(player_key)
            continue

        # 1, 2, 3 week warnings (suppressed when GM is the bottleneck)
        if _gm_bottleneck[pbp_topic_id]:
            continue  # pragma: no cover
        for week_mark in helpers.PLAYER_WARN_WEEKS:
            # Skip week-3 warning for permanent players (it mentions auto-removal)
            if week_mark == 3 and player.get("permanent"):
                continue
            if current_week >= week_mark and last_warned < week_mark:
                template = _INACTIVITY_TEMPLATES.get(week_mark, _INACTIVITY_TEMPLATES[3])
                message = template.format(
                    mention=mention, campaign=campaign,
                    days=days_inactive, date=last_date,
                )
                message += _gm_note(config, state, pbp_topic_id, now)
                print(f"Warning {first_name} in {campaign}: week {week_mark}")
                if tg.send_message(group_id, bot_topic or chat_topic_id, message):
                    player["last_warned_week"] = week_mark
                break  # One warning per player per run

    # Move removed players out
    for key in players_to_remove:
        removed = state["players"].pop(key)
        __import__("players.history", fromlist=["on_leave"]).on_leave(
            str(removed.get("pbp_topic_id", "")), str(removed.get("user_id", "")),
            removed["first_name"], removed.get("username", ""), state, config)
        state["removed_players"][key] = {
            "removed_at": now.isoformat(),
            "first_name": removed["first_name"],
            "username": removed.get("username", ""),
            "campaign_name": removed["campaign_name"],
        }
