"""Smart alerts: pace drops and conversation dying."""

from datetime import datetime, timedelta, timezone

import helpers
from helpers import build_topic_maps, fmt_date
import telegram as tg


def check_pace_drop(config: dict, state: dict, *, now: datetime | None = None, maps=None) -> None:
    """Alert when a campaign's weekly posts drop >40% vs the previous week.

    Checks once per week (tied to archive cadence). Sends a gentle nudge
    to the campaign's chat topic so the GM is aware without being pushy.
    """
    group_id = config["group_id"]
    bot_topic = config.get("bot_topic_id")
    now = now or datetime.now(timezone.utc)
    maps = maps or build_topic_maps(config)

    # Only run on archive day (weekly)
    if not helpers.interval_elapsed(state.get("last_pace_drop_check"), 7, now):
        return

    week_ago = now - timedelta(days=7)
    two_weeks_ago = now - timedelta(days=14)

    alerts_sent = False
    for pid, chat_topic_id in maps.to_chat.items():
        if not helpers.feature_enabled(config, pid, "smart_alerts"):
            continue

        name = maps.to_name.get(pid, "Unknown")
        topic_timestamps = helpers.get_topic_timestamps(state, pid)
        gm_ids = helpers.gm_ids_for_campaign(config, pid)

        if not topic_timestamps:
            continue  # pragma: no cover

        pace = helpers.pace_split(topic_timestamps, gm_ids, now)
        this_week = pace["gm_this"] + pace["player_this"]
        last_week = pace["gm_last"] + pace["player_last"]

        # Skip if last week had very few posts (avoid noisy alerts)
        if last_week < 5:
            continue

        if this_week == 0 and last_week > 0:
            drop_pct = 100  # pragma: no cover
        elif last_week > 0:
            drop_pct = ((last_week - this_week) / last_week) * 100
        else:
            continue  # pragma: no cover

        if drop_pct > 40:
            message = (
                f"📉 Pace check for {name}:\n"
                f"\n"
                f"Posts dropped from {last_week} last week to {this_week} "
                f"this week ({drop_pct:.0f}% decrease).\n"
                f"\n"
                f"Just a heads-up — no action needed if the break is "
                f"intentional."
            )
            print(f"Pace drop alert for {name}: {last_week} -> {this_week} ({drop_pct:.0f}%)")
            tg.send_message(group_id, bot_topic or chat_topic_id, message)
            alerts_sent = True

    state["last_pace_drop_check"] = now.isoformat()
    if not alerts_sent:
        print("Pace drop check: no significant drops detected")


def check_conversation_dying(config: dict, state: dict, *, now: datetime | None = None, maps=None) -> None:
    """Warn when ALL participants (including GM) are silent for 48h+.

    Distinct from the 4-hour nudge (which just prompts the next post) — this
    fires once when a campaign crosses the 48h threshold, suggesting the
    campaign may need attention or a deliberate pause.
    """
    group_id = config["group_id"]
    bot_topic = config.get("bot_topic_id")
    now = now or datetime.now(timezone.utc)
    maps = maps or build_topic_maps(config)
    threshold = timedelta(hours=48)

    state.setdefault("dying_alerts_sent", {})

    for pid, chat_topic_id in maps.to_chat.items():
        if not helpers.feature_enabled(config, pid, "smart_alerts"):
            continue  # pragma: no cover
        # Skip paused campaigns — they're intentionally quiet
        if state.get("paused", {}).get(pid):
            continue

        name = maps.to_name.get(pid, "Unknown")
        topic_timestamps = helpers.get_topic_timestamps(state, pid)

        if not topic_timestamps:
            continue  # pragma: no cover

        # Find the most recent post from ANYONE
        latest = None
        for uid, timestamps in topic_timestamps.items():
            for ts in timestamps:
                if latest is None or ts > latest:
                    latest = ts

        if latest is None:
            continue  # pragma: no cover

        try:
            latest_dt = datetime.fromisoformat(latest)
        except (TypeError, ValueError):
            continue

        silence_hours = (now - latest_dt).total_seconds() / 3600.0

        if silence_hours >= threshold.total_seconds() / 3600.0:
            # Only alert once per silence period
            if state["dying_alerts_sent"].get(pid) == "active":
                continue

            days_silent = silence_hours / 24.0
            message = (
                f"💤 {name} has been completely silent for "
                f"{days_silent:.1f} days.\n"
                f"\n"
                f"No posts from anyone — GM or players — since "
                f"{fmt_date(latest_dt)}."
            )
            print(f"Conversation dying alert for {name}: {days_silent:.1f} days silent")
            if tg.send_message(group_id, bot_topic or chat_topic_id, message):
                state["dying_alerts_sent"][pid] = "active"
        else:
            # Reset the flag when activity resumes
            if state["dying_alerts_sent"].get(pid):
                del state["dying_alerts_sent"][pid]
