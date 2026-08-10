"""Player of the Week award."""

import json
import random
from datetime import datetime, timedelta, timezone

import helpers
from helpers import (
    build_topic_maps, deduplicate_posts,
    fmt_date, posts_str, timestamps_in_window,
)
from helpers_pkg import campaigns
import telegram as tg
from scheduled import potw_schedule


# Transcript post-link lookup lives in scheduled.potw_links; re-exported
# here so player_of_the_week and test patch targets keep resolving. Tests
# that redirect the transcript root patch scheduled.potw_links._LOGS_DIR.
from scheduled.potw_links import _find_player_post_links  # noqa: F401


def _gather_potw_candidates(
    topic_timestamps: dict, gm_ids: set, week_ago: datetime, pid: str, state: dict,
) -> list[dict]:
    """Find POTW candidates: players with enough posts, ranked by avg gap."""
    candidates = []
    for user_id, timestamps in topic_timestamps.items():
        if user_id in gm_ids:
            continue

        sessions = deduplicate_posts(timestamps_in_window(timestamps, week_ago))
        if len(sessions) < helpers.POTW_MIN_POSTS:
            continue

        sessions.sort()
        avg_gap = helpers.avg_gap_hours(sessions) or float("inf")

        player = helpers.get_player(state, pid, user_id)
        candidates.append({
            "user_id": user_id,
            "first_name": player.get("first_name", "Unknown"),
            "last_name": player.get("last_name", ""),
            "username": player.get("username", ""),
            "avg_gap_hours": avg_gap,
            "post_count": len(sessions),
        })
    return candidates


