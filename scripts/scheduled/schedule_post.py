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

Moving it between topics needs no migration: ``tg.delete_message`` is
scoped to the chat and takes no topic, so the run that first posts to a
new topic also removes the predecessor sitting in the old one.
"""

from datetime import datetime, timedelta, timezone

import telegram as tg
from scheduled import local_time
from scheduled.schedule_intervals import interval_lines
from scheduled.schedule_table import todays_items, fixed_schedule


def next_tick(now: datetime) -> datetime:
    """Next cron fire. The workflow runs at :00 and :30 every hour."""
    if now.minute < 30:
        return now.replace(minute=30, second=0, microsecond=0)
    return (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)


def schedule_destination(config: dict) -> tuple[int, int | None] | None:
    """``(chat_id, thread_id)`` for the schedule post, or None if unset.

    Its own keys, deliberately, rather than reusing ``gm_queue_topic_id``:
    ``leaderboard_topic_id`` is shared by four unrelated posts, so moving
    the leaderboard on 2026-08-12 silently moved the weekly digest,
    message milestones and the hero-point picker with it. A key per
    destination means moving one post moves one post.

    ⭐ Returns a CHAT and a thread, not just a thread (changed 2026-08-17,
    when the post moved to the Nudge Bot Notifications group). The old
    ``schedule_topic`` could only answer "which topic", so its one caller
    had to supply ``config["group_id"]`` itself — an assumption that is
    invisible until the destination is in a different chat, and then
    wrong. A return value that cannot carry the answer makes the caller
    invent one.

    ``schedule_chat_id`` set -> that chat, ``schedule_thread_id`` within
                                it (absent = General, correct for a forum
                                group's default topic).
    otherwise                -> the main group, ``schedule_topic_id``
                                falling back to ``bot_topic_id`` so an
                                older config still works.
    """
    chat = config.get("schedule_chat_id")
    if chat:
        # Deliberately NOT falling back to schedule_topic_id here. That id
        # names a topic in the MAIN group; reused against another chat it
        # would either fail or, worse, land in an unrelated topic that
        # happens to share the number.
        return int(chat), config.get("schedule_thread_id")
    topic = config.get("schedule_topic_id") or config.get("bot_topic_id")
    return (config["group_id"], topic) if topic else None


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

    interval = interval_lines(config, state, now)
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
    destination = schedule_destination(config)
    if not destination:
        return
    if not config.get("schedule_post_enabled", True):
        return
    chat_id, thread_id = destination

    prev = state.get("schedule_post_msg_id")
    # Where the PREVIOUS post lives, which is not necessarily where the
    # next one goes. On the run that moves the post to a new chat these
    # differ, and deleting `prev` in the new chat would either fail or hit
    # an unrelated message that happens to share the id. Older state has
    # no such key, so fall back to the main group — that is where every
    # post written before 2026-08-17 went.
    prev_chat = state.get("schedule_post_chat_id") or config["group_id"]

    text = build_schedule_text(config, state, now)
    msg_id = tg.send_message_id(chat_id, thread_id, text, silent=True)
    if not msg_id:
        return  # send failed — keep the old one rather than leaving none
    # Delete only after the replacement is up, so a failed send never
    # leaves the destination with no schedule at all.
    if prev:
        tg.delete_message(prev_chat, prev)
    state["schedule_post_msg_id"] = msg_id
    state["schedule_post_chat_id"] = chat_id
