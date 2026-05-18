"""Tests for the players.permanence module (L26).

Added 2026-05-17 when the perm-detection logic was unified behind
``is_permanent(player, config)`` so the per-record flag and the new
``config["permanent_user_ids"]`` list share a single source of truth.
"""

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from players.permanence import is_permanent


def test_is_permanent_per_record_flag_true():
    """Per-record flag True is recognised \u2014 backward compatible
    with the pre-2026-05-17 behaviour."""
    assert is_permanent({"user_id": "1", "permanent": True}, {}) is True


def test_is_permanent_per_record_flag_false_no_config_match():
    """Neither per-record nor config list matches \u2192 False."""
    assert is_permanent({"user_id": "1", "permanent": False}, {}) is False
    assert is_permanent({"user_id": "1"}, {}) is False


def test_is_permanent_user_id_in_config_list():
    """user_id in config['permanent_user_ids'] \u2192 True even with
    per-record flag unset. This is the new 2026-05-17 behaviour."""
    config = {"permanent_user_ids": ["1", "2", "3"]}
    assert is_permanent({"user_id": "1"}, config) is True
    assert is_permanent({"user_id": "4"}, config) is False


def test_is_permanent_handles_int_vs_str_user_id():
    """user_id may be stored as int or str historically; both forms
    match against the config list regardless of type."""
    config = {"permanent_user_ids": [6144366145]}  # int as in config.json
    # State stores as str:
    assert is_permanent({"user_id": "6144366145"}, config) is True
    # State stores as int:
    assert is_permanent({"user_id": 6144366145}, config) is True
    # Mismatch \u2192 False
    assert is_permanent({"user_id": 9999999999}, config) is False


def test_is_permanent_empty_or_missing_user_id():
    """A player without a user_id falls through to False regardless
    of config. Prevents accidental \"\" \u2208 [] matches."""
    config = {"permanent_user_ids": [1, 2, 3]}
    assert is_permanent({"user_id": ""}, config) is False
    assert is_permanent({"user_id": None}, config) is False
    assert is_permanent({}, config) is False


def test_is_permanent_missing_config_key():
    """No ``permanent_user_ids`` key in config \u2192 falls back to per-
    record flag only. Defensive against partial configs."""
    assert is_permanent({"user_id": "1", "permanent": True}, {}) is True
    assert is_permanent({"user_id": "1"}, {}) is False
    # Explicit None for the key
    config = {"permanent_user_ids": None}
    assert is_permanent({"user_id": "1"}, config) is False


def test_is_permanent_per_record_takes_precedence_when_either_true():
    """Per-record flag True OR config match \u2192 True (logical OR).
    Either path independently triggers the perm classification."""
    config_with_match = {"permanent_user_ids": ["999"]}
    config_no_match = {"permanent_user_ids": ["888"]}
    # Per-record True, no config match \u2192 True
    assert is_permanent({"user_id": "1", "permanent": True}, config_no_match) is True
    # Per-record False, config match \u2192 True
    assert is_permanent({"user_id": "999", "permanent": False}, config_with_match) is True
    # Both True \u2192 True
    assert is_permanent({"user_id": "999", "permanent": True}, config_with_match) is True
    # Neither \u2192 False
    assert is_permanent({"user_id": "1", "permanent": False}, config_no_match) is False
