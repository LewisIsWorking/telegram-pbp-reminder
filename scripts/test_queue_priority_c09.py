"""C09 is the last prioritised campaign.

It sorts after every other prioritised campaign but ahead of the unranked
ones, whatever their age.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from commands.queue_format import NO_PRIORITY, build_priority_map
from scheduled.queue_focus import pick_focus_pid

_CONFIG = Path(__file__).resolve().parent.parent / "config.json"


def _config():
    return json.loads(_CONFIG.read_text(encoding="utf-8"))


def _pid(config, code):
    pair = next(p for p in config["topic_pairs"] if p.get("code") == code)
    return str(pair["pbp_topic_ids"][0])


def _entry(t):
    return {"time": t, "name": "P", "preview": "x", "message_id": "1"}


def test_c09_ranks_below_every_other_prioritised_campaign():
    config = _config()
    pmap = build_priority_map(config)
    c09 = pmap[_pid(config, "C09")]
    others = [r for pid, r in pmap.items() if pid != _pid(config, "C09")]
    assert c09 < NO_PRIORITY
    assert all(r < c09 for r in others)


def test_c09_beats_an_older_c00_reply():
    config = _config()
    c09, c00 = _pid(config, "C09"), _pid(config, "C00")
    scanned = {
        c09: {"code": "C09", "campaign": "Metal City",
              "entries": [_entry("2026-11-01 02:00:00")]},
        c00: {"code": "C00", "campaign": "Riddleport",
              "entries": [_entry("2026-10-01 02:00:00")]},
    }
    assert pick_focus_pid(scanned, build_priority_map(config)) == c09


def test_another_prioritised_campaign_beats_c09():
    config = _config()
    c09, c11 = _pid(config, "C09"), _pid(config, "C11")
    scanned = {
        c09: {"code": "C09", "campaign": "Metal City",
              "entries": [_entry("2026-10-01 02:00:00")]},
        c11: {"code": "C11", "campaign": "Dark Pockets",
              "entries": [_entry("2026-11-06 02:00:00")]},
    }
    assert pick_focus_pid(scanned, build_priority_map(config)) == c11


def test_an_owed_c10_reply_no_longer_beats_c09():
    """Lewis, 2026-11-14: C10 only jumps the queue when it is empty, so an
    owed C10 reply has no rank and the older prioritised C09 reply wins."""
    config = _config()
    c09, c10 = _pid(config, "C09"), _pid(config, "C10")
    scanned = {
        c09: {"code": "C09", "campaign": "Metal City",
              "entries": [_entry("2026-11-06 02:00:00")]},
        c10: {"code": "C10", "campaign": "The Junction",
              "entries": [_entry("2026-10-01 02:00:00")]},
    }
    assert pick_focus_pid(scanned, build_priority_map(config)) == c09


def test_oldest_waiting_line_stays_chronological():
    """C09 jumps the priority pick, but the "Oldest waiting" line still names
    the older C00 post."""
    from scheduled.queue_oldest_waiting import pick_oldest_waiting
    config = _config()
    c09, c00 = _pid(config, "C09"), _pid(config, "C00")
    scanned = {
        c09: {"code": "C09", "campaign": "Metal City",
              "entries": [_entry("2026-11-01 02:00:00")]},
        c00: {"code": "C00", "campaign": "Riddleport",
              "entries": [_entry("2026-10-01 02:00:00")]},
    }
    picked = pick_oldest_waiting(scanned)
    assert picked[0] == c00
