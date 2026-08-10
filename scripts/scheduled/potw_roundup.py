"""Single summary of every campaign's Player of the Week.

Posted to the bot topic straight after the individual awards, so one
glance answers "who won this week" across all campaigns instead of
hunting through a dozen per-campaign topics.

Why this is a *second* post rather than a replacement
-----------------------------------------------------
The per-campaign messages have to stay. ``boons/handler.py`` edits each
POTW message **in place** when its winner claims a boon, and
``pending_potw_boons`` is keyed by campaign pid. Merging every campaign
into one message would mean several winners rewriting the same message,
each with their own ``base_message``. So the roundup is additive: it
summarises, it does not carry boons.
"""

from datetime import datetime, timezone

import helpers
import telegram as tg
from scheduled import potw_schedule


def build_roundup_text(awarded: list[dict], now: datetime) -> str:
    """Render the roundup body for the winners awarded this week.

    ``awarded`` entries are ``{"campaign", "pid", "winner"}`` as collected
    by ``player_of_the_week``; ``winner`` is the candidate dict carrying
    ``post_count`` and ``avg_gap_hours``. Sorted by average gap so the
    most consistent poster across all campaigns reads first.
    """
    ranked = sorted(awarded, key=lambda a: a["winner"]["avg_gap_hours"])
    lines = [f"🏆 Players of the Week — {potw_schedule.week_key(now)}", ""]
    for item in ranked:
        w = item["winner"]
        lines.append(
            f"{item['campaign']}: {helpers.player_mention(w)} — "
            f"{helpers.posts_str(w['post_count'])}, "
            f"avg gap {w['avg_gap_hours']:.1f}h"
        )
    lines.append("")
    lines.append("Winners: claim your boon at "
                 "https://comeonover.netlify.app/PathWars")
    return "\n".join(lines)


def post_potw_roundup(config: dict, state: dict, awarded: list[dict], *,
                      now: datetime | None = None, **_kw) -> None:
    """Post the weekly roundup to the bot topic.

    No-ops when nothing was awarded (a fully quiet week posts nothing at
    all rather than an empty leaderboard), when there is no bot topic
    configured, or when this week's roundup already went out.
    """
    now = now or datetime.now(timezone.utc)
    if not awarded:
        return
    bot_topic = config.get("bot_topic_id")
    if not bot_topic:
        return
    if potw_schedule.already_done(state, "last_potw_roundup", now):
        return

    if tg.send_message(config["group_id"], bot_topic,
                       build_roundup_text(awarded, now)):
        potw_schedule.mark_done(state, "last_potw_roundup", now)
        print(f"POTW roundup posted for {len(awarded)} campaign(s)")
