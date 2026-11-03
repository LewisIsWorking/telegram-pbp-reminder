"""The GM queue footer names the oldest post waiting, beside the priority pick.

Lewis, 2026-11-03: the footer's "Post here next" is the PRIORITY pick (Kibwe is
always first, prioritised campaigns jump the age queue, a silent campaign can
win). He also wants the CHRONOLOGICAL next: the single oldest unreplied post
across every campaign, with its campaign, poster, age and link. When the two
point at the same post, one line says so instead of repeating it.

The priority pick itself must not move: these tests check the extra line only.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

from commands.queue_format import build_priority_map
from scheduled.queue_focus import (OLDEST_LABEL, SAME_POST_LINE,
                                   build_focus_message, focus_key,
                                   pick_oldest_waiting)

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
KIBWE = {"name": "Kibwe", "code": "C06", "emoji": "🦠", "pbp_topic_ids": [40585],
         "queue_priority": 0, "queue_always_first": True}
C04 = {"name": "Magni Guard", "code": "C04", "emoji": "🛡", "pbp_topic_ids": [144765]}
C07 = {"name": "Hopeful End-Times", "code": "C07", "emoji": "⭐", "pbp_topic_ids": [52083]}
C10 = {"name": "The Junction", "code": "C10", "pbp_topic_ids": [146645], "queue_priority": 1}
CONFIG = {"group_id": -100, "topic_pairs": [KIBWE, C04, C07, C10]}

C04_LINK = "https://t.me/Path_Wars/144765/190001"
C07_LINK = "https://t.me/Path_Wars/52083/190500"


def _at(hours_ago):
    return (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%d %H:%M:%S")


def _scanned(c04_hours=20 * 24 + 17, c07_hours=3 * 24):
    return {
        "144765": {"code": "C04", "campaign": "Magni Guard", "entries": [
            {"time": _at(c04_hours), "name": "Mira", "preview": "We hold the gate",
             "message_id": "190001", "link": C04_LINK}]},
        "52083": {"code": "C07", "campaign": "Hopeful End-Times", "entries": [
            {"time": _at(c07_hours), "name": "Terra", "preview": "I don't trust that",
             "message_id": "190500", "link": C07_LINK}]},
    }


def _state(kibwe_quiet_hours):
    ago = (NOW - timedelta(hours=kibwe_quiet_hours)).isoformat()
    recent = (NOW - timedelta(hours=1)).isoformat()
    return {"topics": {"40585": {"last_message_time": ago},
                       "144765": {"last_message_time": recent},
                       "52083": {"last_message_time": recent},
                       "146645": {"last_message_time": recent}}}


def _focus(scanned, state):
    return build_focus_message(CONFIG, scanned, build_priority_map(CONFIG), NOW, state=state)


def _priority_part(text):
    return text.split(OLDEST_LABEL)[0]


def test_always_first_pick_also_names_the_oldest_post_waiting():
    """Today's case: Kibwe is the priority, C04's 20d 17h post is the oldest."""
    text = _focus(_scanned(), _state(kibwe_quiet_hours=25))
    assert "🎯 Post here next" in text and "C06: Kibwe" in text
    oldest = text.split(OLDEST_LABEL, 1)[1]
    assert "🛡 C04: Magni Guard" in oldest
    assert "Mira" in oldest and "20d 17h" in oldest
    assert C04_LINK in oldest
    assert "C07" not in text


def test_the_priority_pick_is_unchanged_by_the_new_line():
    text = _focus(_scanned(), _state(kibwe_quiet_hours=25))
    assert "C04" not in _priority_part(text)
    key = focus_key(_scanned(), build_priority_map(CONFIG), config=CONFIG,
                    state=_state(kibwe_quiet_hours=25), now=NOW)
    assert key == "idle:40585"


def test_a_prioritised_pick_still_wins_and_the_older_post_is_named():
    scanned = _scanned()
    scanned["146645"] = {"code": "C10", "campaign": "The Junction", "entries": [
        {"time": _at(2), "name": "Oscar", "preview": "after what?",
         "message_id": "1", "link": "https://t.me/Path_Wars/146645/1"}]}
    text = _focus(scanned, _state(kibwe_quiet_hours=1))
    assert "Reply to this next" in _priority_part(text)
    assert "C10: The Junction" in _priority_part(text)
    assert "C04: Magni Guard" in text.split(OLDEST_LABEL, 1)[1]


def test_one_line_when_both_point_at_the_same_post():
    text = _focus(_scanned(), _state(kibwe_quiet_hours=1))
    assert "Reply to this next" in text and "C04: Magni Guard" in text
    assert OLDEST_LABEL not in text
    assert SAME_POST_LINE in text
    assert text.count(C04_LINK) == 1


def test_no_oldest_line_when_nothing_is_waiting():
    text = _focus({}, _state(kibwe_quiet_hours=30))
    assert "C06: Kibwe" in text
    assert OLDEST_LABEL not in text and SAME_POST_LINE not in text


def test_pick_oldest_waiting_crosses_campaigns():
    pid, entry = pick_oldest_waiting(_scanned(c04_hours=5, c07_hours=50))
    assert pid == "52083" and entry["name"] == "Terra"
    assert pick_oldest_waiting({}) is None
    assert pick_oldest_waiting({"1": {"entries": []}}) is None


def test_the_old_label_stays_for_tools_that_look_for_it():
    """pbp_queue.py and the DM key read the message; keep the priority label."""
    assert "🎯 Post here next" in _focus(_scanned(), _state(kibwe_quiet_hours=25))
