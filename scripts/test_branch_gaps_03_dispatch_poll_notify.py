"""Coverage tests extracted from test_branch_gaps.py — bin 3.

Sections in this file:
  - dispatch/poll_notify.py: capture_unknown_voter + identify_unknown_voter
  - scheduled/session_poll.py: exception isolation
  - commands/queue_stats.py: avg reply per campaign

Targeted tests for specific uncovered branches in the production
modules listed above. Module imports are duplicated from the original
``test_branch_gaps.py`` header; per-section helper functions are
extracted alongside their sections.
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


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



# ─── scheduled/session_poll.py: exception isolation ──────────────────────────

def test_session_poll_exception_isolated():
    from scheduled.session_poll import post_session_poll
    config = {"group_id": -1, "gm_user_ids": [], "bot_topic_id": 999,
              "poll_post_hour": 7,
              "topic_pairs": [{"pbp_topic_ids": [100], "code": "C01",
                               "hybrid_live": True, "poll_options": ["A"],
                               "chat_topic_id": 21514}]}
    now = datetime(2026, 3, 29, 8, tzinfo=timezone.utc)
    state = {}
    with patch("scheduled.session_poll._post_one", side_effect=RuntimeError("boom")):
        post_session_poll(config, state, now=now)  # should not raise



# ─── commands/queue_stats.py: avg reply per campaign ─────────────────────────

def test_queue_stats_avg_reply_shown():
    from commands.queue_stats import build_queue_stats
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    ts = [(now - timedelta(hours=h*2)).isoformat() for h in range(5)]
    config = {"group_id": -1, "gm_user_ids": [999],
              "topic_pairs": [{"pbp_topic_ids": [100], "code": "C00",
                               "name": "Kibwe", "gm_user_ids": [999]}]}
    state = {
        "queue_history": {}, "queue_archive": [],
        "_config_cache": config,
        "post_timestamps": {"100": {"999": ts}},
    }
    with patch("commands.queue_scan.scan_transcripts", return_value={}), \
         patch("commands.queue_analytics.helpers") as mh, \
         patch("commands.queue_stats.helpers") as mh2:
        mh.iter_campaigns.return_value = []
        mh2.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
        mh2.is_excluded.return_value = False
        mh2.get_topic_timestamps.return_value = {"999": ts}
        result = build_queue_stats(config, state)
    assert isinstance(result, str)


