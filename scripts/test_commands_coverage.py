"""
Coverage tests for:
  commands/queue_io.py
  commands/player_registry.py
  scheduled/poll_result.py
  scheduled/diagnostic.py
  scheduled/reports.py  (partial — tg-calling functions mocked)
"""
import sys, os, json, pytest, tempfile
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

# ═══════════════════════════════════════════════════════════════════════════════
# commands/queue_io.py
# ═══════════════════════════════════════════════════════════════════════════════

from commands import queue_io


@pytest.fixture
def tmp_queues(tmp_path, monkeypatch):
    """Redirect queue_io file operations to a temp directory."""
    monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path)
    return tmp_path


def test_load_missing_returns_empty(tmp_queues):
    result = queue_io.load("999")
    assert result["unreplied"] == []
    assert result["replied"] == []
    assert result["reply_log"] == []


def test_load_existing(tmp_queues):
    data = {"pid": "100", "unreplied": [{"message_id": 1}], "replied": [], "reply_log": []}
    (tmp_queues / "100.json").write_text(json.dumps(data))
    result = queue_io.load("100")
    assert result["unreplied"][0]["message_id"] == 1


def test_load_corrupt_returns_empty(tmp_queues):
    (tmp_queues / "100.json").write_text("not json{{}")
    result = queue_io.load("100")
    assert result["unreplied"] == []


def test_save_creates_file(tmp_queues):
    cq = {"pid": "100", "unreplied": [], "replied": [], "reply_log": []}
    assert queue_io.save("100", cq) is True
    assert (tmp_queues / "100.json").exists()


def test_save_oserror(tmp_queues):
    with patch.object(Path, "write_text", side_effect=OSError("disk full")):
        result = queue_io.save("100", {})
    assert result is False


def test_all_pids_empty(tmp_queues):
    assert queue_io.all_pids() == []


def test_all_pids_with_files(tmp_queues):
    (tmp_queues / "100.json").write_text("{}")
    (tmp_queues / "200.json").write_text("{}")
    pids = queue_io.all_pids()
    assert set(pids) == {"100", "200"}


def test_all_pids_dir_missing(tmp_path, monkeypatch):
    missing = tmp_path / "nonexistent"
    monkeypatch.setattr(queue_io, "_QUEUES_DIR", missing)
    assert queue_io.all_pids() == []


def test_replied_set(tmp_queues):
    data = {"replied": ["msg:123", "2026-03-01 10:00:00"]}
    (tmp_queues / "100.json").write_text(json.dumps(data))
    rs = queue_io.replied_set("100")
    assert "msg:123" in rs


def test_mark_replied_adds_entries(tmp_queues):
    cq = {"pid": "100", "unreplied": [
        {"message_id": 42, "time": "2026-03-01 10:00:00"}
    ], "replied": [], "reply_log": []}
    (tmp_queues / "100.json").write_text(json.dumps(cq))
    queue_io.mark_replied("100", "msg:42", "2026-03-01 10:00:00",
                           {"msg_id": "42", "player": "Alice"})
    result = queue_io.load("100")
    assert "msg:42" in result["replied"]
    assert len(result["unreplied"]) == 0
    assert len(result["reply_log"]) == 1


def test_mark_replied_no_duplicate_keys(tmp_queues):
    cq = {"replied": ["msg:42"], "unreplied": [], "reply_log": []}
    (tmp_queues / "100.json").write_text(json.dumps(cq))
    queue_io.mark_replied("100", "msg:42", None, {"msg_id": "42"})
    result = queue_io.load("100")
    assert result["replied"].count("msg:42") == 1


def test_migrate_from_state(tmp_queues):
    state = {
        "gm_queue_replied": {"100": ["msg:1", "2026-03-01"]},
        "gm_queue": {"100": [{"message_id": 5}]},
        "gm_reply_log": [{"pid": "100", "msg_id": "1"}],
    }
    count = queue_io.migrate_from_state(state)
    assert count == 1
    result = queue_io.load("100")
    assert "msg:1" in result["replied"]


