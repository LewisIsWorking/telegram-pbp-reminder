"""Shared fixtures for the never-posted-campaign tests.

Leading underscore so pytest does not collect it, following
``_test_checker_helpers`` and ``_test_state_isolation``.

Used by ``test_never_posted_is_the_silent_one`` (the bug itself) and
``test_never_posted_blast_radius`` (what the fix must not have changed).
The two files split on 2026-08-30 at the 200-line limit; extracting the
fixtures kept one definition of C10 rather than two that could drift.
"""

from datetime import datetime, timedelta, timezone

NOW = datetime(2026, 8, 30, 12, 0, tzinfo=timezone.utc)

# C10 The Junction, the campaign Lewis asked about. Configured
# 2026-08-13, first message 2026-08-30 12:07, so for 17 days it was a
# real campaign the bot had never seen a message in.
NEW = {"pbp_topic_ids": [146645], "chat_topic_id": 107186,
       "code": "C10", "name": "The Junction", "emoji": "🚦"}
OLD = {"pbp_topic_ids": [40585], "chat_topic_id": 1, "code": "C06",
       "name": "Kibwe", "emoji": "🦠"}


def config(*pairs) -> dict:
    return {"group_id": -100, "group_username": "Path_Wars",
            "topic_pairs": list(pairs)}


def state(**ages_in_days) -> dict:
    """State where each pid last posted N days before NOW."""
    return {"topics": {
        pid: {"last_message_time": (NOW - timedelta(days=d)).isoformat()}
        for pid, d in ages_in_days.items()}}


NEVER = {"topics": {}}
