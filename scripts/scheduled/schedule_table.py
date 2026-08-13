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
    """Return the fixed-clock jobs as ``{day, hour, label, checks}`` dicts.

    ``day`` is a ``weekday()`` int, or None for daily. Hours are UTC and
    read from config where the job reads them from config, so the post
    cannot claim 09:00 while the job actually uses 07:00.

    ``checks`` names the labels the job is registered under in
    ``checker._run_checks``. That pairing is what makes completeness
    machine-checkable — see ``test_schedule_is_complete.py``. A source
    comment naming the gate's line number, which is all this table had
    before 2026-08-13, tells a reader where to look but cannot notice a
    job that was never added at all.
    """
    poll_hour = config.get("poll_post_hour", 7)
    diag_hour = config.get("diagnostic_hour", 8)
    # Mirrors scheduled/pin_report.py:58 exactly, including its fallback
    # to the diagnostic hour — the two share 08:00 UTC by default.
    pin_hour = config.get("pin_digest_hour", diag_hour)
    raw = config.get("queue_daily_hours") or (
        [config["queue_daily_hour"]]
        if config.get("queue_daily_hour") is not None else [])
    queue_hours = raw if isinstance(raw, list) else [raw]

    items = [
        # scheduled/session_poll.py:104, week_welcome.py:24
        {"day": 6, "hour": poll_hour, "label": "Session poll + week welcome",
         "checks": ("Session poll", "Week welcome")},
        # scheduled/diagnostic.py:68
        {"day": None, "hour": diag_hour, "label": "Daily diagnostic",
         "checks": ("Daily diagnostic",)},
        # scheduled/potw.py via helpers.POTW_WEEKDAY / POTW_POST_HOUR
        {"day": helpers.POTW_WEEKDAY, "hour": helpers.POTW_POST_HOUR,
         "label": "🏆 Player of the Week + roundup",
         "checks": ("Player of the Week",)},
        {"day": helpers.POTW_COUNTDOWN_WEEKDAY, "hour": helpers.POTW_POST_HOUR,
         "label": "⏳ POTW standings", "checks": ("POTW countdown",)},
        # scheduled/poll_result.py:14
        {"day": 4, "hour": 15, "label": "Session poll result",
         "checks": ("Poll result",)},
        # scheduled/pin_report.py:59. Added 2026-08-13 — it fires daily at
        # the same hour as the diagnostic, so the post showed one job at
        # 09:00 BST when two were due.
        {"day": None, "hour": pin_hour, "label": "📌 Pin digest",
         "checks": ("Pin digest",)},
    ]
    if config.get("swimming_poll_enabled", True):
        # scheduled/swimming_poll.py:42 — same Sunday slot as the session
        # poll, but listed separately because it is independently
        # switchable and currently off.
        items.append({"day": 6, "hour": poll_hour, "label": "🏊 Swimming poll",
                      "checks": ("Swimming poll",)})
    for h in queue_hours:
        # scheduled/queue_reminder.py:67
        items.append({"day": None, "hour": h, "label": "📋 GM queue digest",
                      "checks": ("Queue reminder",)})
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