def test_migrate_skips_already_migrated(tmp_queues):
    state = {"gm_queue_replied": {"100": ["msg:1"]}}
    queue_io.migrate_from_state(state)  # first time
    count = queue_io.migrate_from_state(state)  # second time
    assert count == 0


# ═══════════════════════════════════════════════════════════════════════════════
# commands/player_registry.py
# ═══════════════════════════════════════════════════════════════════════════════

from commands.player_registry import (
    get_or_assign_id, get_player_id, format_id, build_registry
)


def test_get_or_assign_id_gm():
    state = {}
    pid = get_or_assign_id("100", "GM1", "Lewis", True, state)
    assert pid == 0


def test_get_or_assign_id_player():
    state = {}
    pid = get_or_assign_id("100", "U1", "Alice", False, state)
    assert pid == 1


def test_get_or_assign_id_sequential():
    state = {}
    get_or_assign_id("100", "U1", "Alice", False, state)
    pid2 = get_or_assign_id("100", "U2", "Bob", False, state)
    assert pid2 == 2


def test_get_or_assign_id_existing():
    state = {}
    pid1 = get_or_assign_id("100", "U1", "Alice", False, state)
    pid2 = get_or_assign_id("100", "U1", "Alice Updated", False, state)
    assert pid1 == pid2
    # Name updated
    assert state["player_registry"]["100"]["U1"]["name"] == "Alice Updated"


def test_get_player_id_found():
    state = {"player_registry": {"100": {"U1": {"id": 3, "name": "Alice"}}}}
    assert get_player_id("100", "U1", state) == 3


def test_get_player_id_not_found():
    assert get_player_id("100", "U99", {}) is None


def test_format_id():
    assert format_id(0) == "#00"
    assert format_id(1) == "#01"
    assert format_id(10) == "#10"


def test_build_registry_empty():
    result = build_registry("100", "Kibwe", {}, {})
    assert "No players" in result


@patch("commands.player_registry.helpers")
def test_build_registry_with_players(mock_helpers):
    mock_helpers.get_label.return_value = "C06: Kibwe"
    state = {
        "player_registry": {"100": {
            "U1": {"id": 1, "name": "Alice", "joined": "2026-01-01"},
            "U2": {"id": 2, "name": "Bob", "joined": "2026-01-02"},
        }},
        "players": {"100:U1": {}},
        "removed_players": {"100:U2": {}},
    }
    result = build_registry("100", "Kibwe", {}, state)
    assert "Alice" in result
    assert "Bob" in result
    assert "[removed]" in result
    assert "[inactive]" not in result or "Alice" not in result.split("[inactive]")[0]


# ═══════════════════════════════════════════════════════════════════════════════
# scheduled/poll_result.py
# ═══════════════════════════════════════════════════════════════════════════════

from scheduled.poll_result import announce_poll_result

_FRIDAY_3PM = datetime(2026, 4, 3, 15, 0, tzinfo=timezone.utc)  # Friday 15:00
_THURSDAY   = datetime(2026, 4, 2, 15, 0, tzinfo=timezone.utc)


def _pr_config():
    return {
        "group_id": -1001,
        "topic_pairs": [{
            "pbp_topic_ids": [100], "code": "C01",
            "name": "DF", "hybrid_live": True,
            "chat_topic_id": 21514,
            "poll_options": ["Friday", "Saturday", "Either", "Both", "Can't make it"],
            "allows_multiple_answers": False,
        }]
    }


def test_poll_result_skips_non_friday():
    state = {}
    announce_poll_result(_pr_config(), state, now=_THURSDAY)
    assert "poll_history" not in state


def test_poll_result_skips_before_3pm():
    morning = datetime(2026, 4, 3, 10, 0, tzinfo=timezone.utc)
    state = {}
    announce_poll_result(_pr_config(), state, now=morning)
    assert "poll_history" not in state


def test_poll_result_skips_non_hybrid():
    config = {"group_id": -1, "topic_pairs": [{
        "pbp_topic_ids": [100], "code": "C00", "name": "R",
        "chat_topic_id": 100,
    }]}
    state = {}
    announce_poll_result(config, state, now=_FRIDAY_3PM)
    assert "poll_history" not in state


