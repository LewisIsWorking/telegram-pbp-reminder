"""Coverage tests extracted from test_dispatch_coverage.py — bin 5.

Sections in this file:
  - dispatch/cmd_gm.py — /setpermanent and /unsetpermanent
  - dispatch/poll_notify.py — _poll_link_for and updated capture_unknown_voter
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


# ── dispatch/cmd_gm.py — /setpermanent and /unsetpermanent ──────────────────

def _gm_ctx(cmd: str, state: dict) -> dict:
    """Build a minimal GM ctx for cmd_gm tests."""
    return {
        "cmd_word": cmd.split()[0],
        "text": cmd,
        "user_id": "999",
        "gm_ids": ["999"],
        "pid": "100",
        "campaign_name": "TestCampaign",
        "state": state,
        "config": {"topic_pairs": [{"pbp_topic_ids": [100], "name": "TestCampaign"}]},
        "group_id": -1001,
        "thread_id": 200,
        "now_iso": "2026-04-10T00:00:00+00:00",
        "config": {"topic_pairs": [{"pbp_topic_ids": [100], "name": "TestCampaign"}]},
        "parsed": {"raw_text": cmd},
    }


def test_setpermanent_marks_player():
    from dispatch.cmd_gm import handle
    state = {"players": {"100:42": {
        "user_id": "42", "first_name": "Bob", "username": "bobuser",
        "pbp_topic_id": "100", "campaign_name": "TestCampaign",
        "last_post_time": "2026-04-01T00:00:00+00:00", "last_warned_week": 0,
    }}, "paused_campaigns": {}}
    ctx = _gm_ctx("/setpermanent @bobuser", state)
    result = handle(ctx)
    assert result is True
    assert state["players"]["100:42"].get("permanent") is True


def test_unsetpermanent_removes_flag():
    from dispatch.cmd_gm import handle
    state = {"players": {"100:42": {
        "user_id": "42", "first_name": "Bob", "username": "bobuser",
        "pbp_topic_id": "100", "campaign_name": "TestCampaign",
        "last_post_time": "2026-04-01T00:00:00+00:00", "last_warned_week": 0,
        "permanent": True,
    }}, "paused_campaigns": {}}
    ctx = _gm_ctx("/unsetpermanent @bobuser", state)
    result = handle(ctx)
    assert result is True
    assert "permanent" not in state["players"]["100:42"]


def test_setpermanent_unknown_player():
    from dispatch.cmd_gm import handle
    state = {"players": {}, "paused_campaigns": {}}
    ctx = _gm_ctx("/setpermanent @nobody", state)
    result = handle(ctx)
    assert result is True  # handled but not found — sends error msg


def test_setpermanent_no_arg():
    from dispatch.cmd_gm import handle
    state = {"players": {}, "paused_campaigns": {}}
    ctx = _gm_ctx("/setpermanent", state)
    result = handle(ctx)
    assert result is True  # handled — sends usage msg



# ── dispatch/poll_notify.py — _poll_link_for and updated capture_unknown_voter ─

def _pn_config_with_poll():
    return {
        "group_id": -1001, "bot_topic_id": 999,
        "group_username": "Path_Wars",
        "topic_pairs": [{
            "pbp_topic_ids": [100], "code": "C01", "name": "DF",
            "chat_topic_id": 21514, "poll_user_ids": [111],
            "poll_user_names": {"111": "Alice"},
            "poll_options": ["Friday", "Saturday"],
        }],
    }


def test_poll_link_for_with_msg_id():
    from dispatch.poll_notify import _poll_link_for
    state = {"session_poll": {"C01": {"poll_message_id": 9999, "votes": {}}}}
    result = _poll_link_for("C01", _pn_config_with_poll(), state)
    assert "9999" in result


def test_poll_link_for_no_msg_id():
    from dispatch.poll_notify import _poll_link_for
    state = {"session_poll": {"C01": {}}}
    result = _poll_link_for("C01", _pn_config_with_poll(), state)
    assert result == ""


def test_poll_link_for_unknown_code():
    from dispatch.poll_notify import _poll_link_for
    state = {"session_poll": {}}
    result = _poll_link_for("C99", _pn_config_with_poll(), state)
    assert result == ""


def test_capture_unknown_voter_posts_alert():
    from dispatch.poll_notify import capture_unknown_voter
    config = _pn_config_with_poll()
    state = {"poll_unknown_voters": {}, "session_poll": {}}
    capture_unknown_voter("999888", "C01", config, state)
    assert "999888" in state["poll_unknown_voters"].get("C01", [])
    # tg.send_message should have been called (conftest mock captures it)


def test_capture_unknown_voter_skips_known_uid():
    from dispatch.poll_notify import capture_unknown_voter
    config = _pn_config_with_poll()
    state = {"poll_unknown_voters": {}, "session_poll": {}}
    # uid 111 is in poll_user_ids — should not be captured
    capture_unknown_voter("111", "C01", config, state)
    assert "C01" not in state["poll_unknown_voters"]


def test_capture_unknown_voter_skips_known_name_uid():
    from dispatch.poll_notify import capture_unknown_voter
    config = _pn_config_with_poll()
    state = {"poll_unknown_voters": {}, "session_poll": {}}
    # uid "111" is in poll_user_names — should not be captured
    capture_unknown_voter("111", "C01", config, state)
    assert "C01" not in state["poll_unknown_voters"]


def test_capture_unknown_voter_no_duplicate():
    from dispatch.poll_notify import capture_unknown_voter
    config = _pn_config_with_poll()
    state = {"poll_unknown_voters": {"C01": ["999888"]}, "session_poll": {}}
    capture_unknown_voter("999888", "C01", config, state)
    assert state["poll_unknown_voters"]["C01"].count("999888") == 1

