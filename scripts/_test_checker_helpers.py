"""Tests for checker.py logic.

The telegram module is mocked globally by conftest.py before any test
module is imported. This file references the shared _sent_messages list
and _mock_tg from conftest so all modules bound to the same mock object.
"""

import sys
from datetime import datetime, timezone, timedelta

# _sent_messages and _mock_tg come from conftest.py (loaded before this module)
import conftest as _conftest
_sent_messages = _conftest._sent_messages
_mock_tg = _conftest._mock_tg

import checker
import helpers


def _utc(*args):
    return datetime(*args, tzinfo=timezone.utc)


def _reset():
    _sent_messages.clear()


# Redirect transcript logging to temp dir (so tests don't write to repo)
import tempfile as _tempfile
_test_log_dir = _tempfile.mkdtemp()
checker._LOGS_DIR = __import__("pathlib").Path(_test_log_dir)

# Also patch extracted modules that have their own _LOGS_DIR
from commands import recap as _recap_mod, catchup as _catchup_mod
from transcript import logger as _logger_mod, finalize as _finalize_mod
_recap_mod._LOGS_DIR = checker._LOGS_DIR
_catchup_mod._LOGS_DIR = checker._LOGS_DIR
_logger_mod._LOGS_DIR = checker._LOGS_DIR
_finalize_mod._LOGS_DIR = checker._LOGS_DIR

# Redirect archive to temp file so tests don't write to repo
helpers.ARCHIVE_PATH = __import__("pathlib").Path(_test_log_dir) / "weekly_archive.json"


def _make_config(pairs=None, gm_ids=None):
    return {
        "group_id": -100,
        "alert_after_hours": 4,
        "gm_user_ids": gm_ids or [999],
        "leaderboard_topic_id": None,
        "bot_topic_id": 300,
        "topic_pairs": pairs or [
            {"name": "TestCampaign", "chat_topic_id": 200, "pbp_topic_ids": [100]},
        ],
    }


def _make_state():
    return {
        "offset": 0,
        "topics": {},
        "players": {},
        "message_counts": {},
        "post_timestamps": {},
        "last_alerts": {},
        "last_roster": {},
        "last_potw": {},
        "last_pace": {},
        "last_leaderboard": None,
        "last_recruitment_check": {},
        "last_anniversary": {},
        "combat": {},
        "removed_players": {},
        "pending_potw_boons": {},
    }


def _make_msg(update_id, topic_id, text, user_id=42, first_name="TestPlayer",
              username="tp", last_name="", group_id=-100, date_ts=None):
    """Convenience factory for a Telegram update dict."""
    return {
        "update_id": update_id,
        "message": {
            "chat": {"id": group_id},
            "message_thread_id": topic_id,
            "from": {
                "id": user_id,
                "first_name": first_name,
                "last_name": last_name,
                "username": username,
            },
            "date": date_ts or int(datetime.now(timezone.utc).timestamp()),
            "text": text,
        },
    }


# ------------------------------------------------------------------ #
#  Pure function tests
# ------------------------------------------------------------------ #

def _run_all():
    tests = [(name, obj) for name, obj in globals().items()
             if name.startswith("test_") and callable(obj)]
    passed = failed = 0
    for name, func in sorted(tests):
        try:
            func()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  FAIL: {name}: {e}")
    print(f"\n{passed} passed, {failed} failed out of {passed + failed}")
    return failed