def test_poll_result_skips_already_announced():
    state = {"session_poll": {"C01": {"result_announced": True, "votes": {}}}}
    announce_poll_result(_pr_config(), state, now=_FRIDAY_3PM)
    assert not state.get("poll_history", {}).get("C01")


def test_poll_result_skips_no_chat_topic():
    config = {"group_id": -1, "topic_pairs": [{
        "pbp_topic_ids": [100], "code": "C01",
        "hybrid_live": True, "poll_options": ["A"],
    }]}
    state = {"session_poll": {"C01": {"votes": {}}}}
    announce_poll_result(config, state, now=_FRIDAY_3PM)
    assert not state.get("poll_history", {}).get("C01")


def test_poll_result_winner():
    state = {"session_poll": {"C01": {
        "votes": {"0": ["U1", "U2"], "1": ["U3"]},
    }}}
    announce_poll_result(_pr_config(), state, now=_FRIDAY_3PM)
    assert state["session_poll"]["C01"].get("result_announced") is True
    assert "poll_history" in state


def test_poll_result_tie():
    state = {"session_poll": {"C01": {
        "votes": {"0": ["U1"], "1": ["U2"]},
    }}}
    announce_poll_result(_pr_config(), state, now=_FRIDAY_3PM)
    assert "poll_results" in state


def test_poll_result_no_votes():
    state = {"session_poll": {"C01": {"votes": {}}}}
    announce_poll_result(_pr_config(), state, now=_FRIDAY_3PM)
    # No votes — tally is "No votes"
    assert "poll_results" in state


def test_poll_result_with_history():
    state = {
        "session_poll": {"C01": {"votes": {"0": ["U1", "U2"]}}},
        "poll_history": {"C01": {"wins": {"0": 3}}},
    }
    announce_poll_result(_pr_config(), state, now=_FRIDAY_3PM)
    # All-time history should be shown (wins accumulated)
    assert state["poll_history"]["C01"]["wins"].get("0", 0) >= 3


# ═══════════════════════════════════════════════════════════════════════════════
# scheduled/diagnostic.py
# ═══════════════════════════════════════════════════════════════════════════════

from scheduled.diagnostic import run_daily_diagnostic, _gh_request, _fetch_run_log


def test_diagnostic_skips_wrong_hour():
    config = {"group_id": -1, "bot_topic_id": 999, "diagnostic_hour": 8}
    now = datetime(2026, 4, 3, 10, tzinfo=timezone.utc)  # hour=10, not 8
    state = {}
    run_daily_diagnostic(config, state, now=now)
    assert "last_diagnostic" not in state


def test_diagnostic_skips_already_run():
    config = {"group_id": -1, "bot_topic_id": 999, "diagnostic_hour": 8}
    now = datetime(2026, 4, 3, 8, tzinfo=timezone.utc)
    state = {"last_diagnostic": "2026-04-03"}
    run_daily_diagnostic(config, state, now=now)
    # Still "2026-04-03" — not run again
    assert state["last_diagnostic"] == "2026-04-03"


def test_diagnostic_skips_no_bot_topic():
    config = {"group_id": -1, "diagnostic_hour": 8}
    now = datetime(2026, 4, 3, 8, tzinfo=timezone.utc)
    state = {}
    run_daily_diagnostic(config, state, now=now)
    assert "last_diagnostic" not in state


def test_diagnostic_skips_no_gh_data():
    config = {"group_id": -1, "bot_topic_id": 999, "diagnostic_hour": 8}
    now = datetime(2026, 4, 3, 8, tzinfo=timezone.utc)
    state = {}
    with patch("scheduled.diagnostic._gh_request", return_value=None):
        run_daily_diagnostic(config, state, now=now)
    assert "last_diagnostic" not in state


def test_diagnostic_skips_no_recent_runs():
    config = {"group_id": -1, "bot_topic_id": 999, "diagnostic_hour": 8}
    now = datetime(2026, 4, 3, 8, tzinfo=timezone.utc)
    old_run = {"created_at": "2026-04-01T00:00:00Z", "id": 1}
    with patch("scheduled.diagnostic._gh_request", return_value={"workflow_runs": [old_run]}):
        run_daily_diagnostic({"group_id": -1, "bot_topic_id": 999, "diagnostic_hour": 8}, {}, now=now)


