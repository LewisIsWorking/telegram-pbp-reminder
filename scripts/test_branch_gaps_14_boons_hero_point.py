"""Tests extracted from test_branch_gaps.py — bin 14.

Sections in this file:
  - boons/hero_point.py
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


def test_pending_hero_points_survives_state_round_trip(tmp_path):
    """Regression: the picker writes pending_hero_points; it MUST persist.

    The bot runs on an hourly cron — the button is created on one run and
    tapped (handled) on a later run, so the pending entry has to survive a
    save/load cycle. Before pending_hero_points was added to the queue
    partition, save() silently dropped it and every Hero Point button was
    a no-op on the next run. See state.py PARTITIONS.
    """
    import state as state_mod
    from boons.hero_point import (post_hero_point_picker,
                                  process_hero_campaign_callback)

    state = _hp_state()
    with patch("boons.hero_point.tg.send_message_with_buttons"):
        post_hero_point_picker("U1", "Chase", _hp_config(), state)
    assert "U1" in state["pending_hero_points"]

    # Persist and reload exactly as the cron does between runs.
    with patch("state._state_dir", return_value=tmp_path):
        state_mod._loaded_ok = True
        state_mod._save_to_files(state)
        reloaded = state_mod._load_from_files()

    assert reloaded.get("pending_hero_points", {}).get("U1"), \
        "pending_hero_points was dropped on save — button would be a no-op"

    # And the reloaded pending entry actually lets the callback fire.
    cb = {"data": "herocampaign:U1:100", "from": {"id": "U1"},
          "message": {"chat": {"id": -1001}, "message_id": 42}}
    with patch("boons.hero_point.tg.edit_message"), \
         patch("boons.hero_point.tg.send_message"):
        assert process_hero_campaign_callback(cb, _hp_config(), reloaded) is True
