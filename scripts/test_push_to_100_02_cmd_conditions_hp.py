"""Tests extracted from test_push_to_100.py — bin 2.

Sections in this file:
  - cmd_conditions_hp.py
"""
"""Tests for the 4 largest remaining coverage gaps."""
import sys, os
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


def _ctx(cmd, text, state, config=None, **kw):
    base = {
        "user_id": "GM1", "user_name": "Lewis", "gm_ids": {"GM1"},
        "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
        "state": state,
        "config": config or {"group_id": -1, "gm_user_ids": [], "topic_pairs": []},
        "campaign_name": "Kibwe", "now_iso": "2026-04-03T12:00:00+00:00",
        "msg_time_iso": "2026-04-03T12:00:00+00:00",
        "parsed": {"raw_text": text}, "maps": MagicMock(),
        "cmd_word": cmd, "text": text,
    }
    base.update(kw)
    return base

def _ic(cmd, state=None):
    return {"user_id": "GM1", "user_name": "Lewis", "gm_ids": {"GM1"},
            "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
            "state": state or {}, "campaign_name": "Kibwe",
            "config": {"group_id": -1, "gm_user_ids": [], "topic_pairs": []},
            "now_iso": "2026-04-03T12:00:00+00:00", "msg_time_iso": "2026-04-03T12:00:00+00:00",
            "parsed": {}, "maps": MagicMock(), "cmd_word": cmd, "text": cmd}

def _status(state_extras=None):
    s = {"topics": {}, "post_timestamps": {}, "message_counts": {},
         "players": {}, "paused_campaigns": {}, "current_scenes": {}}
    if state_extras:
        s.update(state_extras)
    return s

def _run_status(state, gm_ids=None, hours=1.0):
    from commands.status import build_status
    with patch("commands.status.helpers") as mh:
        mh.get_label.return_value = "C00"
        mh.get_topic_timestamps.return_value = {}
        mh.hours_since.return_value = hours
        mh.get_characters.return_value = {}
        mh.player_full_name.return_value = "A"
        mh.players_by_campaign.return_value = {}
        mh.pace_split.return_value = {"gm_this": 0, "player_this": 0,
                                       "gm_last": 0, "player_last": 0}
        mh.trend_icon.return_value = "➡️"
        mh.posts_str.return_value = "0"
        return build_status("100", "Kibwe", state, gm_ids or set(), {})

# ── cmd_conditions_hp.py ─────────────────────────────────────────────────────

def test_condition_no_target():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/condition", "/condition", {"conditions": {}},
               parsed={"raw_text": "/condition"})
    assert handle(ctx) is True


def test_condition_double_dash():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/condition", "/condition Goblin -- Stunned",
               {"conditions": {"100": []}},
               parsed={"raw_text": "/condition Goblin -- Stunned"})
    assert handle(ctx) is True


def test_condition_single_dash():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/condition", "/condition Goblin - Stunned",
               {"conditions": {"100": []}},
               parsed={"raw_text": "/condition Goblin - Stunned"})
    assert handle(ctx) is True


def test_condition_no_separator():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/condition", "/condition Goblin",
               {"conditions": {"100": []}},
               parsed={"raw_text": "/condition Goblin"})
    assert handle(ctx) is True


def test_endcondition_num_out_of_range():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/endcondition", "/endcondition 9",
               {"conditions": {"100": [{"target": "G", "effect": "S"}]}},
               parsed={"raw_text": "/endcondition 9"})
    assert handle(ctx) is True


def test_endcondition_not_a_number():
    from dispatch.cmd_conditions_hp import handle
    # /delcondition with non-numeric → hits ValueError branch (lines 74-75)
    ctx = _ctx("/endcondition", "/endcondition bad",
               {"conditions": {"100": [{"target": "G", "effect": "S"}]}},
               parsed={"raw_text": "/endcondition bad"})
    assert handle(ctx) is True


def test_hp_bare_shows_tracker():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/hp", "/hp",
               {"hp_tracker": {"100": {"Goblin": {"current": 10, "max": 20}}}},
               parsed={"raw_text": "/hp"})
    assert handle(ctx) is True


def test_hp_set_max_out_of_range():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/hp", "/hp set Goblin 10/99999",
               {"hp_tracker": {}}, parsed={"raw_text": "/hp set Goblin 10/99999"})
    assert handle(ctx) is True


def test_hp_set_bad_format():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/hp", "/hp set Goblin notanumber",
               {"hp_tracker": {}}, parsed={"raw_text": "/hp set Goblin notanumber"})
    assert handle(ctx) is True


def test_hp_set_no_target():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/hp", "/hp set", {"hp_tracker": {}}, parsed={"raw_text": "/hp set"})
    assert handle(ctx) is True


def test_hp_damage_bad_amount():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/hp", "/hp d Goblin bad",
               {"hp_tracker": {"100": {"Goblin": {"current": 20, "max": 20}}}},
               parsed={"raw_text": "/hp d Goblin bad"})
    assert handle(ctx) is True


def test_hp_damage_no_target():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/hp", "/hp d", {"hp_tracker": {}}, parsed={"raw_text": "/hp d"})
    assert handle(ctx) is True


def test_hp_heal_no_entry():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/hp", "/hp h Ghost 10",
               {"hp_tracker": {"100": {}}}, parsed={"raw_text": "/hp h Ghost 10"})
    assert handle(ctx) is True


def test_hp_heal_bad_amount():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/hp", "/hp h Goblin bad",
               {"hp_tracker": {"100": {"Goblin": {"current": 20, "max": 20}}}},
               parsed={"raw_text": "/hp h Goblin bad"})
    assert handle(ctx) is True


def test_hp_heal_no_target():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/hp", "/hp h", {"hp_tracker": {}}, parsed={"raw_text": "/hp h"})
    assert handle(ctx) is True


def test_hp_bad_subcommand():
    from dispatch.cmd_conditions_hp import handle
    ctx = _ctx("/hp", "/hp unknown", {"hp_tracker": {}},
               parsed={"raw_text": "/hp unknown"})
    assert handle(ctx) is True

