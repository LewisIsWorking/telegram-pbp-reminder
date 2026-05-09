"""Coverage tests extracted from test_push_to_100.py — bin 2.

Sections in this file:
  - cmd_conditions_hp.py
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


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


