"""Tests for opt-in active-roster filtering of session-poll rosters.

Background: the poll "waiting" list and vote denominator were built from the
static ``poll_user_ids`` config array, so players who had left/gone inactive
kept getting pinged (Lewis flagged C01 pinging three ex-players). The fix adds
``commands.roster.active_poll_uids`` which, when a campaign opts in via
``poll_roster_filter``, trims the list to the active roster. The flag is opt-in
because campaigns in a separate Telegram group (C11) have no tracked roster and
must keep the full list.
"""
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(__file__))


def _recent():
    return (datetime.now(timezone.utc) - timedelta(days=1)
            ).strftime("%Y-%m-%d %H:%M:%S")


def _stale():
    return (datetime.now(timezone.utc) - timedelta(days=60)
            ).strftime("%Y-%m-%d %H:%M:%S")


def _pair(filter_on):
    p = {"code": "C01", "pbp_topic_ids": [100],
         "poll_user_ids": [1, 2, 3],
         "poll_user_names": {}}
    if filter_on:
        p["poll_roster_filter"] = True
    return p


def _config(pair):
    # uid 2 is globally permanent
    return {"topic_pairs": [pair], "permanent_user_ids": [2]}


def _state():
    return {"players": {
        "100:1": {"user_id": "1", "username": "alice", "first_name": "Alice",
                  "pbp_topic_id": "100", "last_post_time": _recent()},
        "100:2": {"user_id": "2", "username": "bob", "first_name": "Bob",
                  "pbp_topic_id": "100", "last_post_time": _stale()},  # perm
        "100:3": {"user_id": "3", "username": "charlie", "first_name": "Charlie",
                  "pbp_topic_id": "100", "last_post_time": _stale()},  # inactive
    }}


def test_passthrough_when_flag_off():
    from commands.roster import active_poll_uids
    pair = _pair(filter_on=False)
    assert active_poll_uids(pair, _config(pair), _state()) == ["1", "2", "3"]


def test_filters_to_active_roster_when_flag_on():
    from commands.roster import active_poll_uids
    pair = _pair(filter_on=True)
    # alice active (recent), bob permanent → kept; charlie stale non-perm → dropped
    assert active_poll_uids(pair, _config(pair), _state()) == ["1", "2"]


def test_waiting_list_excludes_inactive_when_flag_on():
    from dispatch.poll_tally import _waiting_for_code
    pair = _pair(filter_on=True)
    state = _state()
    state["session_poll"] = {"C01": {"voted_uids": []}}
    waiting = _waiting_for_code("C01", _config(pair), state)
    assert "@alice" in waiting and "@bob" in waiting
    assert "@charlie" not in waiting


def test_tally_denominator_uses_filtered_count():
    from dispatch.poll_tally import build_tally_block
    pair = _pair(filter_on=True)
    state = _state()
    slot = {"votes": {}, "voted_uids": []}
    out = build_tally_block("C01", slot, ["Friday", "Saturday"],
                            _config(pair), state)
    assert "C01 — 0/2 voted" in out  # 2 active, not 3 configured
    assert "@charlie" not in out
