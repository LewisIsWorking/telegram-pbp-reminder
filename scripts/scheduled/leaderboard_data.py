"""Leaderboard data collection."""

from datetime import datetime, timedelta

import helpers
from helpers import (
    build_topic_maps, deduplicate_posts, timestamps_in_window,
)


def _gather_leaderboard_stats(config: dict, state: dict, now: datetime) -> tuple[list, dict, list]:
    """Collect per-campaign stats, global player rankings, and top streaks for the leaderboard."""
    seven_days_ago = now - timedelta(days=7)
    three_days_ago = now - timedelta(days=3)
    six_days_ago = now - timedelta(days=6)

    campaign_stats = []
    global_player_posts = {}
    all_streaks = []

    maps = build_topic_maps(config)

    for pid, name in maps.to_name.items():
        topic_timestamps = helpers.get_topic_timestamps(state, pid)
        gm_ids = helpers.gm_ids_for_campaign(config, pid)

        gm_7d = 0
        player_7d = 0
        posts_recent_3d = 0
        posts_prev_3d = 0
        player_post_counts = {}
        all_post_times_7d = []
        player_post_times_7d = []

        for uid, timestamps in topic_timestamps.items():
            is_gm = uid in gm_ids
            player_info = helpers.get_player(state, pid, uid)

            user_7d_posts = timestamps_in_window(timestamps, seven_days_ago)
            posts_recent_3d += len(timestamps_in_window(timestamps, three_days_ago))
            posts_prev_3d += len(timestamps_in_window(timestamps, six_days_ago, three_days_ago))

            user_sessions = deduplicate_posts(user_7d_posts)
            session_count = len(user_sessions)

            all_post_times_7d.extend(user_sessions)
            if is_gm:
                gm_7d += session_count
            else:
                player_7d += session_count
                player_post_times_7d.extend(user_sessions)
                if session_count > 0:
                    full = helpers.player_full_name(player_info)
                    player_post_counts.setdefault(uid, {
                        "full_name": full,
                        "username": player_info.get("username", ""),
                        "count": 0,
                    })
                    player_post_counts[uid]["count"] += session_count

            # Collect streak data (players only)
            if not is_gm:
                streak = helpers.calc_streak(timestamps, now)
                if streak >= 2 and player_info:
                    all_streaks.append({
                        "name": helpers.player_full_name(player_info),
                        "streak": streak,
                        "campaign": name,
                    })

        total_7d = gm_7d + player_7d

        # Average response gap (all posts)
        all_post_times_7d.sort()
        all_avg = helpers.avg_gap_hours(all_post_times_7d)
        avg_gap_str = f"{all_avg:.1f}h" if all_avg is not None else "N/A"

        # Player-only average gap
        player_post_times_7d.sort()
        player_avg_gap = helpers.avg_gap_hours(player_post_times_7d)
        player_avg_gap_str = f"{player_avg_gap:.1f}h" if player_avg_gap is not None else "N/A"

        # Last post across all users
        all_ts = [ts for tss in topic_timestamps.values() for ts in tss]
        last_post_time = max((datetime.fromisoformat(ts) for ts in all_ts), default=None) if all_ts else None

        last_post_str, days_since_last = helpers.fmt_brief_relative(now, last_post_time)
        trend = helpers.trend_icon(posts_recent_3d, posts_prev_3d)

        top_players = sorted(
            player_post_counts.values(),
            key=lambda p: p["count"],
            reverse=True,
        )

        for uid, pdata in player_post_counts.items():
            entry = global_player_posts.setdefault(uid, {
                "full_name": pdata["full_name"],
                "username": pdata.get("username", ""),
                "count": 0,
                "campaigns": 0,
            })
            entry["count"] += pdata["count"]
            entry["campaigns"] += 1

        campaign_stats.append({
            "name": name,
            "total_7d": total_7d,
            "player_7d": player_7d,
            "gm_7d": gm_7d,
            "trend_icon": trend,
            "avg_gap_str": avg_gap_str,
            "player_avg_gap": player_avg_gap,
            "player_avg_gap_str": player_avg_gap_str,
            "last_post_str": last_post_str,
            "days_since_last": days_since_last,
            "top_players": top_players,
        })

    return campaign_stats, global_player_posts, all_streaks
