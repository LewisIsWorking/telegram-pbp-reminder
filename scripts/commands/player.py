"""
Player statistics commands.

/mystats — personal posting stats
/myhistory — 8-week sparkline activity chart
"""

from datetime import datetime, timezone, timedelta

import helpers
from helpers import (
    timestamps_in_window, deduplicate_posts,
    calc_avg_gap_str, fmt_relative_date, fmt_date, posts_str,
)

_SPARK_CHARS = " ▁▂▃▄▅▆▇█"


def _sparkline(values: list[int]) -> str:
    """Convert a list of integers into a text sparkline using block characters."""
    if not values or max(values) == 0:
        return "▁" * len(values)
    peak = max(values)
    return "".join(
        _SPARK_CHARS[min(round(v / peak * 8), 8)] for v in values
    )


def build_mystats(pid: str, user_id: str, campaign_name: str,
                  state: dict, gm_ids: set, config: dict | None = None) -> str:
    """Build personal stats for a player's /mystats command."""
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    is_gm = user_id in gm_ids
    role = "GM" if is_gm else "Player"

    # Character name
    char_name = helpers.character_name(config, pid, user_id) if config else None

    # Get their data
    topic_ts = helpers.get_topic_timestamps(state, pid)
    raw_ts = topic_ts.get(user_id, [])
    total_count = state.get("message_counts", {}).get(pid, {}).get(user_id, 0)

    if not raw_ts:
        return f"No posts tracked yet for you in {campaign_name}. Post something and check back!"

    all_posts = sorted(datetime.fromisoformat(ts) for ts in raw_ts)
    sessions = deduplicate_posts(all_posts)
    week_posts = deduplicate_posts(timestamps_in_window(raw_ts, week_ago))
    avg_gap = calc_avg_gap_str(raw_ts)
    last_post_str = fmt_relative_date(now, all_posts[-1])

    # Calculate posting streak (consecutive days with posts)
    streak = helpers.calc_streak(raw_ts, now)

    header = f"Your stats in {campaign_name} ({role})"
    if char_name:
        header += f" — playing {char_name}"
    header += ":"

    lines = [
        header,
        f"Total: {posts_str(total_count)} ({len(sessions)} sessions)",
        f"This week: {posts_str(len(week_posts))}",
        f"Avg gap: {avg_gap}",
        f"Last post: {last_post_str}",
    ]

    # Word count stats
    total_words = state.get("word_counts", {}).get(pid, {}).get(user_id, 0)
    if total_words > 0 and total_count > 0:
        avg_words = total_words / total_count
        lines.append(f"Words written: {total_words:,} (~{avg_words:.0f}/post)")

    if streak > 1:
        lines.append(f"🔥 Streak: {streak} consecutive days")
    elif streak == 1:
        lines.append(f"Streak: 1 day (keep it going!)")

    return "\n".join(lines)


def build_myhistory(pid: str, user_id: str, campaign_name: str,
                    state: dict, gm_ids: set) -> str:
    """Build a posting history sparkline for the last 8 weeks."""
    now = datetime.now(timezone.utc)
    is_gm = user_id in gm_ids
    role = "GM" if is_gm else "Player"

    topic_ts = helpers.get_topic_timestamps(state, pid)
    raw_ts = topic_ts.get(user_id, [])

    if not raw_ts:
        return f"No posting history yet in {campaign_name}."

    # Calculate weekly post counts for last 8 weeks
    weeks = []
    for w in range(7, -1, -1):
        start = now - timedelta(weeks=w + 1)
        end = now - timedelta(weeks=w)
        count = len(timestamps_in_window(raw_ts, start, end))
        weeks.append(count)

    spark = _sparkline(weeks)
    total = sum(weeks)
    peak = max(weeks)
    current = weeks[-1]

    # Week labels
    label_start = fmt_date(now - timedelta(weeks=8))
    label_end = fmt_date(now)

    lines = [
        f"Posting history in {campaign_name} ({role}):",
        f"",
        f"{label_start}  {spark}  {label_end}",
        f"",
        f"8 weeks: {posts_str(total)} total",
        f"Peak week: {posts_str(peak)}",
        f"This week: {posts_str(current)}",
    ]

    # Trend
    if len(weeks) >= 2 and weeks[-2] > 0:
        trend = helpers.trend_icon(weeks[-1], weeks[-2])
        lines.append(f"Trend: {trend}")

    return "\n".join(lines)
