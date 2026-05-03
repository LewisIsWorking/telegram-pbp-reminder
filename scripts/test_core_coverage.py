"""
Coverage tests for:
  commands/queue.py
  commands/markdone.py
  state.py  (gist/file I/O paths)
  scheduled/session_poll.py  (guard conditions)
  scheduled/queue_reminder.py  (guard conditions)
  scheduled/potw.py  (guard conditions)
"""
import sys, os, json, pytest, tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.dirname(__file__))

# ═══════════════════════════════════════════════════════════════════════════════
# commands/queue.py
# ═══════════════════════════════════════════════════════════════════════════════

from commands.queue import build_queue


def _q_config(priority_pid=None):
    pairs = [{"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe", "gm_user_ids": [999]}]
    if priority_pid:
        pairs[0]["queue_priority"] = True
    return {"group_id": -1, "gm_user_ids": [999], "topic_pairs": pairs}


@patch("commands.queue.scan_transcripts", return_value={})
def test_build_queue_empty(mock_scan):
    result = build_queue(_q_config(), {})
    assert "All caught up" in result


@patch("commands.queue.scan_transcripts")
def test_build_queue_with_entries(mock_scan):
    now = datetime.now(timezone.utc)
    t = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    mock_scan.return_value = {"100": {
        "campaign": "Kibwe", "code": "C00",
        "entries": [{"name": "Alice", "time": t, "preview": "Hello", "link": ""}]
    }}
    result = build_queue(_q_config(), {})
    assert "Alice" in result
    assert "C00" in result


@patch("commands.queue.scan_transcripts")
def test_build_queue_with_link(mock_scan):
    now = datetime.now(timezone.utc)
    t = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    mock_scan.return_value = {"100": {
        "campaign": "Kibwe", "code": "C00",
        "entries": [{"name": "Alice", "time": t, "preview": "Hi",
                     "link": "https://t.me/x/100/99"}]
    }}
    result = build_queue(_q_config(), {})
    assert "t.me" in result


@patch("commands.queue.scan_transcripts")
def test_build_queue_priority_first(mock_scan):
    now = datetime.now(timezone.utc)
    t = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    mock_scan.return_value = {
        "100": {"campaign": "Kibwe", "code": "C00",
                "entries": [{"name": "Alice", "time": t, "preview": "x", "link": ""}]},
        "200": {"campaign": "Other", "code": "C01",
                "entries": [{"name": "Bob", "time": t, "preview": "y", "link": ""}]},
    }
    config = {
        "group_id": -1, "gm_user_ids": [999],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
             "gm_user_ids": [999], "queue_priority": True},
            {"pbp_topic_ids": [200], "code": "C01", "name": "Other", "gm_user_ids": [999]},
        ]
    }
    result = build_queue(config, {})
    # Kibwe (priority) should appear before Other
    assert result.index("Kibwe") < result.index("Other")


@patch("commands.queue.scan_transcripts")
def test_build_queue_numeric_priority_ordering(mock_scan):
    """Numeric queue_priority: lower number = higher position (0 > 1 > default 2)."""
    now = datetime.now(timezone.utc)
    t = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    mock_scan.return_value = {
        "100": {"campaign": "DarkPockets", "code": "C11",
                "entries": [{"name": "A", "time": t, "preview": "x", "link": ""}]},
        "200": {"campaign": "Kibwe",      "code": "C06",
                "entries": [{"name": "B", "time": t, "preview": "y", "link": ""}]},
        "300": {"campaign": "Other",      "code": "C00",
                "entries": [{"name": "C", "time": t, "preview": "z", "link": ""}]},
    }
    config = {
        "group_id": -1, "gm_user_ids": [999],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C11", "name": "DarkPockets",
             "gm_user_ids": [999], "queue_priority": 0},
            {"pbp_topic_ids": [200], "code": "C06", "name": "Kibwe",
             "gm_user_ids": [999], "queue_priority": 1},
            {"pbp_topic_ids": [300], "code": "C00", "name": "Other", "gm_user_ids": [999]},
        ]
    }
    result = build_queue(config, {})
    assert result.index("DarkPockets") < result.index("Kibwe")
    assert result.index("Kibwe") < result.index("Other")


