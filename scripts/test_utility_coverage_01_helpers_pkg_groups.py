"""Tests extracted from test_utility_coverage.py — bin 1.

Sections in this file:
  - helpers_pkg/groups.py  — pure functions, no mocking needed
  - scheduled/session_poll_build.py  — pure functions
  - scheduled/session_poll_build.py  — pure functions
"""
"""
Coverage tests for:
  migrate_gist_to_files.py
  promote_poll_voters.py
  scheduled/session_poll_build.py
  scheduled/state_backup.py
  helpers_pkg/groups.py
"""
import sys, os, json, pytest, tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

def _g_config():
    return {
        "group_id": -1001,
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C00", "name": "R"},
            {"pbp_topic_ids": [101], "code": "C01", "name": "D",
             "group_id": -2002, "linked_polls": ["C11"]},
        ]
    }

def _now():
    return datetime(2026, 4, 3, 12, 0, tzinfo=timezone.utc)  # Friday

# ═══════════════════════════════════════════════════════════════════════════════
# helpers_pkg/groups.py  — pure functions, no mocking needed

# ═══════════════════════════════════════════════════════════════════════════════

from helpers_pkg.groups import (
    group_id_for_campaign, linked_poll_codes, all_group_ids, pid_for_code
)


def _g_config():
    return {
        "group_id": -1001,
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C00", "name": "R"},
            {"pbp_topic_ids": [101], "code": "C01", "name": "D",
             "group_id": -2002, "linked_polls": ["C11"]},
        ]
    }


def test_group_id_for_campaign_global():
    assert group_id_for_campaign(_g_config(), "100") == -1001


def test_group_id_for_campaign_override():
    assert group_id_for_campaign(_g_config(), "101") == -2002


def test_group_id_for_campaign_not_found():
    assert group_id_for_campaign(_g_config(), "999") == -1001


def test_linked_poll_codes_found():
    assert linked_poll_codes(_g_config(), "101") == ["C11"]


def test_linked_poll_codes_none():
    assert linked_poll_codes(_g_config(), "100") == []


def test_linked_poll_codes_not_found():
    assert linked_poll_codes(_g_config(), "999") == []


def test_all_group_ids():
    ids = all_group_ids(_g_config())
    assert -1001 in ids
    assert -2002 in ids


def test_all_group_ids_no_overrides():
    config = {"group_id": -1, "topic_pairs": [{"pbp_topic_ids": [1]}]}
    assert all_group_ids(config) == {-1}


def test_pid_for_code_found():
    assert pid_for_code(_g_config(), "C00") == "100"


def test_pid_for_code_not_found():
    assert pid_for_code(_g_config(), "C99") is None



# ═══════════════════════════════════════════════════════════════════════════════
# scheduled/session_poll_build.py  — pure functions
