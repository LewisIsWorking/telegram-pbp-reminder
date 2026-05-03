"""Coverage tests for scheduled/{session_poll,queue_reminder,potw}.py guards."""
import sys, os, json, pytest, tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.dirname(__file__))

# ═══════════════════════════════════════════════════════════════════════════════
# scheduled/session_poll.py — guard conditions
# ═══════════════════════════════════════════════════════════════════════════════

from scheduled.session_poll import post_session_poll

_SUNDAY_EARLY = datetime(2026, 3, 29, 5, 0, tzinfo=timezone.utc)
_SUNDAY_8AM   = datetime(2026, 3, 29, 8, 0, tzinfo=timezone.utc)
_MONDAY_8AM   = datetime(2026, 3, 30, 8, 0, tzinfo=timezone.utc)


def _sp_config():
    return {
        "group_id": -1001, "bot_topic_id": 999,
        "gm_user_ids": [999], "poll_post_hour": 7,
        "topic_pairs": [{
            "pbp_topic_ids": [100], "code": "C01",
            "name": "DF", "hybrid_live": True,
            "chat_topic_id": 21514,
            "poll_options": ["Friday", "Saturday", "Both", "Can't make it"],
            "allows_multiple_answers": False,
            "poll_user_ids": [111, 222],
            "poll_user_names": {"111": "Alice", "222": "Bob"},
        }]
    }


def test_session_poll_skips_non_sunday():
    state = {}
    post_session_poll(_sp_config(), state, now=_MONDAY_8AM)
    # _migrate_flat_poll runs but no poll is posted
    assert not state.get("session_poll", {}).get("C01", {}).get("week_iso")


def test_session_poll_skips_before_hour():
    state = {}
    post_session_poll(_sp_config(), state, now=_SUNDAY_EARLY)
    assert not state.get("session_poll", {}).get("C01", {}).get("week_iso")


def test_session_poll_skips_already_posted():
    state = {"session_poll": {"C01": {"week_iso": "sun2026-03-29", "voted_uids": [],
                                       "last_ping_day": -1, "votes": {}}}}
    post_session_poll(_sp_config(), state, now=_SUNDAY_8AM)
    assert state["session_poll"]["C01"]["week_iso"] == "sun2026-03-29"


def test_session_poll_posts_new():
    state = {}
    post_session_poll(_sp_config(), state, now=_SUNDAY_8AM)
    assert "session_poll" in state
    assert state["session_poll"]["C01"]["week_iso"] == "sun2026-03-29"


def test_session_poll_send_failure_no_state():
    state = {}
    with patch("scheduled.session_poll.tg.send_poll", return_value=None):
        post_session_poll(_sp_config(), state, now=_SUNDAY_8AM)
    assert not state.get("session_poll", {}).get("C01", {}).get("week_iso")

# ═══════════════════════════════════════════════════════════════════════════════
# scheduled/queue_reminder.py — guard conditions
# ═══════════════════════════════════════════════════════════════════════════════

from scheduled.queue_reminder import post_queue_reminder


def _qr_config():
    return {
        "group_id": -1001, "bot_topic_id": 999,
        "gm_user_ids": [999], "queue_daily_hours": [9, 21],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
             "gm_user_ids": [999]}
        ]
    }


@patch("scheduled.queue_reminder.post_topic_queues")
@patch("scheduled.queue_reminder.scan_transcripts", return_value={})
def test_queue_reminder_no_entries_no_post(mock_scan, mock_ptq):
    state = {"last_queue_fingerprint": None, "queue_post_count": 0,
             "last_queue_pin_id": None, "last_queue_daily_slots": []}
    now = datetime(2026, 4, 3, 9, 0, tzinfo=timezone.utc)
    post_queue_reminder(_qr_config(), state, now=now)


@patch("scheduled.queue_reminder.post_topic_queues")
@patch("scheduled.queue_reminder.scan_transcripts")
def test_queue_reminder_same_fingerprint_skips(mock_scan, mock_ptq):
    # Use hour 10 — not in queue_daily_hours [9, 21], so daily override won't fire
    now = datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc)
    t = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    entries = [{"name": "Alice", "time": t, "preview": "hi", "link": "", "message_id": "1"}]
    mock_scan.return_value = {"100": {"campaign": "Kibwe", "code": "C00", "entries": entries}}
    # Fingerprint format: "{pid}:{time}" joined by "|"
    fp = f"100:{t}"
    state = {"last_queue_fingerprint": fp, "queue_post_count": 0,
             "last_queue_pin_id": None, "last_queue_daily_slots": []}
    post_queue_reminder(_qr_config(), state, now=now)
    # Fingerprint matched and not a daily slot → skipped
    assert state["queue_post_count"] == 0


