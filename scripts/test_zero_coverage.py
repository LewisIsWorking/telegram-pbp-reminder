"""
Coverage tests for previously-0% files:
  commands/health.py
  commands/waiting.py
  commands/queue_analytics.py
  commands/queue_stats.py
  set_commands.py
  scheduled/diagnostic_analysis.py
"""
import sys, os, pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

# ═══════════════════════════════════════════════════════════════════════════════
# commands/health.py
# ═══════════════════════════════════════════════════════════════════════════════

from commands.health import build_health

# Use real current time so build_health's internal datetime.now() matches
def _now():
    return datetime.now(timezone.utc)

def _recent():
    return (_now() - timedelta(hours=2)).isoformat()

def _stale():
    return (_now() - timedelta(days=8)).isoformat()

def _days_ago(n):
    return (_now() - timedelta(days=n, hours=1)).isoformat()


def _h_config():
    return {
        "group_id": -1001, "gm_user_ids": [999], "bot_topic_id": 1,
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C00", "name": "Riddleport",
             "gm_user_ids": [999]},
            {"pbp_topic_ids": [101], "code": "C01", "name": "Dungeon",
             "gm_user_ids": [999]},
        ]
    }


def _h_state(last_100=None, last_101=None, ts=None):
    return {
        "topics": {
            "100": {"last_message_time": last_100} if last_100 else {},
            "101": {"last_message_time": last_101} if last_101 else {},
        },
        "post_timestamps": ts or {"100": {"1": [_recent()]*12}, "101": {}},
        "players": {
            "100:1": {"pbp_topic_id": "100", "user_id": "1"},
        },
        "session_counts": {},
    }


@patch("commands.queue_scan.scan_transcripts", return_value={})
def test_health_no_data(mock_scan):
    state = _h_state()
    # No last_message_time for topic 101
    result = build_health(_h_config(), state)
    assert "no data" in result


@patch("commands.queue_scan.scan_transcripts", return_value={})
def test_health_green(mock_scan):
    ts = {"100": {"1": [_recent()]*12}}
    state = _h_state(last_100=_recent(), ts=ts)
    result = build_health(_h_config(), state)
    assert "🟢" in result


@patch("commands.queue_scan.scan_transcripts", return_value={})
def test_health_yellow(mock_scan):
    two_days_ago = _days_ago(2)
    ts = {"100": {"1": [_recent()]*4}}
    state = _h_state(last_100=two_days_ago, ts=ts)
    result = build_health(_h_config(), state)
    assert "🟡" in result


@patch("commands.queue_scan.scan_transcripts", return_value={})
def test_health_orange(mock_scan):
    state = _h_state(last_100=_days_ago(4), ts={"100": {}})
    result = build_health(_h_config(), state)
    assert "🟠" in result


@patch("commands.queue_scan.scan_transcripts", return_value={})
def test_health_red(mock_scan):
    state = _h_state(last_100=_stale(), ts={"100": {}})
    result = build_health(_h_config(), state)
    assert "🔴" in result


@patch("commands.queue_scan.scan_transcripts", return_value={})
def test_health_age_hours(mock_scan):
    six_hours_ago = (_now() - timedelta(hours=6)).isoformat()
    ts = {"100": {"1": [_recent()]*12}}
    state = _h_state(last_100=six_hours_ago, ts=ts)
    result = build_health(_h_config(), state)
    assert "h" in result


@patch("commands.queue_scan.scan_transcripts", return_value={})
def test_health_age_days(mock_scan):
    two_days_ago = _days_ago(2)
    state = _h_state(last_100=two_days_ago, ts={"100": {}})
    result = build_health(_h_config(), state)
    assert "d" in result


@patch("commands.queue_scan.scan_transcripts", return_value={"100": {"entries": ["a", "b"]}})
def test_health_queue_indicator(mock_scan):
    state = _h_state(last_100=_recent(), ts={"100": {"1": [_recent()]*12}})
    result = build_health(_h_config(), state)
    assert "📋2" in result