def test_diagnostic_runs_and_posts():
    config = {"group_id": -1, "bot_topic_id": 999, "diagnostic_hour": 8}
    now = datetime(2026, 4, 3, 8, tzinfo=timezone.utc)
    recent_run = {"created_at": "2026-04-03T07:00:00Z", "id": 123}
    state = {}
    with patch("scheduled.diagnostic._gh_request", return_value={"workflow_runs": [recent_run]}):
        with patch("scheduled.diagnostic._fetch_run_log", return_value="State loaded from files"):
            run_daily_diagnostic(config, state, now=now)
    assert state.get("last_diagnostic") == "2026-04-03"


def test_gh_request_success():
    m = MagicMock()
    m.read.return_value = json.dumps({"ok": True}).encode()
    with patch("scheduled.diagnostic.urllib.request.urlopen", return_value=m):
        result = _gh_request("/repos/x")
    assert result == {"ok": True}


def test_gh_request_error():
    with patch("scheduled.diagnostic.urllib.request.urlopen", side_effect=Exception("x")):
        assert _gh_request("/repos/x") is None


def test_fetch_run_log_success():
    import zipfile, io
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("0_check-inactivity.txt", "State loaded")
    buf.seek(0)
    m = MagicMock(); m.read.return_value = buf.read()
    with patch("scheduled.diagnostic.urllib.request.urlopen", return_value=m):
        result = _fetch_run_log(123)
    assert "State loaded" in result


def test_fetch_run_log_error():
    with patch("scheduled.diagnostic.urllib.request.urlopen", side_effect=Exception("x")):
        result = _fetch_run_log(123)
    assert result == ""


# ═══════════════════════════════════════════════════════════════════════════════
# scheduled/reports.py  — test post_roster_summary guard conditions
# ═══════════════════════════════════════════════════════════════════════════════

from scheduled.reports import post_roster_summary


def _rpt_config():
    return {
        "group_id": -1001,
        "bot_topic_id": 999,
        "gm_user_ids": [999],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C00", "name": "R",
             "gm_user_ids": [999], "chat_topic_id": 21514}
        ]
    }


@patch("scheduled.reports.helpers")
def test_roster_summary_skips_no_feature(mock_helpers):
    mock_helpers.build_topic_maps.return_value = MagicMock(
        to_chat={"100": 21514}, to_name={"100": "R"}
    )
    mock_helpers.players_by_campaign.return_value = {}
    mock_helpers.feature_enabled.return_value = False
    mock_helpers.interval_elapsed.return_value = True
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    state = {"last_roster": {}}
    post_roster_summary(_rpt_config(), state, now=now)


@patch("scheduled.reports.helpers")
def test_roster_summary_skips_interval_not_elapsed(mock_helpers):
    mock_helpers.build_topic_maps.return_value = MagicMock(
        to_chat={"100": 21514}, to_name={"100": "R"}
    )
    mock_helpers.players_by_campaign.return_value = {}
    mock_helpers.feature_enabled.return_value = True
    mock_helpers.interval_elapsed.return_value = False
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    state = {"last_roster": {"100": "2026-04-03"}}
    post_roster_summary(_rpt_config(), state, now=now)


@patch("scheduled.reports.helpers")
def test_roster_summary_skips_no_players(mock_helpers):
    mock_helpers.build_topic_maps.return_value = MagicMock(
        to_chat={"100": 21514}, to_name={"100": "R"}
    )
    mock_helpers.players_by_campaign.return_value = {"100": []}
    mock_helpers.feature_enabled.return_value = True
    mock_helpers.interval_elapsed.return_value = True
    mock_helpers.gm_ids_for_campaign.return_value = {999}
    mock_helpers.get_label.return_value = "C00: R"
    mock_helpers.get_characters.return_value = {}
    mock_helpers.get_topic_timestamps.return_value = {}
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    state = {"last_roster": {}, "message_counts": {}}
    post_roster_summary(_rpt_config(), state, now=now)
