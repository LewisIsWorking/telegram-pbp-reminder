"""The GM's posting rate and queue clearing rate, shown on the GM queue post.

Lewis, 2026-10-20: "It would be good if the bot posted to the GM queue topic
about MY post number per day (the rate of clearing the queue) kinda thing."

Two lines go under the queue post's header::

    ✍️ GM posts: 6 today | 9 yesterday | 7.4/day (7d)
    📉 Queue 17 -> 12 since yesterday (5 fewer)

**Posts** are counted from ``state["post_timestamps"]``, which the bot already
records for every message in a campaign's RP topics and keeps for 15 days
(``maintenance.cleanup_timestamps``). Only the global ``gm_user_ids`` count,
because the post is about Lewis's rate: a campaign with its own GM (Theria)
would otherwise mix someone else's posts in. Raw messages are counted, not
the deduplicated "sessions" the leaderboard uses, because each message is a
post the transcripts mark "[GM]".

**Days** are Europe/London calendar days, the same zone every other post
renders in (``scheduled.local_time``). The 7-day average is over the seven
COMPLETE days before today, so it is not dragged down every morning by a
day that has barely started.

**Queue size** has no history anywhere else, so every run records the
unreplied count in ``state["gm_queue_size_log"]`` as ``[iso, n]`` pairs,
kept for 48 hours. The comparison uses the newest sample at least 24 hours
old. Runs are not delivered reliably (see ``scheduled/due.py``), so a sample
up to 36 hours old still counts; with nothing in that window the queue line
is left out rather than compared against the wrong day.

Everything takes ``now`` so tests can pin the clock.
"""

from datetime import datetime, timedelta

import helpers
from scheduled.local_time import to_local

LOG_KEY = "gm_queue_size_log"
KEEP_HOURS = 48
COMPARE_HOURS = 24
STALEST_HOURS = 36
AVERAGE_DAYS = 7


def record_queue_size(state: dict, scanned: dict, now: datetime) -> None:
    """Append this run's unreplied count and drop samples past KEEP_HOURS."""
    total = sum(len(d.get("entries", [])) for d in scanned.values())
    cutoff = now - timedelta(hours=KEEP_HOURS)
    log = [s for s in state.get(LOG_KEY, [])
           if datetime.fromisoformat(s[0]) >= cutoff]
    log.append([now.isoformat(), total])
    state[LOG_KEY] = log


def queue_size_then(state: dict, now: datetime) -> int | None:
    """The unreplied count about 24 hours ago, or None with no usable sample."""
    newest_ok = now - timedelta(hours=COMPARE_HOURS)
    oldest_ok = now - timedelta(hours=STALEST_HOURS)
    best = None
    for iso, n in state.get(LOG_KEY, []):
        at = datetime.fromisoformat(iso)
        if oldest_ok <= at <= newest_ok and (best is None or at > best[0]):
            best = (at, n)
    return best[1] if best else None


def gm_posts_by_day(config: dict, state: dict, now: datetime) -> dict:
    """{London date: GM message count} over every tracked campaign."""
    gm_ids = helpers.gm_id_set(config)
    counts: dict = {}
    for by_user in state.get("post_timestamps", {}).values():
        for uid, stamps in by_user.items():
            if uid not in gm_ids:
                continue
            for iso in stamps:
                day = to_local(datetime.fromisoformat(iso)).date()
                counts[day] = counts.get(day, 0) + 1
    return counts


def posts_line(config: dict, state: dict, now: datetime) -> str:
    """'✍️ GM posts: 6 today | 9 yesterday | 7.4/day (7d)'."""
    counts = gm_posts_by_day(config, state, now)
    today = to_local(now).date()
    yesterday = today - timedelta(days=1)
    week = sum(counts.get(today - timedelta(days=d), 0)
               for d in range(1, AVERAGE_DAYS + 1))
    avg = week / AVERAGE_DAYS
    return (f"✍️ GM posts: {counts.get(today, 0)} today | "
            f"{counts.get(yesterday, 0)} yesterday | "
            f"{avg:.1f}/day ({AVERAGE_DAYS}d)")


def queue_change_line(state: dict, total: int, now: datetime) -> str | None:
    """'📉 Queue 17 -> 12 since yesterday (5 fewer)', or None without history."""
    then = queue_size_then(state, now)
    if then is None:
        return None
    if total == then:
        return f"➖ Queue {total}, same as yesterday"
    diff = abs(total - then)
    icon, word = ("📉", "fewer") if total < then else ("📈", "more")
    return f"{icon} Queue {then} -> {total} since yesterday ({diff} {word})"


def rate_lines(config: dict, state: dict, total: int, now: datetime) -> list:
    """Both lines, ready to go under the queue post's header."""
    lines = [posts_line(config, state, now)]
    change = queue_change_line(state, total, now)
    if change:
        lines.append(change)
    return lines
