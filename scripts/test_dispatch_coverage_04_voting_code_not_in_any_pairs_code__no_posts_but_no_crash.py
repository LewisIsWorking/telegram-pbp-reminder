"""Coverage tests extracted from test_dispatch_coverage.py — bin 4.

Sections in this file:
  - voting_code not in any pair's code → no posts but no crash
  - commands/queue_scan._build_link
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


# ═══════════════════════════════════════════════════════════════════════════════

from dispatch.poll_notify import _voter_mention, notify_vote
from dispatch.poll_tally import _lead_summary, build_tally_block


def _pn_config():
    return {
        "group_id": -1001,
        "topic_pairs": [{
            "pbp_topic_ids": [100], "code": "C01", "name": "DF",
            "chat_topic_id": 21514, "hybrid_live": True,
            "poll_options": ["Friday", "Saturday", "Both", "Can't make it"],
            "poll_user_names": {"U1": "alice"},
            "poll_user_ids": ["U1"],
        }]
    }


def test_voter_mention_by_player_username():
    state = {"players": {"x": {"user_id": "U1", "username": "alice"}}}
    assert _voter_mention("U1", "Alice", {}, state) == "@alice"


def test_voter_mention_by_first_name():
    state = {"players": {"x": {"user_id": "U1", "username": "", "first_name": "Alice"}}}
    result = _voter_mention("U1", "Alice", {}, state)
    assert "Alice" in result and "⚠️" in result


def test_voter_mention_from_poll_names():
    config = {"topic_pairs": [{"poll_user_names": {"U2": "bob"}}]}
    assert _voter_mention("U2", "Bob", config, {}) == "@bob"


def test_voter_mention_fallback():
    result = _voter_mention("U99", "Fallback", {}, {})
    assert "Fallback" in result and "⚠️" in result


def test_build_tally_block_no_votes():
    result = build_tally_block("C01", {"votes": {}, "voted_uids": []},
                               ["Friday", "Saturday"], _pn_config(), {})
    assert "C01" in result


def test_build_tally_block_with_votes():
    slot = {"votes": {"0": ["U1", "U2"], "1": ["U3"]}, "voted_uids": ["U1", "U2", "U3"]}
    result = build_tally_block("C01", slot,
                               ["Friday", "Saturday", "Both", "Can't"],
                               _pn_config(), {})
    assert "C01" in result
    assert "Friday" in result


def test_lead_summary_winner():
    votes = {"0": ["U1", "U2"], "1": ["U3"]}
    options = ["Friday", "Saturday", "Both", "Can't"]
    result = _lead_summary(votes, options)
    assert "Friday" in result or "leads" in result


def test_lead_summary_tie():
    votes = {"0": ["U1"], "1": ["U2"]}
    options = ["Friday", "Saturday"]
    result = _lead_summary(votes, options)
    assert "tied" in result or "tie" in result.lower()


def test_lead_summary_no_votes():
    result = _lead_summary({}, ["Friday"])
    assert result == ""


def test_notify_vote_unknown_code():
    # voting_code not in any pair's code → no posts but no crash
    state = {"session_poll": {}}
    notify_vote(_pn_config(), state, "Alice", "U1", "C99", "Friday", "100")


def test_notify_vote_sends_tally():
    state = {"session_poll": {"C01": {
        "poll_id": "p1", "votes": {"0": ["U1"]}, "voted_uids": [], "week_iso": "sun2026-03-29",
    }}}
    notify_vote(_pn_config(), state, "Alice", "U1", "C01", "Friday", "100")
    # conftest mock tg.send_message should have been called (checked via no-error)


def test_notify_vote_no_chat_topic():
    config = {"group_id": -1, "topic_pairs": [{
        "pbp_topic_ids": [100], "code": "C01", "name": "DF",
        "poll_options": ["Friday"], "poll_user_names": {},
    }]}
    state = {"session_poll": {"C01": {"votes": {}, "voted_uids": []}}}
    notify_vote(config, state, "Alice", "U1", "C01", "Friday", "100")
    # No chat_topic_id → no send, no crash



# ── commands/queue_scan._build_link ──────────────────────────────────────────

def test_build_link_public_group():
    from commands.queue_scan import _build_link
    link = _build_link(-1001661053273, "Path_Wars", "1242", "1540")
    assert link == "https://t.me/Path_Wars/1242/1540"


def test_build_link_private_group():
    from commands.queue_scan import _build_link
    # C11: group_id=-1003496373617, no username → c/ format stripping leading 100
    link = _build_link(-1003496373617, None, "1242", "1540")
    assert link == "https://t.me/c/3496373617/1242/1540"


def test_build_link_private_group_empty_username():
    from commands.queue_scan import _build_link
    link = _build_link(-1003496373617, "", "1242", "1540")
    assert link == "https://t.me/c/3496373617/1242/1540"