@patch("scheduled.queue_reminder.post_topic_queues")
@patch("scheduled.queue_reminder.scan_transcripts")
def test_queue_reminder_posts_on_change(mock_scan, mock_ptq):
    now = datetime(2026, 4, 3, 9, 0, tzinfo=timezone.utc)
    t = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    entries = [{"name": "Alice", "time": t, "preview": "hi", "link": "", "message_id": "1"}]
    mock_scan.return_value = {"100": {"campaign": "Kibwe", "code": "C00", "entries": entries}}
    state = {"last_queue_fingerprint": "OLD", "queue_post_count": 0,
             "last_queue_pin_id": None, "last_queue_daily_slots": []}
    post_queue_reminder(_qr_config(), state, now=now)
    assert state["queue_post_count"] == 1

# ═══════════════════════════════════════════════════════════════════════════════
# scheduled/potw.py — guard conditions
# ═══════════════════════════════════════════════════════════════════════════════

from scheduled.potw import player_of_the_week


def _potw_config():
    return {
        "group_id": -1001, "bot_topic_id": 999,
        "gm_user_ids": [999],
        "topic_pairs": [{
            "pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
            "chat_topic_id": 21514, "gm_user_ids": [999],
        }]
    }

def _potw_state():
    return {"last_potw": {}, "post_timestamps": {}, "players": {}, "paused_campaigns": {}}


@patch("scheduled.potw.helpers")
def test_potw_skips_feature_disabled(mock_helpers):
    now = datetime(2026, 3, 29, 9, tzinfo=timezone.utc)
    mock_helpers.build_topic_maps = MagicMock(return_value=MagicMock(
        to_chat={"100": 21514}, to_name={"100": "Kibwe"}
    ))
    mock_helpers.feature_enabled.return_value = False
    mock_helpers.interval_elapsed.return_value = True
    mock_helpers.gm_ids_for_campaign.return_value = {999}
    mock_helpers.get_topic_timestamps.return_value = {}
    mock_helpers.POTW_INTERVAL_DAYS = 7
    mock_helpers.POTW_MIN_POSTS = 3
    mock_helpers.BOONS_PATH = "/nonexistent/boons.json"
    state = {"last_potw": {}}
    player_of_the_week(_potw_config(), state, now=now)
    assert "potw_history" not in state


@patch("scheduled.potw.helpers")
def test_potw_skips_interval_not_elapsed(mock_helpers):
    now = datetime(2026, 3, 29, 9, tzinfo=timezone.utc)
    mock_helpers.build_topic_maps = MagicMock(return_value=MagicMock(
        to_chat={"100": 21514}, to_name={"100": "Kibwe"}
    ))
    mock_helpers.feature_enabled.return_value = True
    mock_helpers.interval_elapsed.return_value = False
    mock_helpers.BOONS_PATH = "/nonexistent/boons.json"
    state = {"last_potw": {"100": "2026-03-29"}}
    player_of_the_week(_potw_config(), state, now=now)
    assert "potw_history" not in state


@patch("scheduled.potw.helpers")
def test_potw_skips_no_candidates(mock_helpers):
    now = datetime(2026, 3, 29, 9, tzinfo=timezone.utc)
    mock_helpers.build_topic_maps = MagicMock(return_value=MagicMock(
        to_chat={"100": 21514}, to_name={"100": "Kibwe"}
    ))
    mock_helpers.feature_enabled.return_value = True
    mock_helpers.interval_elapsed.return_value = True
    mock_helpers.gm_ids_for_campaign.return_value = {999}
    mock_helpers.get_topic_timestamps.return_value = {}
    mock_helpers.POTW_MIN_POSTS = 3
    mock_helpers.POTW_INTERVAL_DAYS = 7
    mock_helpers.BOONS_PATH = "/nonexistent/boons.json"
    state = {"last_potw": {}}
    with patch("scheduled.potw._gather_potw_candidates", return_value=[]):
        player_of_the_week(_potw_config(), state, now=now)
    assert "potw_history" not in state