def player_of_the_week(config: dict, state: dict, *, now: datetime | None = None, maps=None) -> None:
    """Award Player of the Week — Monday only, once per calendar week.

    Fires on ``POTW_WEEKDAY`` at or after ``POTW_POST_HOUR`` UTC, guarded
    per campaign by an ISO week key. Previously this used a rolling
    ``interval_elapsed`` gate which drifted later each week and, on a
    quiet week, fired on the first tick after someone posted — see
    ``scheduled.potw_schedule`` for the full rationale.

    Every enabled campaign is evaluated in the same pass, so the awards
    arrive together instead of scattered across the week, and the winners
    are summarised in a single roundup post.
    """
    group_id = config["group_id"]
    bot_topic = config.get("bot_topic_id")
    now = now or datetime.now(timezone.utc)

    if not potw_schedule.due(now, helpers.POTW_WEEKDAY, helpers.POTW_POST_HOUR):
        return

    try:
        with open(helpers.BOONS_PATH, encoding="utf-8") as f:
            boons = json.load(f)  # pragma: no cover
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Could not load boons: {e}")
        boons = ["Something mildly beneficial happens to you today."]

    maps = maps or build_topic_maps(config)
    week_ago = now - timedelta(days=7)
    # Winners collected across every campaign in this single Monday pass,
    # then summarised by scheduled.potw_roundup. Per-campaign messages are
    # still sent individually because boons/handler.py edits each one in
    # place when its winner claims, keyed by pid in pending_potw_boons.
    awarded: list[dict] = []
    week_stamps = state.setdefault("potw_week", {})

    for pid, chat_topic_id in maps.to_chat.items():
        if not helpers.feature_enabled(config, pid, "potw"):
            continue
        # Per-campaign idempotency: the cron ticks twice an hour, so
        # without this every tick for the rest of Monday would repost.
        if week_stamps.get(pid) == potw_schedule.week_key(now):
            continue

        name = maps.to_name.get(pid)
        # 🛡️ Refuse to POTW a campaign we can't name. The old fallback was
        # `name = maps.to_name.get(pid, "Unknown")` which would post "Player of
        # the Week for Unknown" AND, worse, persist "campaign": "Unknown" into
        # players.json forever via the pending_potw_boons → handler flow. If
        # `maps` is somehow out of sync with the live config, try resolving
        # from config directly before giving up.
        if not name:
            name = campaigns.try_get_name(config, pid)
        if not name:
            print(f"[potw] Skipping unmapped topic {pid} (not in campaigns config)")
            continue
        topic_timestamps = helpers.get_topic_timestamps(state, pid)
        gm_ids = helpers.gm_ids_for_campaign(config, pid)

        candidates = _gather_potw_candidates(topic_timestamps, gm_ids, week_ago, pid, state)
        if not candidates:
            # Stamp even with no winner. The old code `continue`d without
            # stamping, which left the gate open so the award fired on the
            # first tick after someone posted — the "goes off at random"
            # bug. A quiet week is now simply a week with no award.
            week_stamps[pid] = potw_schedule.week_key(now)
            print(f"No POTW candidates for {name} (need {helpers.POTW_MIN_POSTS}+ posts)")
            continue

        winner = min(candidates, key=lambda c: c["avg_gap_hours"])
        mention = helpers.player_mention(winner)
        avg_gap_str = f"{winner['avg_gap_hours']:.1f}h"

        # Pick 3 random flavour boons + 1 mechanical boon
        chosen_boons = random.sample(boons, min(3, len(boons)))
        chosen_boons.append(random.choice(helpers.MECHANICAL_BOONS))

        base_message = (
            f"Player of the Week for {name}: {mention}!\n"
            f"({fmt_date(week_ago)} to {fmt_date(now)})\n\n"
            f"{posts_str(winner['post_count'])} this week with an average "
            f"gap of {avg_gap_str} between posts. The most consistent "
            f"driver of the story."
        )

        # Find winner's posts with links from transcripts
        winner_links = _find_player_post_links(
            name, winner["first_name"], pid, week_ago)
        if winner_links:
            base_message += "\n\nPosts this week:"  # pragma: no cover
            for link in winner_links:  # pragma: no cover
                base_message += f"\n{link}"  # pragma: no cover

        boon_text = "\n\nChoose your boon:\n"
        for i, b in enumerate(chosen_boons):
            boon_text += f"\n{i + 1}. {b}\n"
        # User-facing boon selection moved entirely to the website on
        # 2026-05-11. Players log in at the URL below to claim. The
        # bot no longer accepts /chooseboon or inline-button taps —
        # see commands/help_text.py removal and dispatch/* handler
        # removals in the same commit.
        boon_text += ("\nLog in to claim your boon: "
                      "\n🔗 https://comeonover.netlify.app/PathWars")

        print(f"POTW for {name}: {winner['first_name']} (avg gap {avg_gap_str})")
        # send_message_id (not send_message_with_buttons) since there
        # are no inline buttons anymore. Returns the message id for
        # tracking the pending POTW entry in state, same as before.
        msg_id = tg.send_message_id(group_id, bot_topic or chat_topic_id,
                                    base_message + boon_text)
        if msg_id:
            state["last_potw"][pid] = now.isoformat()
            week_stamps[pid] = potw_schedule.week_key(now)
            awarded.append({"campaign": name, "pid": pid, "winner": winner})
            _, week_num, _ = now.isocalendar()
            state["pending_potw_boons"][pid] = {
                "message_id": msg_id,
                "winner_user_id": winner["user_id"],
                "campaign_name": name,
                "boons": chosen_boons,
                "base_message": base_message,
                "posted_at": now.isoformat(),
            }
            # Permanent POTW history record
            history = state.setdefault("potw_history", [])
            history.append({
                "week":        f"W{week_num}",
                "year":        now.year,
                "date":        now.strftime("%Y-%m-%d"),
                "campaign":    name,
                "campaign_pid": pid,
                "user_id":     winner["user_id"],
                "first_name":  winner["first_name"],
                "username":    winner.get("username", ""),
                "post_count":  winner["post_count"],
                "avg_gap_h":   round(winner["avg_gap_hours"], 1),
                "boons_offered": chosen_boons,
                "boon_chosen": None,  # updated by boons/handler.py on pick
            })
            # Update mvp_wins counter
            uid = winner["user_id"]
            wins = state.setdefault("mvp_wins", {})
            entry = wins.setdefault(uid, {"name": helpers.player_mention(winner), "count": 0})
            entry["count"] += 1
            # Check and announce streaks
            from scheduled.potw_streaks import announce_streaks
            announce_streaks(config, state, winner, name, pid,
                             group_id, bot_topic or chat_topic_id)

    # One summary of every campaign's winner, posted after the individual
    # awards so the roundup can't precede the messages it summarises.
    from scheduled.potw_roundup import post_potw_roundup
    post_potw_roundup(config, state, awarded, now=now)