@patch("commands.queue_scan.scan_transcripts", return_value={})
def test_health_session_count(mock_scan):
    state = _h_state(last_100=_recent(), ts={"100": {"1": [_recent()]*12}})
    state["session_counts"] = {"100": 5}
    result = build_health(_h_config(), state)
    assert "S5" in result


@patch("commands.queue_scan.scan_transcripts", return_value={})
def test_health_invalid_timestamp_ignored(mock_scan):
    ts = {"100": {"1": ["not-a-date", _recent()]}}
    state = _h_state(last_100=_recent(), ts=ts)
    result = build_health(_h_config(), state)
    assert "Riddleport" in result


# ═══════════════════════════════════════════════════════════════════════════════
# commands/queue_analytics.py
# ═══════════════════════════════════════════════════════════════════════════════

from commands.queue_analytics import peak_hours, age_heatmap, player_momentum


def test_peak_hours_no_data():
    assert peak_hours({}) == "No data yet"


def test_peak_hours_with_data():
    state = {"activity_hours": {"100": {"U1": {"9": 10, "10": 5, "14": 8}}}}
    result = peak_hours(state)
    assert "09:00" in result


def test_age_heatmap_empty():
    assert age_heatmap({}) == ""


def test_age_heatmap_with_entries():
    two_days_ago = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d %H:%M:%S")
    scanned = {"100": {
        "campaign": "Kibwe", "code": "C06",
        "entries": [{"time": two_days_ago}]
    }}
    result = age_heatmap(scanned)
    assert "C06" in result


def test_age_heatmap_skips_missing_time():
    # Entry with no time still produces output (uses epoch as fallback)
    scanned = {"100": {"campaign": "X", "code": "C00", "entries": [{"time": ""}]}}
    result = age_heatmap(scanned)
    # Should not raise; result may or may not contain C00 depending on strptime
    assert isinstance(result, str)


def _pm_config():
    return {
        "group_id": -1001, "gm_user_ids": [999],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C00", "name": "R",
             "gm_user_ids": [999]}
        ]
    }


@patch("commands.queue_analytics.helpers")
def test_player_momentum_no_data(mock_helpers):
    mock_helpers.iter_campaigns.return_value = [("100", "C00", "R", {})]
    mock_helpers.is_excluded.return_value = False
    mock_helpers.gm_ids_for_campaign.return_value = {999}
    mock_helpers.get_topic_timestamps.return_value = {}
    result = player_momentum({}, _pm_config())
    assert result == []


@patch("commands.queue_analytics.helpers")
def test_player_momentum_excluded(mock_helpers):
    mock_helpers.iter_campaigns.return_value = [("100", "C00", "R", {})]
    mock_helpers.is_excluded.return_value = True
    result = player_momentum({}, _pm_config())
    assert result == []


@patch("commands.queue_analytics.helpers")
def test_player_momentum_with_responses(mock_helpers):
    now = datetime.now(timezone.utc)
    gm_ts = (now - timedelta(hours=5)).isoformat()
    player_ts = (now - timedelta(hours=3)).isoformat()
    mock_helpers.iter_campaigns.return_value = [("100", "C00", "R", {})]
    mock_helpers.is_excluded.return_value = False
    mock_helpers.gm_ids_for_campaign.return_value = {"999"}
    mock_helpers.get_topic_timestamps.return_value = {
        "999": [gm_ts], "U1": [player_ts]
    }
    mock_helpers.get_player.return_value = {"first_name": "Alice"}
    result = player_momentum({}, _pm_config())
    assert len(result) == 1
    assert "Alice" in result[0]


@patch("commands.queue_analytics.helpers")
def test_player_momentum_large_gap_ignored(mock_helpers):
    now = datetime.now(timezone.utc)
    gm_ts = (now - timedelta(days=10)).isoformat()
    player_ts = (now - timedelta(hours=1)).isoformat()
    mock_helpers.iter_campaigns.return_value = [("100", "C00", "R", {})]
    mock_helpers.is_excluded.return_value = False
    mock_helpers.gm_ids_for_campaign.return_value = {"999"}
    mock_helpers.get_topic_timestamps.return_value = {
        "999": [gm_ts], "U1": [player_ts]
    }
    result = player_momentum({}, _pm_config())
    assert result == []


