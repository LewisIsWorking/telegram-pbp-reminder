"""Self-replacing "what's running and when" post for the GM queue topic.

One message, rewritten on every run: today's fixed-clock schedule with
what has already fired, the interval jobs and when they are next due,
and the next cron tick.

Why one message and not two
---------------------------
A "next fire" timer is only useful if it is current, and the cron ticks
twice an hour — so an accurate timer has to refresh every run anyway.
Since the post deletes its predecessor, refreshing costs no clutter: the
topic always holds exactly one of these. Folding the schedule into the
same message means one lifecycle to manage rather than two, and one
thing to delete.

Why delete-and-repost rather than editMessageText
-------------------------------------------------
Editing would leave the message wherever it was, drifting up the topic
as other posts arrive. Deleting and reposting keeps it pinned to the
bottom, which is the point: glance at the end of the topic and see what
the bot is about to do.

Sent with ``silent=True``. Without that this would notify 48 times a
day. The delete goes through ``tg.delete_message``, so it inherits the
bot-sent registry guard — this post can only ever remove its own
previous message.
"""

from datetime import datetime, timedelta, timezone

import helpers
import telegram as tg
from scheduled import local_time
from scheduled.schedule_table import todays_items, fixed_schedule

# Interval jobs, as (state key, interval-days, label). These fire relative
# to their last run rather than on a clock, so they get "next due" rather
# than a time of day. Nested dict keys (per-campaign) are summarised by
# their earliest due entry.
_INTERVAL_JOBS = [
    ("last_leaderboard", helpers.LEADERBOARD_INTERVAL_DAYS, "Leaderboard"),
    ("last_roster", helpers.ROSTER_INTERVAL_DAYS, "Roster summary"),
    ("last_pace", helpers.PACE_INTERVAL_DAYS, "Pace report"),
]


def next_tick(now: datetime) -> datetime:
    """Next cron fire. The workflow runs at :00 and :30 every hour."""
    if now.minute < 30:
        return now.replace(minute=30, second=0, microsecond=0)
    return (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)


def _earliest(value) -> datetime | None:
    """Earliest ISO timestamp in a str or a dict-of-str, else None."""
    if isinstance(value, str):
        raw = [value]
    elif isinstance(value, dict):
        raw = [v for v in value.values() if isinstance(v, str)]
    else:
        return None
    stamps = []
    for s in raw:
        try:
            stamps.append(datetime.fromisoformat(s))
        except (ValueError, TypeError):
            continue
    return min(stamps) if stamps else None


def _interval_lines(state: dict, now: datetime) -> list[str]:
    """One 'next due' line per interval job, soonest first."""
    rows = []
    for key, days, label in _INTERVAL_JOBS:
        last = _earliest(state.get(key))
        if last is None:
            rows.append((0.0, f"  • {label} — due now"))
            continue
        due = last + timedelta(days=days)
        hours = (due - now).total_seconds() / 3600
        when = "due now" if hours <= 0 else (
            f"in {int(hours)}h" if hours < 48 else f"in {int(hours // 24)}d")
        rows.append((hours, f"  • {label} — {when}"))
    rows.sort(key=lambda r: r[0])
    return [text for _h, text in rows]


def _at(now: datetime, hour: int, day_offset: int = 0) -> datetime:
    """The UTC datetime of ``hour`` on now's date (+offset days).

    Built as a real datetime rather than formatting the raw int so the
    local-time conversion handles BST/GMT — and any day rollover — by
    itself. Adding an hour by hand would be wrong for half the year.
    """
    base = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    return base + timedelta(days=day_offset)


def build_schedule_text(config: dict, state: dict, now: datetime) -> str:
    """Render the schedule + timer body, in the GM's local timezone.

    Gates remain UTC everywhere; only the rendering is converted. See
    ``scheduled.local_time``.
    """
    lines = ["🗓️ Bot schedule — "
             + local_time.to_local(now).strftime("%A %d %b, %H:%M ")
             + local_time.tz_label(local_time.to_local(now)), ""]

    today = todays_items(config, now)
    lines.append("━━ Today ━━")
    if today:
        for item in today:
            mark = "✅" if item["done"] else "🕒"
            when = local_time.to_local(_at(now, item["hour"]))
            lines.append(f"  {mark} {when:%H:%M} — {item['label']}")
    else:
        lines.append("  Nothing on the fixed clock today.")

    upcoming = _upcoming_days(config, now)
    if upcoming:
        lines.append("")
        lines.append("━━ Coming up ━━")
        lines.extend(upcoming)

    interval = _interval_lines(state, now)
    if interval:
        lines.append("")
        lines.append("━━ Interval jobs ━━")
        lines.extend(interval)

    nxt = next_tick(now)
    mins = max(0, int((nxt - now).total_seconds() // 60))
    lines.append("")
    lines.append(f"⏱️ Next run: {local_time.fmt(nxt)} (in {mins} min)")
    lines.append("Runs every :00 and :30. This post replaces itself each run.")
    return "\n".join(lines)


def _upcoming_days(config: dict, now: datetime, ahead: int = 6) -> list[str]:
    """Weekday-specific jobs in the next ``ahead`` days, soonest first.

    Day names come from the *local* occurrence, not the UTC weekday, so
    a late-evening UTC job that lands after local midnight is named on
    the day the GM would actually see it.
    """
    out = []
    for offset in range(1, ahead + 1):
        day = (now.weekday() + offset) % 7
        for item in fixed_schedule(config):
            if item["day"] == day:
                when = local_time.to_local(_at(now, item["hour"], offset))
                out.append(f"  {when:%A} {when:%H:%M} — {item['label']}")
    return out


def post_schedule(config: dict, state: dict, *,
                  now: datetime | None = None, **_kw) -> None:
    """Replace the schedule post in the GM queue topic.

    Deletes the previous one first so the topic holds exactly one, and
    so the current copy always sits at the bottom where it is visible.
    """
    now = now or datetime.now(timezone.utc)
    bot_topic = config.get("bot_topic_id")
    if not bot_topic:
        return
    if not config.get("schedule_post_enabled", True):
        return

    prev = state.get("schedule_post_msg_id")
    text = build_schedule_text(config, state, now)
    msg_id = tg.send_message_id(config["group_id"], bot_topic, text,
                                silent=True)
    if not msg_id:
        return  # send failed — keep the old one rather than leaving none
    # Delete only after the replacement is up, so a failed send never
    # leaves the topic with no schedule at all.
    if prev:
        tg.delete_message(config["group_id"], prev)
    state["schedule_post_msg_id"] = msg_id
