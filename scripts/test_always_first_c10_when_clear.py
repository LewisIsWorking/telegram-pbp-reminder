"""C10 The Junction only goes first when the chronological queue is empty.

Lewis, 2026-11-14: "I think the junction should be updated to only be in the
priority queue if the chronological queue is empty." C10 keeps
``queue_always_first`` and its rank (C06 > C01 > C10 > C11), plus
``queue_always_first_when_clear``:

  * while any campaign owes a reply, a quiet C10 is never the focus;
  * an owed C10 reply waits its turn by age, with no priority rank;
  * with nothing owed anywhere, a quiet C10 still ranks after C06 and C01.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))

from commands.queue_format import build_priority_map
from scheduled.queue_always_first import pick_always_first
from scheduled.queue_focus import pick_focus_pid

NOW = datetime(2026, 11, 14, 12, 0, tzinfo=timezone.utc)
CODES = ("C06", "C01", "C10", "C11", "C07")

with open(os.path.join(os.path.dirname(__file__), "..", "config.json"),
          encoding="utf-8") as _fh:
    REAL = json.load(_fh)
PAIRS = {p.get("code"): p for p in REAL["topic_pairs"]}
PIDS = {c: str(PAIRS[c]["pbp_topic_ids"][0]) for c in CODES}
CONFIG = {"group_id": REAL["group_id"], "group_username": REAL["group_username"],
          "topic_pairs": [PAIRS[c] for c in CODES]}


def _owed(code, days):
    pid = PIDS[code]
    return {pid: {"code": code, "campaign": PAIRS[code]["name"], "entries": [
        {"time": (NOW - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S"),
         "name": "Player", "preview": "your move", "message_id": "9",
         "link": f"https://t.me/Path_Wars/{pid}/9"}]}}


def _state(**quiet_hours):
    return {"topics": {pid: {"last_message_time":
                             (NOW - timedelta(hours=quiet_hours.get(code, 1))).isoformat()}
                       for code, pid in PIDS.items()}}


def test_real_config_flags_only_c10():
    flagged = [p.get("code") for p in REAL["topic_pairs"]
               if p.get("queue_always_first_when_clear")]
    assert flagged == ["C10"]
    assert PAIRS["C10"].get("queue_always_first") is True
    assert PAIRS["C10"].get("queue_priority") == 2


def test_c10_is_left_out_of_the_priority_map():
    assert PIDS["C10"] not in build_priority_map(CONFIG)
    assert build_priority_map(CONFIG)[PIDS["C06"]] == 0


def test_a_quiet_c10_does_not_jump_an_owed_reply():
    assert pick_always_first(CONFIG, _state(C10=200), _owed("C07", 5), NOW) is None


def test_a_quiet_c10_goes_first_when_nothing_is_owed():
    first = pick_always_first(CONFIG, _state(C10=31), {}, NOW)
    assert first is not None and first.pid == PIDS["C10"]


def test_with_nothing_owed_c06_and_c01_still_outrank_c10():
    assert pick_always_first(CONFIG, _state(C01=31, C10=200), {}, NOW).pid == PIDS["C01"]
    assert pick_always_first(CONFIG, _state(C06=31, C10=200), {}, NOW).pid == PIDS["C06"]


def test_an_owed_c10_reply_waits_its_turn_by_age():
    scanned = {**_owed("C10", 1), **_owed("C07", 5)}
    ranks = build_priority_map(CONFIG)
    assert pick_focus_pid(scanned, ranks) == PIDS["C07"]
