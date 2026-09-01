"""Campaign and player inactivity alerts."""

from datetime import datetime, timezone

import helpers
from helpers import build_topic_maps, fmt_date
import telegram as tg
from players.history import post_roster
from players.permanence import is_permanent
from players.proxy import effective_post_time, is_proxied
from players.retire import retire_seat
from scheduled.gm_bottleneck import gm_last_post, gm_note
from scheduled.inactivity_policy import sweep_and_warn


def check_and_alert(config: dict, state: dict, *, now: datetime | None = None, maps=None) -> None:
    """Send alerts to campaigns inactive beyond alert_after_hours."""
    group_id = config["group_id"]
    bot_topic = config.get("bot_topic_id")
    alert_hours = config.get("alert_after_hours", 4)
    now = now or datetime.now(timezone.utc)

    maps = maps or build_topic_maps(config)

    for pid, chat_topic_id in maps.to_chat.items():
        name = maps.to_name[pid]

        if not helpers.feature_enabled(config, pid, "alerts"):
            continue

        if pid in state.get("paused_campaigns", {}):
            continue

        if pid not in state.get("topics", {}):
            continue

        topic_state = state["topics"][pid]
        last_time = datetime.fromisoformat(topic_state["last_message_time"])
        elapsed_hours = helpers.hours_since(now, last_time)

        if elapsed_hours < alert_hours:
            continue

        # Don't re-alert within 24 hours (once per day max)
        last_alert_str = state["last_alerts"].get(pid)
        if last_alert_str:
            since_last = helpers.hours_since(now, datetime.fromisoformat(last_alert_str))
            if since_last < 24:
                continue

        hours_int = int(elapsed_hours)
        days = hours_int // 24
        remaining_hours = hours_int % 24
        last_user = topic_state.get("last_user", "someone")
        last_user_id = topic_state.get("last_user_id", "")

        time_str = f"{days}d {remaining_hours}h" if days > 0 else f"{hours_int}h"

        # Look up total message count for last poster
        count = state.get("message_counts", {}).get(pid, {}).get(last_user_id, 0)
        count_str = f" ({count} total posts)" if count > 0 else ""

        last_date = fmt_date(last_time)

        message = (
            f"━━━━━━━━━━━━━━━━\n"
            f"No new posts in {name} PBP for {time_str}.\n"
            f"Last post was from {last_user}{count_str} on {last_date}."
        )
        message += gm_note(config, state, pid, now)

        print(f"Sending alert for {name}: {time_str} inactive")
        if tg.send_message(group_id, bot_topic or chat_topic_id, message):
            state["last_alerts"][pid] = now.isoformat()

_INACTIVITY_TEMPLATES = {
    1: "{mention} hasn't posted in {campaign} PBP for {days} days (last: {date}). Everything okay?",
    2: "{mention} still no post in {campaign} PBP. It's been {days} days now (last: {date}).",
    3: "{mention} it's been {days} days without a post in {campaign} PBP (last: {date}). 1 week until auto-removal from the campaign.",
}


