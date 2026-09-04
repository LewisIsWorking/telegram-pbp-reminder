"""Streak and anniversary milestones."""

from datetime import datetime, timezone

import helpers
from helpers import build_topic_maps, fmt_date
import telegram as tg


_STREAK_MILESTONES = [7, 14, 30, 60, 90]

_STREAK_MESSAGES = {
    7: "🔥 {name} is on a 7-day posting streak in {campaign}! One full week of consistency.",
    14: "🔥🔥 {name} has hit a 14-day streak in {campaign}! Two solid weeks.",
    30: "🔥🔥🔥 {name} has reached a 30-day streak in {campaign}! A full month of daily posts. Legendary.",
    60: "🌟 {name} has been posting daily for 60 days straight in {campaign}. Absolute dedication.",
    90: "👑 {name} has hit 90 days in {campaign}. Three months without missing a day. Unbelievable.",
}


def check_streak_milestones(config: dict, state: dict, *, now: datetime | None = None, maps=None, **_kw) -> None:
    """Celebrate when a player crosses a streak milestone (7, 14, 30, 60, 90 days)."""
    group_id = config["group_id"]
    bot_topic = config.get("bot_topic_id")
    now = now or datetime.now(timezone.utc)

    maps = maps or build_topic_maps(config)
    celebrated = state.setdefault("celebrated_streaks", {})

    for pid, chat_topic_id in maps.to_chat.items():
        name = maps.to_name.get(pid, "Unknown")
        topic_ts = helpers.get_topic_timestamps(state, pid)
        gm_ids = helpers.gm_ids_for_campaign(config, pid)

        for uid, raw_ts in topic_ts.items():
            if uid in gm_ids:
                continue  # pragma: no cover

            streak = helpers.calc_streak(raw_ts, now)
            if streak < _STREAK_MILESTONES[0]:
                continue  # pragma: no cover

            # Find the highest milestone crossed
            milestone = 0
            for m in _STREAK_MILESTONES:
                if streak >= m:
                    milestone = m

            key = f"{pid}:{uid}"
            last_celebrated = celebrated.get(key, 0)

            if milestone <= last_celebrated:
                continue

            player = helpers.get_player(state, pid, uid)
            player_name = player.get("first_name", "Someone") if player else "Someone"

            message = _STREAK_MESSAGES.get(milestone, "🔥 {name} is on a {streak}-day streak in {campaign}!")
            message = message.format(name=player_name, campaign=name, streak=streak)

            print(f"Streak milestone: {player_name} hit {milestone}d in {name}")
            if tg.send_message(group_id, bot_topic or chat_topic_id, message):
                celebrated[key] = milestone


def _next_anniversary(config: dict, today) -> str | None:
    """Find the next upcoming campaign anniversary after today."""
    upcoming = []
    for pair in config["topic_pairs"]:
        created_str = pair.get("created")
        if not created_str:
            continue  # pragma: no cover
        created = datetime.strptime(created_str, "%Y-%m-%d").date()
        name = pair["name"]

        # This year's anniversary
        try:
            ann_this_year = created.replace(year=today.year)
        except ValueError:  # pragma: no cover
            continue  # Feb 29 edge case  # pragma: no cover

        if ann_this_year > today:
            years = today.year - created.year  # pragma: no cover
            if years >= 1:  # pragma: no cover
                upcoming.append((ann_this_year, name, years))  # pragma: no cover
        else:
            # Next year's anniversary
            try:
                ann_next_year = created.replace(year=today.year + 1)
            except ValueError:  # pragma: no cover
                continue  # pragma: no cover
            years = today.year + 1 - created.year
            if years >= 1:
                upcoming.append((ann_next_year, name, years))

    if not upcoming:
        return None  # pragma: no cover
    upcoming.sort()
    date, name, years = upcoming[0]
    days_until = (date - today).days
    year_str = f"{years} year{'s' if years != 1 else ''}"
    return f"📅 Next anniversary: {name} turns {year_str} old on {date.strftime('%B %d')} ({days_until}d away)"


def check_anniversaries(config: dict, state: dict, *, now: datetime | None = None, **_kw) -> None:
    """Post a celebration when a campaign hits a yearly anniversary."""
    group_id = config["group_id"]
    now = now or datetime.now(timezone.utc)
    today = now.date()

    for pair in config["topic_pairs"]:
        pid = str(pair["pbp_topic_ids"][0])
        chat_topic_id = pair["chat_topic_id"]
        name = pair["name"]

        if not helpers.feature_enabled(config, pid, "anniversary"):
            continue  # pragma: no cover

        created_str = pair.get("created")

        if not created_str:
            continue  # pragma: no cover

        created = datetime.strptime(created_str, "%Y-%m-%d").date()

        # Check if today is the anniversary (same month and day)
        if today.month != created.month or today.day != created.day:
            continue

        # How many years?
        years = today.year - created.year
        if years < 1:
            continue  # pragma: no cover

        # Don't post the same anniversary twice
        anniversary_key = f"{pid}:{years}"
        if anniversary_key in state["last_anniversary"]:
            continue

        if years == 1:
            year_str = "1 year"
        else:
            year_str = f"{years} years"

        message = (
            f"🎂 {name} is {year_str} old today!\n\n"
            f"Campaign started {created.strftime('%B %d, %Y')} (W{created.isocalendar()[1]}). "
            f"Here's to more adventures ahead."
        )

        # Append next upcoming anniversary
        next_ann = _next_anniversary(config, today)
        if next_ann:
            message += f"\n\n———\n\n{next_ann}"

        print(f"Anniversary for {name}: {year_str}")
        # ⭐ The campaign's own chat topic, NOT `bot_topic or ...`. Corrected
        # 2026-09-04: Metal City's first anniversary landed in the bot topic,
        # where its players do not read. This is a message ABOUT one campaign
        # addressed TO that campaign's players, which is the opposite of the
        # operational alerts and reports the bot topic exists to keep out of
        # the way. The other 14 `bot_topic or chat_topic_id` sends are
        # deliberately unchanged; they are for the operator, not the table.
        if tg.send_message(group_id, chat_topic_id, message):
            state["last_anniversary"][anniversary_key] = now.isoformat()
