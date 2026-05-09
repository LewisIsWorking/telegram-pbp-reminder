"""Coverage tests extracted from test_branch_gaps.py — bin 12.

Sections in this file:
  - boons/hero_point.py
  - dispatch/cmd_gm.py: _canonical_pid and kick from chat topic

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


# ─── boons/hero_point.py ──────────────────────────────────────────────────────

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


def test_post_hero_point_picker_sends_buttons():
    """post_hero_point_picker sends a button message and stores pending entry."""
    from boons.hero_point import post_hero_point_picker
    state = _hp_state()
    sent_buttons = []
    with patch("boons.hero_point.tg.send_message_with_buttons",
               side_effect=lambda g, t, m, b: sent_buttons.append((m, b))):
        post_hero_point_picker("U1", "Chase", _hp_config(), state)
    assert sent_buttons, "Expected button message"
    msg, buttons = sent_buttons[0]
    assert "Chase" in msg
    assert any("Magni Watch" in b["text"] for b in buttons)
    assert any("Kibwe" in b["text"] for b in buttons)
    assert "U1" in state.get("pending_hero_points", {})


def test_post_hero_point_picker_no_campaigns():
    """post_hero_point_picker does nothing if winner has no active campaigns."""
    from boons.hero_point import post_hero_point_picker
    state = {"players": {}}
    sent = []
    with patch("boons.hero_point.tg.send_message_with_buttons",
               side_effect=lambda *a: sent.append(a)):
        post_hero_point_picker("U1", "Chase", _hp_config(), state)
    assert not sent


def test_process_hero_campaign_callback_confirms():
    """Tapping a campaign button confirms the Hero Point and clears pending."""
    from boons.hero_point import process_hero_campaign_callback
    state = {"pending_hero_points": {"U1": {"name": "Chase"}}}
    sent = []
    cb = {
        "data": "herocampaign:U1:100",
        "from": {"id": "U1"},
        "message": {"chat": {"id": -1001}, "message_id": 42},
    }
    with patch("boons.hero_point.tg.edit_message"), \
         patch("boons.hero_point.tg.send_message",
               side_effect=lambda g, t, m: sent.append(m)):
        result = process_hero_campaign_callback(cb, _hp_config(), state)
    assert result is True
    assert any("Magni Watch" in m for m in sent)
    assert "U1" not in state["pending_hero_points"]


def test_process_hero_campaign_callback_wrong_user():
    """A different user tapping the button is ignored."""
    from boons.hero_point import process_hero_campaign_callback
    state = {"pending_hero_points": {"U1": {"name": "Chase"}}}
    cb = {"data": "herocampaign:U1:100", "from": {"id": "U2"}, "message": {}}
    assert process_hero_campaign_callback(cb, _hp_config(), state) is False


def test_process_hero_campaign_callback_wrong_prefix():
    """Non-herocampaign callback data returns False immediately."""
    from boons.hero_point import process_hero_campaign_callback
    cb = {"data": "boon:100:0", "from": {"id": "U1"}, "message": {}}
    assert process_hero_campaign_callback(cb, _hp_config(), {}) is False


def test_process_hero_campaign_callback_no_pending():
    """No pending entry for this user → returns False."""
    from boons.hero_point import process_hero_campaign_callback
    cb = {"data": "herocampaign:U1:100", "from": {"id": "U1"}, "message": {}}
    assert process_hero_campaign_callback(cb, _hp_config(), {}) is False


# ─── dispatch/cmd_gm.py: _canonical_pid and kick from chat topic ──────────────

def _gm_config():
    return {"topic_pairs": [
        {"code": "C00", "name": "Riddleport",
         "pbp_topic_ids": [66154, 133428],
         "chat_topic_id": 91008},
    ]}


def test_canonical_pid_from_pbp_topic():
    from dispatch.cmd_gm import _canonical_pid
    assert _canonical_pid("66154", _gm_config()) == "66154"


def test_canonical_pid_from_chat_topic():
    from dispatch.cmd_gm import _canonical_pid
    assert _canonical_pid("91008", _gm_config()) == "66154"


def test_canonical_pid_from_combat_topic():
    from dispatch.cmd_gm import _canonical_pid
    assert _canonical_pid("133428", _gm_config()) == "66154"


def test_canonical_pid_unknown_returns_self():
    from dispatch.cmd_gm import _canonical_pid
    assert _canonical_pid("99999", _gm_config()) == "99999"


def test_campaign_name_found():
    from dispatch.cmd_gm import _campaign_name
    assert _campaign_name("66154", _gm_config()) == "Riddleport"


def test_campaign_name_not_found():
    from dispatch.cmd_gm import _campaign_name
    assert _campaign_name("99999", _gm_config()) == ""

