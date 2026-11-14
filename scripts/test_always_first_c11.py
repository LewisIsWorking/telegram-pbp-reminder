"""C11 Dark Pockets joins the always-first ranks, after C10.

Lewis, 2026-11-03: "C11 should be added to the next priority of the
priority queue: C06 > C01 > C10 > C11". So C11 carries rank 3 and
``queue_always_first``, and follows the same 30-hour rule as the other three.

C11 runs in its own Telegram group (-1003496373617), not Path_Wars, so these
tests use the REAL config.json pairs and also check that the always-first
message links to C11's own group (t.me/c/3496373617/1242), never to
t.me/Path_Wars/1242.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

from commands.queue_format import build_priority_map
from scheduled.queue_always_first import always_first_message, pick_always_first
from scheduled.queue_focus import OLDEST_LABEL, build_focus_message, focus_key

NOW = datetime(2026, 11, 3, 12, 0, tzinfo=timezone.utc)
CODES = ("C06", "C01", "C10", "C11")

with open(os.path.join(os.path.dirname(__file__), "..", "config.json"),
          encoding="utf-8") as _fh:
    REAL = json.load(_fh)
PAIRS = {p.get("code"): p for p in REAL["topic_pairs"]}
PIDS = {c: str(PAIRS[c]["pbp_topic_ids"][0]) for c in (*CODES, "C07")}
CONFIG = {"group_id": REAL["group_id"], "group_username": REAL["group_username"],
          "topic_pairs": [PAIRS[c] for c in (*CODES, "C07")]}
RANKS = build_priority_map(CONFIG)

C07_OWED = {PIDS["C07"]: {"code": "C07", "campaign": PAIRS["C07"]["name"], "entries": [
    {"time": (NOW - timedelta(days=5)).strftime("%Y-%m-%d %H:%M:%S"),
     "name": "Terra", "preview": "your move", "message_id": "9",
     "link": f"https://t.me/Path_Wars/{PIDS['C07']}/9"}]}}


def _state(**quiet_hours):
    """Hours since the last post per campaign code; anything unnamed posted 1h ago."""
    return {"topics": {pid: {"last_message_time":
                             (NOW - timedelta(hours=quiet_hours.get(code, 1))).isoformat()}
                       for code, pid in PIDS.items()}}


def test_real_config_ranks_c06_c01_c10_c11_all_always_first():
    ranks = [PAIRS[c].get("queue_priority") for c in CODES]
    assert ranks == [0, 1, 2, 3]
    assert all(PAIRS[c].get("queue_always_first") is True for c in CODES)
    others = [p.get("queue_priority") for p in REAL["topic_pairs"]
              if p.get("code") not in CODES and p.get("queue_priority") is not None]
    assert all(isinstance(r, int) and r > 3 for r in others), others


def test_a_quiet_c11_beats_an_owed_non_priority_reply():
    state = _state(C11=31)
    first = pick_always_first(CONFIG, state, C07_OWED, NOW)
    assert first is not None and first.pid == PIDS["C11"]
    text = build_focus_message(CONFIG, C07_OWED, RANKS, NOW, state=state)
    priority = text.split(OLDEST_LABEL)[0]
    assert "Post here next" in priority and "C11: Dark Pockets" in priority
    assert focus_key(C07_OWED, RANKS, config=CONFIG, state=state, now=NOW) == f"idle:{PIDS['C11']}"


def test_a_quiet_c11_loses_to_a_quiet_c10():
    first = pick_always_first(CONFIG, _state(C10=31, C11=200), C07_OWED, NOW)
    assert first.pid == PIDS["C10"]


def test_c11_quiet_29h_does_not_jump_an_owed_reply():
    assert pick_always_first(CONFIG, _state(C11=29), C07_OWED, NOW) is None


def test_c11_always_first_message_links_to_its_own_group():
    first = pick_always_first(CONFIG, _state(C11=31), C07_OWED, NOW)
    msg = always_first_message(first)
    assert "https://t.me/c/3496373617/1242" in msg
    assert "Path_Wars" not in msg
