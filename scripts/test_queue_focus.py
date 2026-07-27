"""Tests for scheduled/queue_focus.py — the 'reply to this next' follow-up.

Pins the selection rule: oldest-waiting campaign normally, but prioritised
campaigns (queue_priority) win outright whenever any of them is waiting.
"""
import sys, os
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(__file__))

from scheduled.queue_focus import (
    pick_focus_pid, build_focus_message, _oldest_entry,
)

NOW = datetime(2026, 7, 27, 12, 0, tzinfo=timezone.utc)


def _entry(t, name="Someone", preview="hello", mid="1", link=""):
    return {"time": t, "name": name, "preview": preview,
            "message_id": mid, "link": link}


def _cfg():
    return {"topic_pairs": [
        {"code": "C01", "emoji": "\U0001f4c6", "queue_priority": 1},
        {"code": "C06", "emoji": "\U0001f9a0", "queue_priority": 1},
        {"code": "C07", "emoji": "⭐"},
    ]}


# ── selection ────────────────────────────────────────────────────────────

def test_picks_oldest_when_no_priority_campaign_waiting():
    scanned = {
        "52083": {"code": "C07", "campaign": "Hopeful End-Times",
                  "entries": [_entry("2026-07-08 02:00:00")]},
        "66154": {"code": "C00", "campaign": "Riddleport",
                  "entries": [_entry("2026-07-07 08:00:00")]},
    }
    assert pick_focus_pid(scanned, {}) == "66154"  # C00 is older


def test_priority_campaign_beats_an_older_normal_campaign():
    """C01 waited 2h; C07 waited 19 days. C01 still wins."""
    scanned = {
        "52083": {"code": "C07", "campaign": "Hopeful End-Times",
                  "entries": [_entry("2026-07-08 02:00:00")]},
        "25059": {"code": "C01", "campaign": "Doomsday Funtime",
                  "entries": [_entry("2026-07-27 10:00:00")]},
    }
    assert pick_focus_pid(scanned, {"25059": 1}) == "25059"


def test_among_prioritised_the_longest_waiting_wins():
    """C06 and C01 are equal rank, so age decides between them."""
    scanned = {
        "25059": {"code": "C01", "campaign": "Doomsday Funtime",
                  "entries": [_entry("2026-07-27 10:00:00")]},
        "40585": {"code": "C06", "campaign": "Kibwe",
                  "entries": [_entry("2026-07-25 10:00:00")]},
        "52083": {"code": "C07", "campaign": "Hopeful End-Times",
                  "entries": [_entry("2026-07-08 02:00:00")]},
    }
    assert pick_focus_pid(scanned, {"25059": 1, "40585": 1}) == "40585"


def test_lower_rank_number_wins_when_ranks_differ():
    scanned = {
        "25059": {"code": "C01", "campaign": "Doomsday Funtime",
                  "entries": [_entry("2026-07-01 10:00:00")]},
        "40585": {"code": "C06", "campaign": "Kibwe",
                  "entries": [_entry("2026-07-26 10:00:00")]},
    }
    assert pick_focus_pid(scanned, {"25059": 2, "40585": 1}) == "40585"


def test_returns_none_when_nothing_queued():
    assert pick_focus_pid({}, {}) is None
    assert pick_focus_pid({"1": {"entries": []}}, {}) is None


def test_oldest_entry_helper():
    e_old, e_new = _entry("2026-07-01 00:00:00"), _entry("2026-07-20 00:00:00")
    assert _oldest_entry([e_new, e_old]) is e_old


# ── message ──────────────────────────────────────────────────────────────

def test_message_names_campaign_age_and_link():
    scanned = {"52083": {"code": "C07", "campaign": "Hopeful End-Times",
                         "entries": [
                             _entry("2026-07-08 02:00:00", name="Terra",
                                    preview="Lai stops beside Rune",
                                    link="https://t.me/Path_Wars/52083/165926"),
                             _entry("2026-07-20 02:00:00", name="Anthony"),
                         ]}}
    msg = build_focus_message(_cfg(), scanned, {}, NOW)
    assert "Reply to this next" in msg
    assert "C07: Hopeful End-Times" in msg
    assert "19d 10h" in msg                      # oldest entry, not newest
    assert "Terra" in msg                        # oldest entry's author
    assert "(2 unreplied in this campaign)" in msg
    assert "https://t.me/Path_Wars/52083/165926" in msg
    assert "Prioritised" not in msg              # C07 is not prioritised


def test_message_flags_a_prioritised_pick():
    scanned = {"25059": {"code": "C01", "campaign": "Doomsday Funtime",
                         "entries": [_entry("2026-07-27 10:00:00")]}}
    msg = build_focus_message(_cfg(), scanned, {"25059": 1}, NOW)
    assert "Prioritised campaign" in msg
    assert "C01: Doomsday Funtime" in msg


def test_empty_when_nothing_queued():
    assert build_focus_message(_cfg(), {}, {}, NOW) == ""


def test_survives_unparseable_timestamp():
    scanned = {"1": {"code": "C07", "campaign": "X",
                     "entries": [_entry("not-a-date")]}}
    msg = build_focus_message(_cfg(), scanned, {}, NOW)
    assert "Reply to this next" in msg
    assert "0h" in msg


def test_handles_missing_code_and_link():
    scanned = {"1": {"campaign": "Nameless", "entries": [_entry("2026-07-26 12:00:00")]}}
    msg = build_focus_message(_cfg(), scanned, {}, NOW)
    assert "Nameless" in msg
    assert "\U0001f517" not in msg               # no link line when absent
