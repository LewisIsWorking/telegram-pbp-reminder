"""Tests for checker.py — milestone (part a) group.

Extracted from test_checker.py during the test-split refactor. Module
imports, helper functions (_make_config, _make_state, _make_msg, _utc,
_reset, _run_all), and the _LOGS_DIR redirection setup all live in the
shared ``_test_checker_helpers`` module so this file contains test
functions only.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)


def test_milestone_thread_500():
    """Thread hitting 500 posts fires milestone in thread and bot topic."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["thread_message_counts"] = {"100": {"42": 300, "50": 200}}
    state["celebrated_milestones"] = {}

    checker.check_message_milestones(config, state)
    assert state["celebrated_milestones"].get("thread:100") == 500
    assert any("500" in m.get("text", "") for m in _sent_messages)

def test_milestone_thread_not_repeated():
    _reset()
    config = _make_config()
    state = _make_state()
    state["thread_message_counts"] = {"100": {"42": 300, "50": 200}}
    state["celebrated_milestones"] = {"thread:100": 500}

    checker.check_message_milestones(config, state)
    milestone_msgs = [m for m in _sent_messages if "500" in m.get("text", "")]
    assert len(milestone_msgs) == 0

def test_milestone_thread_1000():
    _reset()
    config = _make_config()
    state = _make_state()
    state["thread_message_counts"] = {"100": {"42": 600, "50": 400}}
    state["celebrated_milestones"] = {"thread:100": 500}

    checker.check_message_milestones(config, state)
    assert state["celebrated_milestones"]["thread:100"] == 1000
    assert any("1,000" in m.get("text", "") for m in _sent_messages)

def test_milestone_thread_below_step():
    """Threads under 500 messages don't fire."""
    _reset()
    config = _make_config()
    state = _make_state()
    state["thread_message_counts"] = {"100": {"42": 100}}
    state["celebrated_milestones"] = {}

    checker.check_message_milestones(config, state)
    assert "thread:100" not in state["celebrated_milestones"]

def test_milestone_global():
    _reset()
    config = {
        "group_id": -100,
        "gm_user_ids": [999],
        "leaderboard_topic_id": 9999,
        "topic_pairs": [
            {"name": "A", "chat_topic_id": 200, "pbp_topic_ids": [100]},
            {"name": "B", "chat_topic_id": 400, "pbp_topic_ids": [300]},
        ],
    }
    state = _make_state()
    state["thread_message_counts"] = {
        "100": {"42": 3000},
        "300": {"50": 2000},
    }
    state["celebrated_milestones"] = {}

    checker.check_message_milestones(config, state)
    assert state["celebrated_milestones"].get("global") == 5000
    assert any("5,000" in m.get("text", "") and "Path Wars" in m.get("text", "")
               for m in _sent_messages)

def test_milestone_thread_combat_label():
    """Multi-topic campaign: combat thread fires with COMBAT label."""
    _reset()
    config = {
        "group_id": -100, "bot_topic_id": 999, "gm_user_ids": [999],
        "topic_pairs": [{
            "pbp_topic_ids": [100, 200], "code": "C06", "name": "Kibwe",
            "gm_user_ids": [999], "chat_topic_id": 21514,
        }],
    }
    state = _make_state()
    state["thread_message_counts"] = {"200": {"42": 500}}
    state["celebrated_milestones"] = {}

    checker.check_message_milestones(config, state)
    assert state["celebrated_milestones"].get("thread:200") == 500
    msg_text = next((m.get("text", "") for m in _sent_messages if "500" in m.get("text", "")), "")
    assert "COMBAT" in msg_text

def test_milestone_thread_unknown_thread_skips():
    """Thread not found in any campaign config is skipped gracefully."""
    _reset()
    config = _make_config()
    state = _make_state()
    # Thread 999999 not in any pair
    state["thread_message_counts"] = {"999999": {"42": 500}}
    state["celebrated_milestones"] = {}

    checker.check_message_milestones(config, state)

def test_milestone_messages_specific_body_used():
    """When thread_id + milestone are in JSON, specific body is sent."""
    from scheduled.message_milestones import _MilestoneMessages, _build_msg
    _MilestoneMessages.reset()
    _MilestoneMessages._data = {"66154": {"500": "Bell tower. The beginning."}}
    msg = _build_msg("66154", "Riddleport PBP", "🎯", 500)
    assert "Bell tower. The beginning." in msg
    assert "Riddleport PBP has hit 500 messages" in msg
    _MilestoneMessages.reset()

def test_milestone_messages_generic_body_fallback():
    """When thread_id not in JSON, generic body is used."""
    from scheduled.message_milestones import _MilestoneMessages, _build_msg
    _MilestoneMessages.reset()
    _MilestoneMessages._data = {}
    msg = _build_msg("99999", "Unknown", "🎯", 500)
    assert "collaborative storytelling" in msg
    _MilestoneMessages.reset()
