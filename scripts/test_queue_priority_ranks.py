"""Tests for multi-level queue_priority ranks and the NO_PRIORITY sentinel.

Regression guard for the 2026-07-30 change: the sentinel used to be hardcoded
as 2, so a campaign given a real rank of 2 sorted level with unprioritised
campaigns instead of above them. C10 (rank 1) must outrank C01/C06 (rank 2),
and both must outrank everything unranked.
"""
import sys, os, json
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from commands.queue_format import NO_PRIORITY
from scheduled.queue_focus import pick_focus_pid

_CONFIG = Path(__file__).resolve().parent.parent / "config.json"


def _entry(t):
    return {"time": t, "name": "P", "preview": "x", "message_id": "1"}


def test_no_priority_sentinel_exceeds_real_ranks():
    assert NO_PRIORITY > 2
    # A rank-2 campaign must sort strictly before an unranked one.
    assert 2 < NO_PRIORITY


def test_rank_1_beats_rank_2_regardless_of_age():
    """C10 rank 1 with a fresh message beats C01 rank 2 with an old one."""
    scanned = {
        "146645": {"code": "C10", "campaign": "The Junction",
                   "entries": [_entry("2026-07-30 02:00:00")]},
        "25059": {"code": "C01", "campaign": "Doomsday Funtime",
                  "entries": [_entry("2026-07-01 02:00:00")]},
        "40585": {"code": "C06", "campaign": "Kibwe",
                  "entries": [_entry("2026-07-02 02:00:00")]},
    }
    pmap = {"146645": 1, "25059": 2, "40585": 2}
    assert pick_focus_pid(scanned, pmap) == "146645"


def test_rank_2_campaigns_still_beat_unranked():
    scanned = {
        "25059": {"code": "C01", "campaign": "Doomsday Funtime",
                  "entries": [_entry("2026-07-29 02:00:00")]},
        "52083": {"code": "C07", "campaign": "Hopeful End-Times",
                  "entries": [_entry("2026-07-08 02:00:00")]},
    }
    assert pick_focus_pid(scanned, {"25059": 2}) == "25059"


def test_equal_ranks_break_by_age():
    """C01 and C06 share rank 2, so the longest wait wins between them."""
    scanned = {
        "25059": {"code": "C01", "campaign": "Doomsday Funtime",
                  "entries": [_entry("2026-07-29 02:00:00")]},
        "40585": {"code": "C06", "campaign": "Kibwe",
                  "entries": [_entry("2026-07-27 02:00:00")]},
    }
    assert pick_focus_pid(scanned, {"25059": 2, "40585": 2}) == "40585"


def test_rank_1_absent_falls_through_to_rank_2():
    """When C10 has nothing waiting, the rank-2 pair take over."""
    scanned = {
        "25059": {"code": "C01", "campaign": "Doomsday Funtime",
                  "entries": [_entry("2026-07-29 02:00:00")]},
        "52083": {"code": "C07", "campaign": "Hopeful End-Times",
                  "entries": [_entry("2026-07-08 02:00:00")]},
    }
    pmap = {"146645": 1, "25059": 2}      # C10 configured but not waiting
    assert pick_focus_pid(scanned, pmap) == "25059"


# ── live config expectations ──────────────────────────────────────────────

def _pairs():
    return json.loads(_CONFIG.read_text(encoding="utf-8"))["topic_pairs"]


def test_config_ranks_are_ordered_as_intended():
    ranks = {p["code"]: p.get("queue_priority")
             for p in _pairs() if p.get("queue_priority") is not None}
    assert ranks.get("C01") == 2, ranks
    assert ranks.get("C06") == 2, ranks
    # C10 must outrank both once it is added to config.
    if "C10" in ranks:
        assert ranks["C10"] < ranks["C01"], ranks
        assert ranks["C10"] < ranks["C06"], ranks


def test_no_configured_rank_collides_with_the_sentinel():
    for p in _pairs():
        qp = p.get("queue_priority")
        if qp is not None and qp is not False:
            assert int(qp) < NO_PRIORITY, f"{p.get('code')} rank {qp}"