def check_player_activity(config: dict, state: dict, *, now: datetime | None = None, maps=None) -> None:
    """Warn inactive players at 1/2/3 weeks, remove at 4 weeks.

    The two halves are gated separately (``warnings`` and ``removals``),
    because nagging a player and sweeping a dead seat are different acts
    with different audiences. See ``scheduled/inactivity_policy``.
    """
    group_id = config["group_id"]
    bot_topic = config.get("bot_topic_id")
    now = now or datetime.now(timezone.utc)

    # Build lookup: canonical pbp_topic_id -> chat_topic_id
    maps = maps or build_topic_maps(config)

    # Cache GM last-post per campaign to avoid repeated lookups
    _gm_bottleneck = {}

    players_to_remove = []

    for player_key, player in state["players"].items():
        pbp_topic_id = player["pbp_topic_id"]
        chat_topic_id = maps.to_chat.get(pbp_topic_id)
        if not chat_topic_id:
            continue  # pragma: no cover
        sweeps, warns = sweep_and_warn(config, state, pbp_topic_id)
        if not (sweeps or warns):
            continue
        # Skip players who are marked as away
        user_id = player.get("user_id", "")
        if helpers.is_away(state, pbp_topic_id, user_id, now):
            continue
        # Cache GM bottleneck status (3+ days inactive)
        if pbp_topic_id not in _gm_bottleneck:
            gm_last = gm_last_post(config, state, pbp_topic_id)
            _gm_bottleneck[pbp_topic_id] = (
                gm_last is not None and helpers.days_since(now, gm_last) >= 3
            )

        # ``played_by``: measure this seat through whoever posts for it.
        # Added 2026-09-01 after Horia reached week 4 while Anthony was
        # rolling for Lorn in every scene. A redirection, not an
        # exemption: a quiet proxy still gets this seat swept, and an
        # unresolvable proxy falls back to the seat's own clock.
        last_post = effective_post_time(player, pbp_topic_id, state)
        if last_post is None:
            continue  # pragma: no cover - no usable timestamp either way
        elapsed_days = helpers.days_since(now, last_post)
        current_week = int(elapsed_days / 7)
        last_warned = player.get("last_warned_week", 0)

        first_name = player["first_name"]
        campaign = player["campaign_name"]
        mention = helpers.player_mention(player)
        days_inactive = int(elapsed_days)
        last_date = fmt_date(last_post)

        # 4+ weeks: remove. Fires even when the GM is the bottleneck, and
        # (since 2026-08-30) even when `warnings` is disabled: sweeping a
        # dead seat is roster hygiene, not a message to a player. Gated
        # on its own `removals` feature instead. See inactivity_policy.
        # Permanent players are never removed — skip the removal block entirely
        if not is_permanent(player, config) and current_week >= helpers.PLAYER_REMOVE_WEEKS:
            if sweeps and last_warned < helpers.PLAYER_REMOVE_WEEKS:
                message = (
                    f"{mention} has not posted in {campaign} PBP for "
                    f"{days_inactive} days (last: {last_date}). They are no longer tracked "
                    f"as an active player in this campaign."
                )
                message += gm_note(config, state, pbp_topic_id, now)
                print(f"Removing {first_name} from {campaign} ({days_inactive}d)")
                tg.send_message(group_id, bot_topic or chat_topic_id, message)
                players_to_remove.append(player_key)
            continue

        # 1, 2, 3 week warnings: only when this campaign wants them, and
        # never while the GM is the one holding the game up.
        #
        # ⭐ And never for a proxied seat. The warning @-mentions the
        # player to ask why they have not posted; for a character
        # somebody else rolls for, that question has an answer and the
        # person receiving it is not the one who could act on it. The
        # 4-week REMOVAL above still applies, on the proxy's clock:
        # this suppresses the nagging, not the hygiene.
        if not warns or _gm_bottleneck[pbp_topic_id] or is_proxied(player):
            continue
        for week_mark in helpers.PLAYER_WARN_WEEKS:
            # Skip week-3 warning for permanent players (it mentions auto-removal)
            if week_mark == 3 and is_permanent(player, config):
                continue
            if current_week >= week_mark and last_warned < week_mark:
                template = _INACTIVITY_TEMPLATES.get(week_mark, _INACTIVITY_TEMPLATES[3])
                message = template.format(
                    mention=mention, campaign=campaign,
                    days=days_inactive, date=last_date,
                )
                message += gm_note(config, state, pbp_topic_id, now)
                print(f"Warning {first_name} in {campaign}: week {week_mark}")
                if tg.send_message(group_id, bot_topic or chat_topic_id, message):
                    player["last_warned_week"] = week_mark
                break  # One warning per player per run

    # Move removed players out. Not kicked: nobody decided this, they
    # simply stopped posting, and the history should not imply otherwise.
    #
    # ⚠️ announce=False, then ONE roster post per campaign at the end.
    # Announcing per removal put five near-identical rosters into C08's
    # chat topic in a single run when its 2026-08-30 backlog was swept,
    # four of them showing intermediate states nobody needs.
    swept = set()
    for key in players_to_remove:
        removed = retire_seat(key, state, config, now=now, announce=False)
        swept.add(str(removed.get("pbp_topic_id", "")))
    for pid in sorted(swept):
        post_roster(pid, config, state)
