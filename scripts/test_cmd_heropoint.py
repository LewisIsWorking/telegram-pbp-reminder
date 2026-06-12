"""Tests for the /heropoint typed-fallback command (dispatch/cmd_heropoint.py)."""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(__file__))

from dispatch import cmd_heropoint


def _config():
    return {
        "group_id": -1001,
        "bot_topic_id": 137393,
        "topic_pairs": [
            {"pbp_topic_ids": [40585, 1], "name": "Kibwe", "code": "C06"},
            {"pbp_topic_ids": [66154, 2], "name": "Riddleport", "code": "C00"},
        ],
    }


def _state(pending=True):
    s = {
        "players": {
            "40585:U1": {"user_id": "U1", "pbp_topic_id": 40585, "first_name": "Ryo"},
            "66154:U1": {"user_id": "U1", "pbp_topic_id": 66154, "first_name": "Ryo"},
        },
    }
    if pending:
        s["pending_hero_points"] = {"U1": {"name": "Ryo Yamakawa"}}
    return s


def _ctx(text, state, pid=None):
    return {
        "text": text, "user_id": "U1", "user_name": "Ryo",
        "pid": pid, "reply_topic": 999, "thread_id": 999,
        "group_id": -1001, "config": _config(), "state": state,
    }


def _capture():
    """Patch tg.send_message and return the list it appends (group, topic, msg)."""
    sent = []
    return sent, patch("dispatch.cmd_heropoint.tg.send_message",
                       side_effect=lambda g, t, m: sent.append((g, t, m)))


def test_handle_ignores_other_commands():
    assert cmd_heropoint.handle(_ctx("/roll 1d20", _state())) is False


def test_claim_by_code_clears_pending():
    state = _state()
    sent, p = _capture()
    with p:
        assert cmd_heropoint.handle(_ctx("/heropoint C06", state)) is True
    assert any("Kibwe" in m for _, _, m in sent)
    assert "U1" not in state["pending_hero_points"]


def test_claim_by_name():
    state = _state()
    sent, p = _capture()
    with p:
        cmd_heropoint.handle(_ctx("/heropoint Riddleport", state))
    assert any("Riddleport" in m for _, _, m in sent)
    assert "U1" not in state["pending_hero_points"]


def test_no_arg_in_campaign_topic_uses_that_campaign():
    state = _state()
    sent, p = _capture()
    with p:
        cmd_heropoint.handle(_ctx("/heropoint", state, pid="40585"))
    assert any("Kibwe" in m for _, _, m in sent)
    assert "U1" not in state["pending_hero_points"]


def test_no_arg_no_topic_prompts_options():
    state = _state()
    sent, p = _capture()
    with p:
        cmd_heropoint.handle(_ctx("/heropoint", state, pid=None))
    # Still pending; prompt lists both campaigns.
    assert "U1" in state["pending_hero_points"]
    joined = " ".join(m for _, _, m in sent)
    assert "Kibwe" in joined and "Riddleport" in joined


def test_unknown_campaign_arg_prompts_options():
    state = _state()
    sent, p = _capture()
    with p:
        cmd_heropoint.handle(_ctx("/heropoint Nowhere", state))
    assert "U1" in state["pending_hero_points"]  # not claimed
    assert any("which campaign" in m.lower() for _, _, m in sent)


def test_no_pending_entry_is_friendly_noop():
    state = _state(pending=False)
    sent, p = _capture()
    with p:
        assert cmd_heropoint.handle(_ctx("/heropoint C06", state)) is True
    assert any("don't have a Hero Point" in m for _, _, m in sent)


def test_bot_topic_claim_announces_in_bot_topic_only():
    state = _state()
    sent, p = _capture()
    with p:
        cmd_heropoint.handle_bot_topic("c06", "U1", "Ryo",
                                       _config(), state, -1001, 137393)
    # reply_topic == bot_topic, so no duplicate +1 line to a second topic.
    assert any("Kibwe" in m for _, _, m in sent)
    assert "U1" not in state["pending_hero_points"]


def test_campaign_topic_claim_also_pings_bot_topic():
    state = _state()
    sent, p = _capture()
    with p:
        cmd_heropoint.handle(_ctx("/heropoint C06", state))  # reply_topic 999 != bot 137393
    topics = {t for _, t, _ in sent}
    assert 999 in topics and 137393 in topics  # confirmation + bot-topic ledger
