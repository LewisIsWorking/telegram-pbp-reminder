"""Player of the Week award."""

import json
import random
from datetime import datetime, timedelta, timezone

import helpers
from helpers import (
    build_topic_maps, deduplicate_posts,
    fmt_date, posts_str, timestamps_in_window,
)
import telegram as tg


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
    """Award Player of the Week based on smallest average gap between posts."""
    group_id = config["group_id"]
    bot_topic = config.get("bot_topic_id")
    now = now or datetime.now(timezone.utc)

    try:
        with open(helpers.BOONS_PATH) as f:
            boons = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        print(f"Warning: Could not load boons: {e}")
        boons = ["Something mildly beneficial happens to you today."]

    maps = maps or build_topic_maps(config)
    week_ago = now - timedelta(days=7)

    for pid, chat_topic_id in maps.to_chat.items():
        if not helpers.feature_enabled(config, pid, "potw"):
            continue
        if not helpers.interval_elapsed(state["last_potw"].get(pid), helpers.POTW_INTERVAL_DAYS, now):
            continue

        name = maps.to_name.get(pid, "Unknown")
        topic_timestamps = helpers.get_topic_timestamps(state, pid)
        gm_ids = helpers.gm_ids_for_campaign(config, pid)

        candidates = _gather_potw_candidates(topic_timestamps, gm_ids, week_ago, pid, state)
        if not candidates:
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

        boon_text = "\n\nChoose your boon:\n"
        for i, b in enumerate(chosen_boons):
            boon_text += f"\n{i + 1}. {b}\n"
        boon_text += "\nTap a button below, or type /chooseboon N in the " + name + " PBP topic."

        buttons = [
            {"text": f"Boon #{i + 1}", "callback_data": f"boon:{pid}:{i}"}
            for i in range(len(chosen_boons))
        ]

        print(f"POTW for {name}: {winner['first_name']} (avg gap {avg_gap_str})")
        msg_id = tg.send_message_with_buttons(group_id, bot_topic or chat_topic_id, base_message + boon_text, buttons)
        if msg_id:
            state["last_potw"][pid] = now.isoformat()
            state["pending_potw_boons"][pid] = {
                "message_id": msg_id,
                "winner_user_id": winner["user_id"],
                "campaign_name": name,
                "boons": chosen_boons,
                "base_message": base_message,
                "posted_at": now.isoformat(),
            }