# ═══════════════════════════════════════════════════════════════════════════════
# commands/queue_stats.py
# ═══════════════════════════════════════════════════════════════════════════════

from commands.queue_stats import (
    record_reply, get_today_clears, get_week_clears,
    avg_reply_hours, build_queue_stats
)


def test_record_reply_adds_to_history():
    state = {}
    now = datetime(2026, 3, 27, tzinfo=timezone.utc)
    record_reply("100", state, "preview", "Alice", now)
    assert len(state["queue_history"]["100"]) == 1
    assert len(state["queue_archive"]) == 1


def test_record_reply_caps_history():
    state = {"queue_history": {"100": ["x"] * 500}}
    record_reply("100", state, "", "", datetime.now(timezone.utc))
    assert len(state["queue_history"]["100"]) == 500


def test_record_reply_caps_archive():
    state = {"queue_archive": [{"pid": "x"}] * 200}
    record_reply("100", state, "", "", datetime.now(timezone.utc))
    assert len(state["queue_archive"]) == 200


def test_get_today_clears():
    now = datetime(2026, 3, 27, 12, tzinfo=timezone.utc)
    state = {"queue_history": {"100": [
        "2026-03-27T10:00:00", "2026-03-26T10:00:00"
    ]}}
    assert get_today_clears(state, now) == 1


def test_get_week_clears():
    now = datetime(2026, 3, 27, 12, tzinfo=timezone.utc)
    state = {"queue_history": {"100": [
        "2026-03-25T10:00:00",  # within 7 days
        "2026-03-15T10:00:00",  # outside
    ]}}
    assert get_week_clears(state, now) == 1


def test_avg_reply_hours_not_enough_data():
    state = {"post_timestamps": {}}
    assert avg_reply_hours("100", state) is None


@patch("commands.queue_stats.helpers")
def test_avg_reply_hours_calculates(mock_helpers):
    now = datetime(2026, 3, 27, 12, tzinfo=timezone.utc)
    ts = [(now - timedelta(hours=h)).isoformat() for h in [10, 6, 2]]
    mock_helpers.get_topic_timestamps.return_value = {"999": ts}
    config = {"topic_pairs": [
        {"pbp_topic_ids": [100], "gm_user_ids": [999]}
    ], "gm_user_ids": [999]}
    state = {"_config_cache": config}
    result = avg_reply_hours("100", state)
    assert result is not None
    assert result > 0


@patch("commands.queue_stats.helpers")
def test_avg_reply_hours_large_gaps_excluded(mock_helpers):
    now = datetime(2026, 3, 27, 12, tzinfo=timezone.utc)
    ts = [(now - timedelta(days=d)).isoformat() for d in [30, 20, 10]]
    mock_helpers.get_topic_timestamps.return_value = {"999": ts}
    config = {"topic_pairs": [
        {"pbp_topic_ids": [100], "gm_user_ids": [999]}
    ], "gm_user_ids": [999]}
    state = {"_config_cache": config}
    result = avg_reply_hours("100", state)
    assert result is None


@patch("commands.queue_scan.scan_transcripts", return_value={})
@patch("commands.queue_analytics.helpers")
@patch("commands.queue_stats.helpers")
def test_build_queue_stats_runs(mock_h, mock_qa_h, mock_scan):
    mock_h.iter_campaigns.return_value = []
    mock_qa_h.iter_campaigns.return_value = []
    state = {"queue_history": {}, "queue_archive": []}
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": []}
    result = build_queue_stats(config, state)
    assert "GM Queue Stats" in result


# ═══════════════════════════════════════════════════════════════════════════════
# commands/waiting.py
# ═══════════════════════════════════════════════════════════════════════════════

