"""Tests extracted from test_branch_gaps.py — bin 4.

Sections in this file:
  - dispatch/poll_notify.py: capture_unknown_voter + identify_unknown_voter
"""
"""
Targeted tests for every remaining coverage gap.
Organised by file, hitting each uncovered branch.
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

def _gm_ctx(text, pid="100", uid="GM1"):
    return {
        "cmd_word": text.split()[0], "text": text,
        "user_id": uid, "gm_ids": {"GM1"},
        "pid": pid, "group_id": -1, "thread_id": 999,
        "state": {}, "config": {},
        "campaign_name": "Kibwe",
        "now_iso": "2026-04-03T12:00:00+00:00",
        "msg_time_iso": "2026-04-03T12:00:00+00:00",
        "user_name": "Lewis",
        "maps": MagicMock(), "parsed": {"raw_text": "/done 99", "text": "/done 99"},
    }

def _capture_config(placeholders=None):
    return {"group_id": -1, "bot_topic_id": 999, "topic_pairs": [
        {"code": "C01", "pbp_topic_ids": [100],
         "poll_user_ids": placeholders or [111, 222],
         "poll_user_names": {str(u): f"user{u}" for u in (placeholders or [111, 222])}}
    ]}

def _hp_config():
    return {
        "group_id": -1001, "bot_topic_id": 999,
        "leaderboard_topic_id": 888,
        "topic_pairs": [
            {"pbp_topic_ids": [100], "name": "Magni Watch"},
            {"pbp_topic_ids": [200], "name": "Kibwe"},
        ],
    }

def _hp_state(uid="U1"):
    return {
        "players": {
            f"100:{uid}": {"user_id": uid, "pbp_topic_id": 100, "first_name": "Chase"},
            f"200:{uid}": {"user_id": uid, "pbp_topic_id": 200, "first_name": "Chase"},
        }
    }

def _gm_config():
    return {"topic_pairs": [
        {"code": "C00", "name": "Riddleport",
         "pbp_topic_ids": [66154, 133428],
         "chat_topic_id": 91008},
    ]}

def _mention_config():
    return {"topic_pairs": [
        {"code": "C01", "pbp_topic_ids": [100],
         "poll_user_names": {"8787": "Sestina_The_Banner_Witch"}},
    ]}

# ─── dispatch/poll_notify.py: capture_unknown_voter + identify_unknown_voter ──

def _capture_config(placeholders=None):
    return {"group_id": -1, "bot_topic_id": 999, "topic_pairs": [
        {"code": "C01", "pbp_topic_ids": [100],
         "poll_user_ids": placeholders or [111, 222],
         "poll_user_names": {str(u): f"user{u}" for u in (placeholders or [111, 222])}}
    ]}


def test_capture_unknown_voter():
    from dispatch.poll_notify import capture_unknown_voter
    state = {}
    capture_unknown_voter("U99", "C01", _capture_config(), state)
    assert "U99" in state.get("poll_unknown_voters", {}).get("C01", [])


def test_capture_unknown_voter_shows_voted_options():
    """Richer alert includes voted option labels and placeholder names."""
    from dispatch.poll_notify import capture_unknown_voter
    sent = []
    state = {"session_poll": {"C01": {"options": ["Mon", "Tue", "Wed"]}}}
    with patch("dispatch.poll_notify.tg.send_message",
               side_effect=lambda g, t, m: sent.append(m)):
        capture_unknown_voter("U99", "C01", _capture_config([9000000001]),
                              state, option_ids=[0, 2])
    assert sent, "Expected alert to be sent"
    assert "Mon" in sent[0] and "Wed" in sent[0]
    assert "user9000000001" in sent[0]


def test_capture_unknown_voter_no_options():
    """option_ids=None still sends alert without crashing."""
    from dispatch.poll_notify import capture_unknown_voter
    sent = []
    state = {}
    with patch("dispatch.poll_notify.tg.send_message",
               side_effect=lambda g, t, m: sent.append(m)):
        capture_unknown_voter("U99", "C01", _capture_config(), state)
    assert sent


def test_capture_known_voter_skipped():
    from dispatch.poll_notify import capture_unknown_voter
    state = {}
    capture_unknown_voter("111", "C01", _capture_config(), state)
    assert state.get("poll_unknown_voters", {}).get("C01", []) == []


def test_capture_unknown_no_pair():
    from dispatch.poll_notify import capture_unknown_voter
    capture_unknown_voter("U99", "C99", {}, {})  # no crash


def test_identify_unknown_voter_posts_alert():
    """identify_unknown_voter posts alert and moves UID to identified."""
    from dispatch.poll_notify import identify_unknown_voter
    state = {"poll_unknown_voters": {"C01": ["U99"]}}
    sent = []
    with patch("dispatch.poll_notify.tg.send_message",
               side_effect=lambda g, t, m: sent.append(m)):
        identify_unknown_voter("U99", "alice", "Alice", "C01",
                               _capture_config(), state)
    assert sent, "Expected identification alert"
    assert "@alice" in sent[0]
    assert state["poll_identified_voters"]["U99"]["username"] == "alice"
    assert "U99" not in state["poll_unknown_voters"]["C01"]


def test_identify_unknown_voter_skips_already_identified():
    """Calling identify twice for same UID is a no-op after first."""
    from dispatch.poll_notify import identify_unknown_voter
    state = {
        "poll_unknown_voters": {"C01": []},
        "poll_identified_voters": {"U99": {"username": "alice", "code": "C01"}},
    }
    sent = []
    with patch("dispatch.poll_notify.tg.send_message",
               side_effect=lambda g, t, m: sent.append(m)):
        identify_unknown_voter("U99", "alice", "Alice", "C01",
                               _capture_config(), state)
    assert not sent  # UID not in unknown bucket → no-op


def test_identify_unknown_voter_uid_not_in_bucket():
    """UID not in unknown_voters bucket → no alert, no crash."""
    from dispatch.poll_notify import identify_unknown_voter
    state = {"poll_unknown_voters": {"C01": ["OTHER"]}}
    sent = []
    with patch("dispatch.poll_notify.tg.send_message",
               side_effect=lambda g, t, m: sent.append(m)):
        identify_unknown_voter("U99", "alice", "Alice", "C01",
                               _capture_config(), state)
    assert not sent