@patch("commands.queue.scan_transcripts")
def test_build_queue_with_scene(mock_scan):
    now = datetime.now(timezone.utc)
    t = (now - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    mock_scan.return_value = {"100": {
        "campaign": "Kibwe", "code": "C00",
        "entries": [{"name": "Alice", "time": t, "preview": "Hi", "link": ""}]
    }}
    state = {"current_scenes": {"100": "The Tower"}}
    result = build_queue(_q_config(), state)
    assert "The Tower" in result


@patch("commands.queue.scan_transcripts")
def test_build_queue_invalid_time(mock_scan):
    mock_scan.return_value = {"100": {
        "campaign": "Kibwe", "code": "C00",
        "entries": [{"name": "Alice", "time": "bad-time", "preview": "Hi", "link": ""}]
    }}
    result = build_queue(_q_config(), {})
    assert "Alice" in result  # should not crash


# ═══════════════════════════════════════════════════════════════════════════════
# commands/markdone.py
# ═══════════════════════════════════════════════════════════════════════════════

from commands.markdone import handle_markdone, _clear_entries, _clear_by_msg_id


def _md_ctx(text="/markdone", uid="GM1", entries=None):
    return {
        "cmd_word": text.split()[0],
        "text": text,
        "user_id": uid,
        "gm_ids": {"GM1"},
        "pid": "100",
        "group_id": -1,
        "thread_id": 999,
        "state": {},
        "config": {"group_id": -1, "gm_user_ids": [1]},
        "campaign_name": "Kibwe",
    }


def test_markdone_wrong_cmd():
    ctx = _md_ctx("/queue")
    assert handle_markdone(ctx) is False


def test_markdone_non_gm():
    ctx = _md_ctx(uid="U99")
    assert handle_markdone(ctx) is False


@patch("commands.markdone.scan_transcripts", return_value={})
def test_markdone_no_entries(mock_scan):
    ctx = _md_ctx()
    assert handle_markdone(ctx) is True


@patch("commands.markdone.scan_transcripts")
def test_markdone_all(mock_scan):
    mock_scan.return_value = {"100": {"entries": [
        {"message_id": "1", "time": "2026-03-01 10:00:00", "name": "Alice", "preview": "hi"},
        {"message_id": "2", "time": "2026-03-02 10:00:00", "name": "Bob", "preview": "yo"},
    ]}}
    ctx = _md_ctx("/markdone all")
    assert handle_markdone(ctx) is True


@patch("commands.markdone.scan_transcripts")
def test_markdone_by_position(mock_scan):
    mock_scan.return_value = {"100": {"entries": [
        {"message_id": "42", "time": "2026-03-01 10:00:00", "name": "Alice", "preview": "hi"},
    ]}}
    ctx = _md_ctx("/markdone 1")
    assert handle_markdone(ctx) is True


@patch("commands.markdone.scan_transcripts")
def test_markdone_position_out_of_range(mock_scan):
    mock_scan.return_value = {"100": {"entries": [
        {"message_id": "42", "time": "2026-03-01 10:00:00", "name": "Alice", "preview": "hi"},
    ]}}
    ctx = _md_ctx("/markdone 99")
    assert handle_markdone(ctx) is True


@patch("commands.markdone._clear_by_msg_id", return_value=True)
@patch("commands.markdone.scan_transcripts")
def test_markdone_by_msg_id_fallback(mock_scan, mock_clear):
    mock_scan.return_value = {"100": {"entries": []}}
    ctx = _md_ctx("/markdone 140368")
    assert handle_markdone(ctx) is True


@patch("commands.markdone._clear_by_msg_id", return_value=False)
@patch("commands.markdone.scan_transcripts")
def test_markdone_by_msg_id_not_found(mock_scan, mock_clear):
    mock_scan.return_value = {"100": {"entries": []}}
    ctx = _md_ctx("/markdone 140368")
    assert handle_markdone(ctx) is True


@patch("commands.markdone.scan_transcripts")
def test_markdone_url_extracts_id(mock_scan):
    mock_scan.return_value = {"100": {"entries": []}}
    ctx = _md_ctx("/markdone https://t.me/Path_Wars/40585/140368")
    with patch("commands.markdone._clear_by_msg_id", return_value=True):
        handle_markdone(ctx)


@patch("commands.markdone.scan_transcripts")
def test_markdone_no_arg_shows_usage(mock_scan):
    """No argument shows usage message and clears nothing."""
    mock_scan.return_value = {"100": {"entries": [
        {"message_id": "1", "time": "2026-03-01 10:00:00", "name": "Alice", "preview": "hi"},
    ]}}
    ctx = _md_ctx("/markdone")
    sent = []
    with patch("commands.markdone.tg.send_message", side_effect=lambda g,t,m: sent.append(m)):
        result = handle_markdone(ctx)
    assert result is True
    assert any("markdone" in m.lower() or "tip" in m.lower() or "usage" in m.lower() for m in sent), "Expected usage message"
    # Nothing should have been cleared
    assert mock_scan.call_count >= 1


@patch("commands.markdone.scan_transcripts")
def test_markdone_invalid_arg(mock_scan):
    mock_scan.return_value = {"100": {"entries": [
        {"message_id": "1", "time": "2026-03-01 10:00:00", "name": "Alice", "preview": "hi"},
    ]}}
    ctx = _md_ctx("/markdone notanumber")
    assert handle_markdone(ctx) is True


def test_clear_entries(tmp_path, monkeypatch):
    from commands import queue_io
    monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path)
    entries = [{"message_id": "42", "time": "2026-03-01 10:00:00",
                "name": "Alice", "preview": "hi"}]
    now = datetime(2026, 3, 27, tzinfo=timezone.utc)
    count = _clear_entries(entries, "100", {}, now)
    assert count == 1


