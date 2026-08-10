"""Midweek Player of the Week standings — "who is winning right now".

Fires on ``POTW_COUNTDOWN_WEEKDAY`` (Thursday) at or after
``POTW_POST_HOUR``, giving players a few days' notice that Monday's award
is coming and something concrete to chase.

Deliberately reuses ``potw._gather_potw_candidates`` and the same
``min(avg_gap_hours)`` selection the award itself uses, rather than
reimplementing the ranking. If those two ever diverged, the Thursday post
would name a leader the Monday award then contradicts — the most
corrosive thing a standings post can do. Sharing the function makes that
impossible by construction.

The window is a rolling seven days ending now, which is the same window
shape the award uses, so Thursday's numbers are a genuine preview rather
than a different measurement. They are explicitly labelled as provisional
because three more days of posting can still change the order.
"""

from datetime import datetime, timedelta, timezone

import helpers
from helpers import build_topic_maps
from helpers_pkg import campaigns
import telegram as tg
from scheduled import potw_schedule
from scheduled.potw import _gather_potw_candidates


def _standings_for(config: dict, state: dict, maps, now: datetime) -> list[dict]:
    """Rank current POTW contenders per campaign.

    Returns ``[{"campaign", "leader", "runner_up"}]`` for every enabled
    campaign that currently has at least one qualifying player. Ordered by
    the leader's average gap so the tightest campaign reads first.
    """
    week_ago = now - timedelta(days=7)
    rows: list[dict] = []
    for pid in maps.to_chat:
        if not helpers.feature_enabled(config, pid, "potw"):
            continue
        name = maps.to_name.get(pid) or campaigns.try_get_name(config, pid)
        if not name:
            continue
        candidates = _gather_potw_candidates(
            helpers.get_topic_timestamps(state, pid),
            helpers.gm_ids_for_campaign(config, pid),
            week_ago, pid, state)
        if not candidates:
            continue
        ranked = sorted(candidates, key=lambda c: c["avg_gap_hours"])
        rows.append({
            "campaign": name,
            "leader": ranked[0],
            "runner_up": ranked[1] if len(ranked) > 1 else None,
        })
    rows.sort(key=lambda r: r["leader"]["avg_gap_hours"])
    return rows


def build_countdown_text(rows: list[dict], days_to_go: int) -> str:
    """Render the standings body.

    Shows the leader and, where there is one, the closest challenger — the
    gap between those two is the whole point of posting this at all.
    """
    lines = [f"⏳ Player of the Week — {days_to_go} days to go", ""]
    for row in rows:
        lead = row["leader"]
        lines.append(f"{row['campaign']}")
        lines.append(f"  🥇 {helpers.player_mention(lead)} — "
                     f"avg gap {lead['avg_gap_hours']:.1f}h "
                     f"({helpers.posts_str(lead['post_count'])})")
        chase = row["runner_up"]
        if chase:
            behind = chase["avg_gap_hours"] - lead["avg_gap_hours"]
            lines.append(f"  🥈 {helpers.player_mention(chase)} — "
                         f"avg gap {chase['avg_gap_hours']:.1f}h "
                         f"(+{behind:.1f}h behind)")
    lines.append("")
    lines.append("Awarded Monday to the most consistent poster — "
                 "smallest average gap between posts, not the biggest "
                 "wall of text. Still anyone's.")
    return "\n".join(lines)


def post_potw_countdown(config: dict, state: dict, *,
                        now: datetime | None = None, maps=None, **_kw) -> None:
    """Post midweek POTW standings to the bot topic, once per week."""
    now = now or datetime.now(timezone.utc)
    if not potw_schedule.due(now, helpers.POTW_COUNTDOWN_WEEKDAY,
                             helpers.POTW_POST_HOUR):
        return
    bot_topic = config.get("bot_topic_id")
    if not bot_topic:
        return
    if potw_schedule.already_done(state, "last_potw_countdown", now):
        return

    rows = _standings_for(config, state, maps or build_topic_maps(config), now)
    if not rows:
        # Nobody qualifies anywhere — say nothing rather than post an
        # empty scoreboard that reads like the feature is broken.
        return

    # Days until the next award weekday, always 1..7 so Thursday reads 4.
    days_to_go = (helpers.POTW_WEEKDAY - now.weekday()) % 7 or 7
    if tg.send_message(config["group_id"], bot_topic,
                       build_countdown_text(rows, days_to_go)):
        potw_schedule.mark_done(state, "last_potw_countdown", now)
        print(f"POTW countdown posted for {len(rows)} campaign(s)")
