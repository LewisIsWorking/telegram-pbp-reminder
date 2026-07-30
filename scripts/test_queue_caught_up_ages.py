"""Tests for campaign ages on the 'All caught up!' notification.

A cleared queue used to say only that there was nothing to reply to, which
told the GM nothing about which campaign had gone quiet. These pin the age
listing and its ordering.
"""
import sys, os
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

from scheduled.queue_silence import campaign_age_lines
from scheduled import queue_caught_up

NOW = datetime(2026, 7, 30, 12, 0, tzinfo=timezone.utc)


def _cfg():
    return {
        "group_id": -1001661053273,
        "group_username": "Path_Wars",
        "topic_pairs": [
            {"code": "C01", "name": "Doomsday", "emoji": "\U0001f4c6",
             "chat_topic_id": 1, "pbp_topic_ids": [25059]},
            {"code": "C09", "name": "Metal City", "emoji": "\U0001f916",
             "chat_topic_id": 2, "pbp_topic_ids": [107171]},
            {"code": "C06", "name": "Kibwe", "emoji": "\U0001f9a0",
             "chat_topic_id": 3, "pbp_topic_ids": [40585]},
        ],
    }


def _state(ages_hours):
    topics = {}
    for pid, hrs in ages_hours.items():
        topics[pid] = {"last_message_time": (NOW - timedelta(hours=hrs)).isoformat()}
    return {"topics": topics}


def test_lists_every_campaign_when_queue_is_clear():
    lines = campaign_age_lines(_cfg(), _state({"25059": 2, "107171": 50, "40585": 5}), {}, NOW)
    assert len(lines) == 3
    blob = "\n".join(lines)
    for code in ("C01", "C09", "C06"):
        assert code in blob


def test_sorted_longest_idle_first():
    lines = campaign_age_lines(_cfg(), _state({"25059": 2, "107171": 50, "40585": 5}), {}, NOW)
    assert "C09" in lines[0], lines      # 50h, quietest
    assert "C06" in lines[1], lines      # 5h
    assert "C01" in lines[2], lines      # 2h, most recent


def test_campaign_with_unreplied_entries_is_omitted():
    """Those already appear in the queue body, so they must not repeat here."""
    scanned = {"25059": {"entries": [{"time": "2026-07-30 10:00:00"}]}}
    lines = campaign_age_lines(_cfg(), _state({"25059": 2, "107171": 50, "40585": 5}),
                               scanned, NOW)
    assert not any("C01" in ln for ln in lines)
    assert len(lines) == 2


def test_untracked_campaign_is_skipped():
    lines = campaign_age_lines(_cfg(), _state({"25059": 2}), {}, NOW)
    assert len(lines) == 1
    assert "C01" in lines[0]


def test_links_are_included():
    lines = campaign_age_lines(_cfg(), _state({"25059": 2}), {}, NOW)
    assert "https://t.me/Path_Wars/25059" in lines[0]


# ── the posted message ───────────────────────────────────────────────────

def test_post_caught_up_appends_the_age_block():
    sent = {}

    def _fake(state, gid, tid, msgs, pin=False):
        sent["text"] = msgs[0]
        return True, 1

    with patch.object(queue_caught_up, "post_and_persist", _fake):
        queue_caught_up.post_caught_up({}, -1, 9, ["  a — last post 2h ago",
                                                   "  b — no posts for 9d"])
    assert "All caught up!" in sent["text"]
    assert "Time since last post" in sent["text"]
    assert "  a — last post 2h ago" in sent["text"]
    assert "  b — no posts for 9d" in sent["text"]


def test_post_caught_up_unchanged_without_ages():
    """Backwards compatible: no age lines means the original bare message."""
    sent = {}

    def _fake(state, gid, tid, msgs, pin=False):
        sent["text"] = msgs[0]
        return True, 1

    with patch.object(queue_caught_up, "post_and_persist", _fake):
        queue_caught_up.post_caught_up({}, -1, 9)
    assert sent["text"] == queue_caught_up.CAUGHT_UP_TEXT
    assert "Time since last post" not in sent["text"]