def test_clear_by_msg_id_found(tmp_path, monkeypatch):
    from commands import queue_io
    monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path)
    cq = {"unreplied": [{"message_id": 42, "time": "2026-03-01 10:00:00",
                          "user_name": "Alice", "preview": "hi"}],
          "replied": [], "reply_log": []}
    (tmp_path / "100.json").write_text(json.dumps(cq))
    now = datetime(2026, 3, 27, tzinfo=timezone.utc)
    result = _clear_by_msg_id("42", "100", {}, now)
    assert result is True


def test_clear_by_msg_id_not_found(tmp_path, monkeypatch):
    from commands import queue_io
    monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path)
    now = datetime(2026, 3, 27, tzinfo=timezone.utc)
    result = _clear_by_msg_id("99999", "100", {}, now)
    assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
# state.py — gist and file I/O paths
# ═══════════════════════════════════════════════════════════════════════════════

import state as st


def test_load_falls_back_to_defaults(tmp_path, monkeypatch):
    monkeypatch.setattr(st, "_loaded_ok", False)
    with patch.object(st, "_load_from_files", return_value=None):
        with patch.object(st, "gist_load", return_value=None):
            result = st.load()
    assert "offset" in result


def test_save_refuses_if_not_loaded():
    with patch.object(st, "_loaded_ok", False):
        with patch.object(st, "_save_to_files") as mock_files:
            st.save({})
            mock_files.assert_not_called()


def test_load_from_files_missing_core(tmp_path):
    with patch.object(st, "_state_dir", return_value=tmp_path):
        result = st._load_from_files()
    assert result is None


def test_load_from_files_json_error(tmp_path):
    # Create all core partition files but one is corrupt
    for p in ["live", "players", "queue", "activity"]:
        (tmp_path / f"{p}.json").write_text("{}")
    (tmp_path / "live.json").write_text("not json")
    with patch.object(st, "_state_dir", return_value=tmp_path):
        result = st._load_from_files()
    assert result is None


def test_save_to_files(tmp_path):
    with patch.object(st, "_state_dir", return_value=tmp_path):
        with patch.object(st, "gist_save"):
            with patch.object(st, "_loaded_ok", True):
                st.save({"offset": 99, "players": {}})


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