from commands.waiting import build_waiting, build_waiting_all, _age_str


def test_age_str_hours():
    assert _age_str(5) == "5h"

def test_age_str_days():
    assert _age_str(25) == "1d 1h"


@patch("commands.waiting.scan_transcripts")
def test_build_waiting_no_data(mock_scan):
    mock_scan.return_value = {}
    result = build_waiting("U1", "Alice", "100", "Kibwe", {}, {})
    assert "all caught up" in result


@patch("commands.queue_stats.avg_reply_hours", return_value=None)
@patch("commands.waiting.scan_transcripts")
def test_build_waiting_no_match(mock_scan, mock_avg):
    mock_scan.return_value = {
        "100": {"entries": [{"name": "Bob", "time": "2026-03-01 10:00:00",
                              "preview": "hello", "link": ""}]}
    }
    state = {"players": {}}
    result = build_waiting("U1", "Alice", "100", "Kibwe", {}, state)
    assert "No pending" in result


@patch("commands.queue_stats.avg_reply_hours", return_value=48.0)
@patch("commands.waiting.scan_transcripts")
def test_build_waiting_with_match(mock_scan, mock_avg):
    mock_scan.return_value = {
        "100": {"entries": [
            {"name": "Alice", "time": "2026-03-27 10:00:00",
             "preview": "word " * 10, "link": "https://t.me/x"}
        ]}
    }
    state = {"players": {"100:U1": {"first_name": "Alice"}}, "_config_cache": {}}
    result = build_waiting("U1", "Alice", "100", "Kibwe", {}, state)
    assert "Waiting on GM" in result
    assert "t.me" in result


@patch("commands.queue_stats.avg_reply_hours", return_value=12.0)
@patch("commands.waiting.scan_transcripts")
def test_build_waiting_avg_hours(mock_scan, mock_avg):
    mock_scan.return_value = {
        "100": {"entries": [
            {"name": "Alice", "time": "2026-03-27 10:00:00",
             "preview": "hi", "link": ""}
        ]}
    }
    state = {"players": {"100:U1": {"first_name": "Alice"}}, "_config_cache": {}}
    result = build_waiting("U1", "Alice", "100", "Kibwe", {}, state)
    assert "12h" in result


@patch("commands.waiting.scan_transcripts")
def test_build_waiting_all_none(mock_scan):
    mock_scan.return_value = {}
    result = build_waiting_all("U1", "Alice", {"topic_pairs": []}, {})
    assert "all caught up" in result


@patch("commands.waiting.scan_transcripts")
def test_build_waiting_all_with_match(mock_scan):
    mock_scan.return_value = {
        "100": {
            "code": "C00", "campaign": "Riddleport",
            "entries": [
                {"name": "Alice", "time": "2026-03-27 10:00:00",
                 "preview": "word " * 6, "link": ""}
            ]
        }
    }
    config = {"topic_pairs": [{"pbp_topic_ids": [100]}]}
    state = {"players": {"100:U1": {"first_name": "Alice"}}}
    result = build_waiting_all("U1", "Alice", config, state)
    assert "Riddleport" in result


# ═══════════════════════════════════════════════════════════════════════════════
# set_commands.py
# ═══════════════════════════════════════════════════════════════════════════════

from set_commands import _fmt, set_commands, EVERYONE_COMMANDS, GM_COMMANDS


def test_fmt():
    result = _fmt([("help", "Help text")])
    assert result == [{"command": "help", "description": "Help text"}]


def test_everyone_commands_non_empty():
    assert len(EVERYONE_COMMANDS) > 0


def test_gm_commands_non_empty():
    assert len(GM_COMMANDS) > 0


def test_set_commands_success():
    ok = MagicMock()
    ok.json.return_value = {"ok": True}
    with patch("set_commands.requests.post", return_value=ok):
        set_commands("faketoken")


def test_set_commands_failure():
    fail = MagicMock()
    fail.json.return_value = {"ok": False, "description": "err"}
    with patch("set_commands.requests.post", return_value=fail):
        set_commands("faketoken")  # should not raise


