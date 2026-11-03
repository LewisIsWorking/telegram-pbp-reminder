"""C06, C01 and C10 all go first after 24 quiet hours, in rank order.

Lewis, 2026-11-03: "C01, C06 and C10 I think they should all be 24 hours.
C06 > C01 > C10." So all three carry ``queue_always_first``, the idle wait
is 24h for each, and when several could be the focus the rank decides, not
which has been quiet longest. A prioritised campaign with a real owed reply
still competes by the same rank, so an owed C01 reply beats a quiet C10, and
a quiet C06 beats an owed C01 reply.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

from commands.queue_format import build_priority_map
from scheduled.queue_always_first import ALWAYS_FIRST_IDLE_HOURS, pick_always_first
from scheduled.queue_focus import OLDEST_LABEL, build_focus_message, focus_key

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
C06 = {"name": "Kibwe", "code": "C06", "emoji": "🦠", "pbp_topic_ids": [40585],
       "queue_priority": 0, "queue_always_first": True}
C01 = {"name": "Doomsday Funtime", "code": "C01", "emoji": "📆", "pbp_topic_ids": [25059],
       "queue_priority": 1, "queue_always_first": True}
C10 = {"name": "The Junction", "code": "C10", "emoji": "🚦", "pbp_topic_ids": [146645],
       "queue_priority": 2, "queue_always_first": True}
C07 = {"name": "Hopeful End-Times", "code": "C07", "emoji": "⭐", "pbp_topic_ids": [52083]}
CONFIG = {"group_id": -100, "topic_pairs": [C06, C01, C10, C07]}
RANKS = build_priority_map(CONFIG)


def _at(hours_ago):
    return (NOW - timedelta(hours=hours_ago)).strftime("%Y-%m-%d %H:%M:%S")


def _owed(pid, code, name, hours, who="Terra"):
    return {pid: {"code": code, "campaign": name, "entries": [
        {"time": _at(hours), "name": who, "preview": "your move",
         "message_id": "9", "link": f"https://t.me/Path_Wars/{pid}/9"}]}}


C07_OWED = _owed("52083", "C07", "Hopeful End-Times", 5 * 24)
C01_OWED = _owed("25059", "C01", "Doomsday Funtime", 3)


def _state(**quiet_hours):
    """Hours since the last post per campaign code; anything unnamed posted 1h ago."""
    pids = {"C06": "40585", "C01": "25059", "C10": "146645", "C07": "52083"}
    return {"topics": {pid: {"last_message_time": (NOW - timedelta(hours=quiet_hours.get(code, 1))).isoformat()}
                       for code, pid in pids.items()}}


def _focus(scanned, state):
    text = build_focus_message(CONFIG, scanned, RANKS, NOW, state=state)
    return text.split(OLDEST_LABEL)[0], text


def _key(scanned, state):
    return focus_key(scanned, RANKS, config=CONFIG, state=state, now=NOW)


def test_the_idle_wait_is_24_hours():
    assert ALWAYS_FIRST_IDLE_HOURS == 24


def test_c01_quiet_23h_does_not_jump_an_owed_reply_elsewhere():
    priority, _ = _focus(C07_OWED, _state(C01=23))
    assert "C07: Hopeful End-Times" in priority


def test_c01_quiet_25h_goes_first_over_an_owed_non_priority_reply():
    priority, text = _focus(C07_OWED, _state(C01=25))
    assert "Post here next" in priority and "C01: Doomsday Funtime" in priority
    assert "C07: Hopeful End-Times" in text.split(OLDEST_LABEL, 1)[1]
    assert _key(C07_OWED, _state(C01=25)) == "idle:25059"


def test_c10_goes_first_too():
    priority, _ = _focus(C07_OWED, _state(C10=30))
    assert "C10: The Junction" in priority


def test_a_quiet_c06_beats_an_owed_reply_in_c01():
    scanned = {**C07_OWED, **C01_OWED}
    priority, text = _focus(scanned, _state(C06=25))
    assert "C06: Kibwe" in priority and "C01" not in priority
    assert "C07: Hopeful End-Times" in text.split(OLDEST_LABEL, 1)[1]
    assert _key(scanned, _state(C06=25)) == "idle:40585"


def test_an_owed_c01_reply_beats_a_quiet_c10():
    scanned = {**C07_OWED, **C01_OWED}
    priority, _ = _focus(scanned, _state(C10=100))
    assert "Reply to this next" in priority and "C01: Doomsday Funtime" in priority
    assert _key(scanned, _state(C10=100)) == "https://t.me/Path_Wars/25059/9"


def test_rank_not_quietness_decides_between_quiet_campaigns():
    """C10 has been quiet longer, but C01 outranks it."""
    first = pick_always_first(CONFIG, _state(C01=30, C10=200), C07_OWED, NOW)
    assert first.pid == "25059"
    first = pick_always_first(CONFIG, _state(C06=25, C01=30, C10=200), C07_OWED, NOW)
    assert first.pid == "40585"


def test_real_config_ranks_c06_then_c01_then_c10_all_always_first():
    path = os.path.join(os.path.dirname(__file__), "..", "config.json")
    with open(path, encoding="utf-8") as fh:
        pairs = {p.get("code"): p for p in json.load(fh)["topic_pairs"]}
    assert [pairs[c]["queue_priority"] for c in ("C06", "C01", "C10")] == [0, 1, 2]
    assert all(pairs[c].get("queue_always_first") is True for c in ("C06", "C01", "C10"))
