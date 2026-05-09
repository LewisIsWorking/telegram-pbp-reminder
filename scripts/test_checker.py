"""Tests for checker.py — root file after phase-2.3 extraction.

All major feature-area tests have moved to sibling ``test_checker_<group>``
files. See ``docs/dev/REFACTOR_PROGRESS.md`` for the full split history.
"""
from _test_checker_helpers import (
    datetime, timezone, timedelta,
    _sent_messages, _mock_tg, checker, helpers,
    _utc, _reset, _make_config, _make_state, _make_msg, _run_all,
)



