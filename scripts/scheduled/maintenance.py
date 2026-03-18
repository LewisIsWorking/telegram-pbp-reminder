"""Archive, cleanup, and recruitment."""

import json
from datetime import datetime, timedelta, timezone

import helpers
from helpers import (
    build_topic_maps, deduplicate_posts, timestamps_in_window,
)
import telegram as tg


def archive_weekly_data(config: dict, state: dict, *, now: datetime | None = None, maps=None) -> None:
    """Archive weekly summaries to a JSON file in the repo.

    Stores compact per-campaign stats keyed by ISO week (e.g. '2026-W07').
    The file is committed back to the repo by the GitHub Actions workflow,
    giving full git history and no gist size concerns.
    """
    now = now or datetime.now(timezone.utc)

    # Use last week's ISO week number (since current week is still in progress)
    last_week = now - timedelta(days=7)
    year, week_num, _ = last_week.isocalendar()
    week_key = f"{year}-W{week_num:02d}"

    # Check if we already archived this week (tracked in gist state)
    if state.get("last_archived_week") == week_key:
        return

    # Load existing archive from repo file
    helpers.ARCHIVE_PATH.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(helpers.ARCHIVE_PATH) as f:
            archive = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        archive = {}

    week_start = now - timedelta(days=now.weekday() + 7)  # Start of last week (Monday)
    week_end = week_start + timedelta(days=7)

    maps = build_topic_maps(config)
    all_campaigns = helpers.players_by_campaign(state)

    for pid, name in maps.to_name.items():
        topic_timestamps = helpers.get_topic_timestamps(state, pid)
        gm_ids = helpers.gm_ids_for_campaign(config, pid)

        gm_posts = 0
        player_posts = 0
        player_counts = {}
        player_post_times = []
        player_details = {}  # name -> {posts, sessions (unique days), timestamps}

        for uid, timestamps in topic_timestamps.items():
            is_gm = uid in gm_ids
            player_info = helpers.get_player(state, pid, uid)

            user_sessions = deduplicate_posts(
                timestamps_in_window(timestamps, week_start, week_end)
            )
            session_count = len(user_sessions)

            if is_gm:
                gm_posts += session_count
            else:
                player_posts += session_count
                player_post_times.extend(user_sessions)
                if session_count > 0:
                    p_name = helpers.player_mention(player_info)
                    player_counts[p_name] = player_counts.get(p_name, 0) + session_count
                    # Collect per-player detail
                    unique_days = len({ts.date() for ts in user_sessions})
                    p_gap = helpers.avg_gap_hours(sorted(user_sessions))
                    player_details[p_name] = {
                        "posts": session_count,
                        "sessions": unique_days,
                        "avg_gap_h": round(p_gap, 1) if p_gap is not None else None,
                        "words": state.get("word_counts", {}).get(pid, {}).get(uid, 0),
                    }

        # Calculate player avg gap
        raw_gap = helpers.avg_gap_hours(sorted(player_post_times))
        player_avg_gap = round(raw_gap, 1) if raw_gap is not None else None

        active_players = len([p for p in all_campaigns.get(pid, []) if p.get("user_id", "") not in gm_ids])

        archive_key = f"{pid}:{week_key}"
        archive[archive_key] = {
            "campaign": name,
            "week": week_key,
            "gm_posts": gm_posts,
            "player_posts": player_posts,
            "total_posts": gm_posts + player_posts,
            "player_avg_gap_h": player_avg_gap,
            "active_players": active_players,
            "total_words": sum(state.get("word_counts", {}).get(pid, {}).values()),
            "top_players": dict(sorted(
                player_counts.items(), key=lambda x: x[1], reverse=True
            )[:5]),
            "player_breakdown": player_details,
        }

    # Write archive to repo file
    with open(helpers.ARCHIVE_PATH, "w") as f:
        json.dump(archive, f, indent=2)

    state["last_archived_week"] = week_key
    print(f"Archived weekly data for {week_key} to {helpers.ARCHIVE_PATH}")


def cleanup_timestamps(state: dict) -> None:
    """Prune old timestamps to prevent gist from growing."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()

    for pid in list(state.get("post_timestamps", {}).keys()):
        for uid in list(state["post_timestamps"][pid].keys()):
            filtered = [
                ts for ts in state["post_timestamps"][pid][uid]
                if ts >= cutoff
            ]
            if filtered:
                state["post_timestamps"][pid][uid] = filtered
            else:
                del state["post_timestamps"][pid][uid]
        if not state["post_timestamps"][pid]:
            del state["post_timestamps"][pid]


def check_recruitment_needs(config: dict, state: dict, *, now: datetime | None = None, maps=None) -> None:
    """If a campaign has fewer than helpers.REQUIRED_PLAYERS, post a notice."""
    group_id = config["group_id"]
    bot_topic = config.get("bot_topic_id")
    now = now or datetime.now(timezone.utc)

    maps = maps or build_topic_maps(config)
    all_campaigns = helpers.players_by_campaign(state)

    for pid, chat_topic_id in maps.to_chat.items():
        name = maps.to_name[pid]

        if not helpers.feature_enabled(config, pid, "recruitment"):
            continue

        # Check interval
        if not helpers.interval_elapsed(state["last_recruitment_check"].get(pid), helpers.RECRUITMENT_INTERVAL_DAYS, now):
            continue

        # Count active players (excluding GM)
        gm_ids = helpers.gm_ids_for_campaign(config, pid)
        campaign_players = all_campaigns.get(pid, [])
        active = [
            helpers.player_mention(p)
            for p in campaign_players
            if p.get("user_id", "") not in gm_ids
        ]

        player_count = len(active)
        needed = helpers.REQUIRED_PLAYERS - player_count

        if needed <= 0:
            # Full roster, reset timer
            state["last_recruitment_check"][pid] = now.isoformat()
            continue

        # Build roster display
        if active:
            roster_lines = "\n".join(f"- {p}" for p in active)
            roster_section = f"Current roster ({player_count}/{helpers.REQUIRED_PLAYERS}):\n{roster_lines}"
        else:
            roster_section = f"Current roster: 0/{helpers.REQUIRED_PLAYERS} (no active players)"

        message = (
            f"📢 {name} needs {needed} more player{'s' if needed != 1 else ''}!\n\n"
            f"{roster_section}\n\n"
            f"Know anyone who'd like to join? Send them to the recruitment topic!"
        )

        print(f"Recruitment notice for {name}: {player_count}/{helpers.REQUIRED_PLAYERS}")
        if tg.send_message(group_id, bot_topic or chat_topic_id, message):
            state["last_recruitment_check"][pid] = now.isoformat()
