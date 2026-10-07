"""Tests for scheduled/queue_always_first.py: Kibwe always goes first.

Lewis, 2026-10-07: "We should ALWAYS prioritise Kibwe." Replays the case that
prompted it: Kibwe's last post was the GM's "ROUND 2: ENEMY PHASE!", so
nothing there was unreplied, and the focus pointed at C07 for three days.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

from commands.queue_format import build_priority_map
from scheduled.queue_always_first import ALWAYS_FIRST_IDLE_HOURS, pick_always_first
from scheduled.queue_focus import build_focus_message, focus_key

NOW = datetime(2026, 10, 7, 3, 0, tzinfo=timezone.utc)
KIBWE = {"name": "Kibwe", "code": "C06", "emoji": "🦠", "pbp_topic_ids": [40585, 137075],
         "queue_priority": 0, "queue_always_first": True}
C07 = {"name": "Hopeful End-Times", "code": "C07", "emoji": "⭐", "pbp_topic_ids": [52083]}
C10 = {"name": "The Junction", "code": "C10", "pbp_topic_ids": [146645], "queue_priority": 1}
CONFIG = {"group_id": -100, "topic_pairs": [KIBWE, C07, C10]}

C07_WAITING = {"52083": {"code": "C07", "campaign": "Hopeful End-Times", "entries": [
    {"time": "2026-10-02 13:33:45", "name": "Terra", "preview": "I don't trust that",
     "message_id": "182398", "link": "https://t.me/Path_Wars/52083/182398"}]}}


def _state(kibwe_quiet_hours, others_quiet_hours=1):
    def ago(h):
        return (NOW - timedelta(hours=h)).isoformat()
    return {"topics": {"137075": {"last_message_time": ago(kibwe_quiet_hours)},
                       "52083": {"last_message_time": ago(others_quiet_hours)},
                       "146645": {"last_message_time": ago(others_quiet_hours)}}}


def _focus(scanned, state):
    return build_focus_message(CONFIG, scanned, build_priority_map(CONFIG), NOW, state=state)


def test_the_enemy_phase_case_puts_kibwe_first():
    """Kibwe quiet 56h after the GM's own post, C07 owed 4 days: Kibwe wins."""
    text = _focus(C07_WAITING, _state(kibwe_quiet_hours=56))
    assert "Post here next" in text and "C06: Kibwe" in text
    assert "Always first" in text and "C07" not in text


def test_focus_key_agrees_with_the_message():
    key = focus_key(C07_WAITING, build_priority_map(CONFIG), config=CONFIG,
                    state=_state(kibwe_quiet_hours=56), now=NOW)
    assert key == "idle:40585"


def test_a_turn_just_handed_to_players_does_not_jump_the_queue():
    text = _focus(C07_WAITING, _state(kibwe_quiet_hours=ALWAYS_FIRST_IDLE_HOURS - 1))
    assert "C07: Hopeful End-Times" in text


def test_kibwe_shows_even_with_nothing_owed_anywhere():
    assert "C06: Kibwe" in _focus({}, _state(kibwe_quiet_hours=30))


def test_unreplied_kibwe_beats_another_prioritised_campaign():
    scanned = dict(C07_WAITING)
    scanned["146645"] = {"code": "C10", "campaign": "The Junction", "entries": [
        {"time": "2026-10-01 00:00:00", "name": "Oscar", "preview": "after what?",
         "message_id": "1", "link": "l10"}]}
    scanned["40585"] = {"code": "C06", "campaign": "Kibwe", "entries": [
        {"time": "2026-10-07 02:00:00", "name": "Ryo", "preview": "Stride",
         "message_id": "2", "link": "l06"}]}
    text = _focus(scanned, _state(kibwe_quiet_hours=1))
    assert "Reply to this next" in text and "Kibwe" in text


def test_without_state_nothing_changes():
    assert pick_always_first(CONFIG, None, {}, NOW) is None


def test_real_config_flags_kibwe_and_ranks_it_first():
    path = os.path.join(os.path.dirname(__file__), "..", "config.json")
    with open(path, encoding="utf-8") as fh:
        pairs = json.load(fh)["topic_pairs"]
    kibwe = next(p for p in pairs if p.get("code") == "C06")
    assert kibwe.get("queue_always_first") is True
    ranks = build_priority_map({"topic_pairs": pairs})
    assert ranks[str(kibwe["pbp_topic_ids"][0])] == min(ranks.values())
