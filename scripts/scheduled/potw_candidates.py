"""Who is eligible for Player of the Week.

Extracted from ``scheduled/potw.py`` on 2026-08-15, which had reached
204 lines. Candidate gathering is separable from the award-and-post
flow, and is the half worth reading on its own when a GM asks why a
particular player did not win.
"""

from datetime import datetime, timedelta, timezone

import helpers
from helpers import deduplicate_posts, timestamps_in_window
from helpers_pkg import campaigns


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
