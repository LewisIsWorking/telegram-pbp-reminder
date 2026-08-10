"""The bot's fixed-clock schedule, as data.

Every entry here mirrors a real gate in a ``scheduled/`` module. The
gates stay authoritative — this table exists so the schedule post can
*describe* them without each job needing to publish its own timing.

⚠️ **If you change a gate, change it here too.** The pairing is checked
by ``test_schedule_post.py``, which asserts the constants this table
quotes still match ``helpers`` (POTW weekday/hour) and the config keys
it reads. That catches the drift for the tunable ones; the hardcoded
weekday jobs (Sunday polls, Friday result) are covered by a comment
naming their source line so a grep finds them.

Only *fixed-clock* jobs live here. Interval jobs (leaderboard every 3
days, pace every 7, recruitment every 14, roster every 3) fire relative
to when they last ran, so they have no clock time to advertise — they
are summarised separately by ``schedule_post`` from their ``last_*``
state instead.
"""

from datetime import datetime

import helpers

# weekday(): 0=Mon .. 6=Sun. None means "every day".
_DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday",
              "Friday", "Saturday", "Sunday"]


def fixed_schedule(config: dict) -> list[dict]:
    """Return the fixed-clock jobs as ``{day, hour, label}`` dicts.

    ``day`` is a ``weekday()`` int, or None for daily. Hours are UTC and
    read from config where the job reads them from config, so the post
    cannot claim 09:00 while the job actually uses 07:00.
    """
    poll_hour = config.get("poll_post_hour", 7)
    diag_hour = config.get("diagnostic_hour", 8)
    raw = config.get("queue_daily_hours") or (
        [config["queue_daily_hour"]]
        if config.get("queue_daily_hour") is not None else [])
    queue_hours = raw if isinstance(raw, list) else [raw]

    items = [
        # scheduled/session_poll.py, week_welcome.py, swimming_poll.py
        {"day": 6, "hour": poll_hour, "label": "Session poll + week welcome"},
        # scheduled/diagnostic.py:68
        {"day": None, "hour": diag_hour, "label": "Daily diagnostic"},
        # scheduled/potw.py via helpers.POTW_WEEKDAY / POTW_POST_HOUR
        {"day": helpers.POTW_WEEKDAY, "hour": helpers.POTW_POST_HOUR,
         "label": "🏆 Player of the Week + roundup"},
        {"day": helpers.POTW_COUNTDOWN_WEEKDAY, "hour": helpers.POTW_POST_HOUR,
         "label": "⏳ POTW standings"},
        # scheduled/poll_result.py:14
        {"day": 4, "hour": 15, "label": "Session poll result"},
    ]
    for h in queue_hours:
        # scheduled/queue_reminder.py:67
        items.append({"day": None, "hour": h, "label": "📋 GM queue digest"})
    return items


def day_label(day: int | None) -> str:
    """Human label for a weekday int, or 'daily' for None."""
    return "daily" if day is None else _DAY_NAMES[day]


def todays_items(config: dict, now: datetime) -> list[dict]:
    """Fixed-clock jobs due today, earliest first.

    Includes daily jobs and any weekday job matching ``now``. Each dict
    gains ``done``: True when its hour has already passed, so the post
    can show what has fired and what is still coming.
    """
    out = []
    for item in fixed_schedule(config):
        if item["day"] is not None and item["day"] != now.weekday():
            continue
        out.append({**item, "done": now.hour >= item["hour"]})
    out.sort(key=lambda i: i["hour"])
    return out