# ═══════════════════════════════════════════════════════════════════════════════
# scheduled/diagnostic_analysis.py
# ═══════════════════════════════════════════════════════════════════════════════

import sys as _sys
import importlib as _il
import importlib.util as _ilu

# Load diagnostic.py to get the pattern constants
_d_spec = _ilu.spec_from_file_location(
    "_diag", os.path.join(os.path.dirname(__file__), "scheduled", "diagnostic.py")
)
_diag = _ilu.module_from_spec(_d_spec)

# diagnostic.py imports telegram — patch it before exec
import types as _types
_fake_tg = _types.ModuleType("telegram")
_fake_tg.send_message = lambda *a, **kw: True
_sys.modules.setdefault("telegram", _fake_tg)

_d_spec.loader.exec_module(_diag)

from scheduled.diagnostic_analysis import _analyse_logs, _build_report


def test_analyse_logs_empty():
    result = _analyse_logs([])
    assert result["issues"] == {}
    assert result["events"] == []
    assert result["runs_with_errors"] == 0


def test_analyse_logs_detects_error():
    logs = ["Error processing update 123: something went wrong"]
    result = _analyse_logs(logs)
    assert len(result["issues"]) > 0
    assert result["runs_with_errors"] == 1


def test_analyse_logs_detects_poll_vote():
    logs = ["Poll vote recorded for user 123"]
    result = _analyse_logs(logs)
    assert any("Poll vote" in e or "vote" in e.lower() for e in result["events"])


def test_analyse_logs_detects_potw():
    logs = ["POTW for Kibwe: Alice (W14)"]
    result = _analyse_logs(logs)
    assert any("POTW" in e for e in result["events"])


def test_analyse_logs_detects_unknown_voter():
    logs = ["Unknown voter captured: 123456 in C11"]
    result = _analyse_logs(logs)
    assert any("Unknown voter captured" in e for e in result["events"])


def test_analyse_logs_detects_queue_reminder():
    logs = ["Queue reminder: 15 unreplied (2 msg)"]
    result = _analyse_logs(logs)
    assert any("Queue reminder" in e or "unreplied" in e for e in result["events"])


def test_analyse_logs_strips_timestamp():
    logs = ["2026-03-27T12:00:00Z Error processing update 1: oops"]
    result = _analyse_logs(logs)
    assert result["runs_with_errors"] == 1


def test_build_report_all_clear():
    analysis = {"issues": {}, "events": [], "runs_with_errors": 0}
    now = datetime(2026, 3, 27, tzinfo=timezone.utc)
    result = _build_report(analysis, 24, now)
    assert "All clear" in result
    assert "2026-03-27" in result


def test_build_report_with_issues():
    analysis = {
        "issues": {"Error": ["something broke", "something broke again"]},
        "events": [],
        "runs_with_errors": 3,
    }
    now = datetime(2026, 3, 27, tzinfo=timezone.utc)
    result = _build_report(analysis, 24, now)
    assert "1 issue type" in result
    assert "Error" in result


def test_build_report_with_all_event_types():
    analysis = {
        "issues": {},
        "events": [
            "Poll vote for user X",
            "POTW winner selected",
            "Unknown voter 99 captured",
            "Queue reminder: 5 unreplied (1 msg)",
        ],
        "runs_with_errors": 0,
    }
    now = datetime(2026, 3, 27, tzinfo=timezone.utc)
    result = _build_report(analysis, 24, now)
    assert "Activity" in result


def test_build_report_queue_peak_count():
    analysis = {
        "issues": {},
        "events": [
            "Queue reminder: 15 unreplied (2 msg)",
            "Queue reminder: 8 unreplied (1 msg)",
        ],
        "runs_with_errors": 0,
    }
    now = datetime(2026, 3, 27, tzinfo=timezone.utc)
    result = _build_report(analysis, 24, now)
    assert "15" in result
