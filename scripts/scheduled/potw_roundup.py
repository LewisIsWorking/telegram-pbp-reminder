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
from scheduled.potw_streaks import compute_campaign_streak


# A run of wins worth mentioning. Two in a row is already a story; one
# is just this week's winner and saying "1-week streak" would be noise.
MIN_STREAK = 2


def streak_note(streak: int) -> str:
    """The trailing streak fragment for a roundup line, or empty.

    ⚠️ Deliberately looser than ``potw_streaks.CAMPAIGN_MILESTONES``,
    which fires a whole celebration post only at 2, 3, 5 and 10. Lewis
    asked on 2026-09-07 for the roundup to say "when a player has a
    streak", so a 4-week run reads here even though it earns no separate
    announcement. Two different questions: this one is "is it still
    going", that one is "is it worth a fanfare".
    """
    return f" · 🔥 {streak}-week streak" if streak >= MIN_STREAK else ""


def build_roundup_text(awarded: list[dict], now: datetime,
                       streaks: dict | None = None) -> str:
    """Render the roundup body for the winners awarded this week.

    ``awarded`` entries are ``{"campaign", "pid", "winner"}`` as collected
    by ``player_of_the_week``; ``winner`` is the candidate dict carrying
    ``post_count`` and ``avg_gap_hours``. Sorted by average gap so the
    most consistent poster across all campaigns reads first.

    ``streaks`` maps pid -> consecutive weeks won. Passed in rather than
    computed here so this stays a pure renderer and the streak sums can
    be tested against a history fixture on their own.
    """
    ranked = sorted(awarded, key=lambda a: a["winner"]["avg_gap_hours"])
    lines = [f"🏆 Players of the Week — {potw_schedule.week_key(now)}", ""]
    for item in ranked:
        w = item["winner"]
        lines.append(
            f"{item['campaign']}: {helpers.player_mention(w)} — "
            f"{helpers.posts_str(w['post_count'])}, "
            f"avg gap {w['avg_gap_hours']:.1f}h"
            f"{streak_note((streaks or {}).get(item['pid'], 0))}"
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

    # ⚠️ Read AFTER player_of_the_week appended this week's wins, so the
    # count includes the win being announced. A streak computed before
    # the append would always read one short.
    # ⚠️ `.get`, not `[...]`. The roundup is a summary of work already
    # done and posted; it must never be the thing that raises. A winner
    # dict without a user_id simply gets no streak note rather than
    # taking the whole roundup down after the awards have gone out.
    history = state.get("potw_history", [])
    streaks = {}
    for item in awarded:
        uid = item["winner"].get("user_id")
        if uid:
            streaks[item["pid"]] = compute_campaign_streak(
                history, item["pid"], uid)

    if tg.send_message(config["group_id"], bot_topic,
                       build_roundup_text(awarded, now, streaks)):
        potw_schedule.mark_done(state, "last_potw_roundup", now)
        print(f"POTW roundup posted for {len(awarded)} campaign(s)")
