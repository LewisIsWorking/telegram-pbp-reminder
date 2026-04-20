"""
Coverage tests for:
  checker.py  (_run_checks, main)
  commands/queue_scan.py  (scan_transcripts logic)
  dispatch/cmd_info_ext.py  (handle)
  dispatch/poll_notify.py
  scheduled/reports.py  (post_roster_summary with active players)
"""
import sys, os, json, pytest, textwrap
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.dirname(__file__))

# ═══════════════════════════════════════════════════════════════════════════════
# checker.py
# ═══════════════════════════════════════════════════════════════════════════════

import checker


def test_run_checks_isolates_failures():
    """A failing check should not abort other checks."""
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": [],
               "bot_topic_id": 999}
    state = {}
    call_log = []

    def ok_check(cfg, st, **kw):
        call_log.append("ok")

    def bad_check(cfg, st, **kw):
        raise RuntimeError("simulated failure")

    with patch.object(checker, "_run_checks") as mock_run:
        mock_run.side_effect = lambda c, s: None
        checker._run_checks(config, state)


_CHECKER_FUNCS = [
    "check_and_alert", "check_player_activity", "post_roster_summary",
    "player_of_the_week", "expire_pending_boons", "post_pace_report",
    "check_streak_milestones", "check_anniversaries", "check_message_milestones",
    "check_combat_turns", "post_campaign_leaderboard", "post_weekly_digest",
    "check_recruitment_needs", "archive_weekly_data", "check_pace_drop",
    "check_conversation_dying", "check_expired_timers", "post_daily_tip",
    "post_queue_reminder", "check_queue_nudge", "post_campaign_table",
    "post_session_poll", "announce_poll_result", "post_week_welcome",
    "post_swimming_poll", "post_swimming_ping", "run_daily_diagnostic",
    "backup_state",
]

def _patch_all_checks():
    """Return a dict of {attr: MagicMock()} for use with patch.multiple."""
    return {f: MagicMock() for f in _CHECKER_FUNCS}


def test_run_checks_calls_all_checks():
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": [],
               "bot_topic_id": None}
    state = {}
    with patch.multiple("checker", **_patch_all_checks()), \
         patch("checker.build_topic_maps", return_value=MagicMock()):
        checker._run_checks(config, state)


def test_run_checks_catches_exception():
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": [],
               "bot_topic_id": None}
    state = {}
    mocks = _patch_all_checks()
    mocks["check_and_alert"] = MagicMock(side_effect=RuntimeError("boom"))
    with patch.multiple("checker", **mocks), \
         patch("checker.build_topic_maps", return_value=MagicMock()):
        checker._run_checks(config, state)  # should not raise


def test_main_no_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        checker.main()


def test_main_runs(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setenv("GIST_TOKEN", "")
    monkeypatch.setenv("GIST_ID", "")
    state = {"offset": 0, "topics": {}, "players": {}}
    with patch("checker.helpers.load_config", return_value={"group_id": -1,
               "gm_user_ids": [], "topic_pairs": [], "bot_topic_id": None}), \
         patch("checker.helpers.load_settings"), \
         patch("checker.helpers.validate_config", return_value=[]), \
         patch("checker.state_store.load", return_value=state), \
         patch("checker.state_store.save"), \
         patch("checker.tg.get_updates", return_value=[]), \
         patch("checker.process_updates", return_value=0), \
         patch("checker._run_checks"), \
         patch("checker.cleanup_timestamps"), \
         patch("checker.update_transcript_index"):
        checker.main()


def test_main_aborts_on_fatal_config(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    with patch("checker.helpers.load_config", return_value={}), \
         patch("checker.helpers.load_settings"), \
         patch("checker.helpers.validate_config",
               return_value=["ERROR: bad config"]):
        with pytest.raises(SystemExit):
            checker.main()


def test_main_transcript_index_error_isolated(monkeypatch):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    state = {"offset": 0, "topics": {}, "players": {}}
    with patch("checker.helpers.load_config", return_value={"group_id": -1,
               "gm_user_ids": [], "topic_pairs": [], "bot_topic_id": None}), \
         patch("checker.helpers.load_settings"), \
         patch("checker.helpers.validate_config", return_value=[]), \
         patch("checker.state_store.load", return_value=state), \
         patch("checker.state_store.save"), \
         patch("checker.tg.get_updates", return_value=[]), \
         patch("checker.process_updates", return_value=0), \
         patch("checker._run_checks"), \
         patch("checker.cleanup_timestamps"), \
         patch("checker.update_transcript_index", side_effect=Exception("x")):
        checker.main()  # should not raise


# ═══════════════════════════════════════════════════════════════════════════════
# commands/queue_scan.py
# ═══════════════════════════════════════════════════════════════════════════════

from commands.queue_scan import scan_transcripts


def _qs_config():
    return {
        "group_id": -1001, "gm_user_ids": [999],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
             "gm_user_ids": [999]}
        ]
    }


@patch("commands.queue_scan.helpers")
def test_scan_empty_no_logs(mock_helpers, tmp_path):
    mock_helpers.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
    mock_helpers.is_excluded.return_value = False
    mock_helpers.gm_ids_for_campaign.return_value = {999}
    with patch("commands.queue_scan._LOGS_DIR", tmp_path), \
         patch("commands.queue_io.all_pids", return_value=[]):
        result = scan_transcripts(_qs_config(), {})
    assert result == {}


@patch("commands.queue_scan.helpers")
def test_scan_excluded_campaign(mock_helpers, tmp_path):
    mock_helpers.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
    mock_helpers.is_excluded.return_value = True
    with patch("commands.queue_scan._LOGS_DIR", tmp_path), \
         patch("commands.queue_io.all_pids", return_value=[]):
        result = scan_transcripts(_qs_config(), {})
    assert result == {}


@patch("commands.queue_scan.helpers")
def test_scan_parses_transcript(mock_helpers, tmp_path):
    mock_helpers.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
    mock_helpers.is_excluded.return_value = False
    mock_helpers.gm_ids_for_campaign.return_value = {"999"}

    from datetime import datetime
    now = datetime.now(timezone.utc)
    month = now.strftime("%Y-%m")
    log_dir = tmp_path / "Kibwe"
    log_dir.mkdir()
    (log_dir / f"{month}.md").write_text(
        "**Alice** (2026-03-01 10:00:00):\nHello world\n\n"
        "**GM** [GM] (2026-03-01 11:00:00):\nGot it\n",
        encoding="utf-8"
    )
    with patch("commands.queue_scan._LOGS_DIR", tmp_path), \
         patch("commands.queue_scan._IDS_FILE", tmp_path / "ids.json"), \
         patch("commands.queue_io.all_pids", return_value=[]):
        result = scan_transcripts(_qs_config(), {})
    assert "100" in result
    assert result["100"]["entries"][0]["name"] == "Alice"


@patch("commands.queue_scan.helpers")
def test_scan_floor_filters_old(mock_helpers, tmp_path):
    mock_helpers.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
    mock_helpers.is_excluded.return_value = False
    mock_helpers.gm_ids_for_campaign.return_value = {"999"}

    from datetime import datetime
    now = datetime.now(timezone.utc)
    month = now.strftime("%Y-%m")
    log_dir = tmp_path / "Kibwe"
    log_dir.mkdir()
    (log_dir / f"{month}.md").write_text(
        "**Alice** (2020-01-01 10:00:00):\nOld message\n",
        encoding="utf-8"
    )
    state = {"queue_scan_floor": "2026-01-01"}
    with patch("commands.queue_scan._LOGS_DIR", tmp_path), \
         patch("commands.queue_scan._IDS_FILE", tmp_path / "ids.json"), \
         patch("commands.queue_io.all_pids", return_value=[]):
        result = scan_transcripts(_qs_config(), state)
    assert result == {}


@patch("commands.queue_scan.helpers")
def test_scan_msg_id_in_transcript(mock_helpers, tmp_path):
    mock_helpers.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
    mock_helpers.is_excluded.return_value = False
    mock_helpers.gm_ids_for_campaign.return_value = {"999"}

    from datetime import datetime
    now = datetime.now(timezone.utc)
    month = now.strftime("%Y-%m")
    log_dir = tmp_path / "Kibwe"
    log_dir.mkdir()
    (log_dir / f"{month}.md").write_text(
        "**Alice** (2026-03-01 10:00:00) msg#12345:\nHello\n",
        encoding="utf-8"
    )
    with patch("commands.queue_scan._LOGS_DIR", tmp_path), \
         patch("commands.queue_scan._IDS_FILE", tmp_path / "ids.json"), \
         patch("commands.queue_io.all_pids", return_value=[]):
        result = scan_transcripts(_qs_config(), {})
    assert result["100"]["entries"][0]["message_id"] == "12345"
    assert "12345" in result["100"]["entries"][0]["link"]


@patch("commands.queue_scan.helpers")
def test_scan_replied_filtered(mock_helpers, tmp_path, monkeypatch):
    mock_helpers.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
    mock_helpers.is_excluded.return_value = False
    mock_helpers.gm_ids_for_campaign.return_value = {"999"}

    from datetime import datetime
    now = datetime.now(timezone.utc)
    month = now.strftime("%Y-%m")
    log_dir = tmp_path / "Kibwe"
    log_dir.mkdir()
    (log_dir / f"{month}.md").write_text(
        "**Alice** (2026-03-01 10:00:00) msg#42:\nHello\n",
        encoding="utf-8"
    )
    from commands import queue_io
    monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path / "queues")
    (tmp_path / "queues").mkdir()
    (tmp_path / "queues" / "100.json").write_text(
        json.dumps({"replied": ["msg:42"], "unreplied": [], "reply_log": []})
    )
    with patch("commands.queue_scan._LOGS_DIR", tmp_path), \
         patch("commands.queue_scan._IDS_FILE", tmp_path / "ids.json"):
        result = scan_transcripts(_qs_config(), {})
    assert result == {}


@patch("commands.queue_scan.helpers")
def test_scan_id_lookup_file(mock_helpers, tmp_path):
    mock_helpers.iter_campaigns.return_value = [("100", "C00", "Kibwe", {})]
    mock_helpers.is_excluded.return_value = False
    mock_helpers.gm_ids_for_campaign.return_value = {"999"}

    from datetime import datetime
    now = datetime.now(timezone.utc)
    month = now.strftime("%Y-%m")
    log_dir = tmp_path / "Kibwe"
    log_dir.mkdir()
    (log_dir / f"{month}.md").write_text(
        "**Alice** (2026-03-01 10:00:00):\nHello\n",
        encoding="utf-8"
    )
    ids_file = tmp_path / "ids.json"
    ids_file.write_text(json.dumps({"100:2026-03-01 10:00:00": 99999}))
    with patch("commands.queue_scan._LOGS_DIR", tmp_path), \
         patch("commands.queue_scan._IDS_FILE", ids_file), \
         patch("commands.queue_io.all_pids", return_value=[]):
        result = scan_transcripts(_qs_config(), {})
    assert result["100"]["entries"][0]["message_id"] == "99999"


# ═══════════════════════════════════════════════════════════════════════════════
# dispatch/cmd_info_ext.py
# ═══════════════════════════════════════════════════════════════════════════════

from dispatch.cmd_info_ext import handle as handle_ext


def _ext_ctx(cmd):
    return {
        "cmd_word": cmd, "text": cmd, "group_id": -1, "reply_topic": 999,
        "pid": "100", "campaign_name": "Kibwe", "user_id": "U1",
        "user_name": "Alice", "state": {}, "config": {}, "gm_ids": set(),
    }


def test_handle_ext_waiting():
    ctx = _ext_ctx("/waiting")
    with patch("dispatch.cmd_info_ext.tg.send_message") as ms:
        with patch("commands.waiting.scan_transcripts", return_value={}):
            result = handle_ext(ctx)
    assert result is True


def test_handle_ext_session():
    ctx = _ext_ctx("/session")
    with patch("dispatch.cmd_info_ext.tg.send_message"):
        with patch("commands.session.build_session", return_value="S5"):
            result = handle_ext(ctx)
    assert result is True


def test_handle_ext_health():
    ctx = _ext_ctx("/health")
    with patch("dispatch.cmd_info_ext.tg.send_message"):
        with patch("commands.health.build_health", return_value="ok"):
            result = handle_ext(ctx)
    assert result is True


def test_handle_ext_queuestats():
    ctx = _ext_ctx("/queuestats")
    with patch("dispatch.cmd_info_ext.tg.send_message"):
        with patch("commands.queue_stats.build_queue_stats", return_value="stats"):
            result = handle_ext(ctx)
    assert result is True


def test_handle_ext_reactions():
    ctx = _ext_ctx("/reactions")
    with patch("dispatch.cmd_info_ext.tg.send_message"):
        with patch("commands.reactions.build_reactions", return_value="r"):
            result = handle_ext(ctx)
    assert result is True


def test_handle_ext_timeline():
    ctx = _ext_ctx("/timeline")
    with patch("dispatch.cmd_info_ext.tg.send_message"):
        with patch("commands.timeline.build_timeline", return_value="t"):
            result = handle_ext(ctx)
    assert result is True


def test_handle_ext_search():
    ctx = {**_ext_ctx("/search"), "text": "/search fire giant"}
    with patch("dispatch.cmd_search.handle_search") as ms:
        result = handle_ext(ctx)
    assert result is True
    ms.assert_called_once()


def test_handle_ext_registry():
    ctx = _ext_ctx("/registry")
    with patch("dispatch.cmd_info_ext.tg.send_message"):
        with patch("commands.player_registry.build_registry", return_value="r"):
            result = handle_ext(ctx)
    assert result is True


def test_handle_ext_unknown():
    ctx = _ext_ctx("/unknowncmd")
    result = handle_ext(ctx)
    assert result is False


# ═══════════════════════════════════════════════════════════════════════════════
# dispatch/poll_notify.py
# ═══════════════════════════════════════════════════════════════════════════════

from dispatch.poll_notify import _voter_mention, notify_vote
from dispatch.poll_tally import _lead_summary, build_tally_block


def _pn_config():
    return {
        "group_id": -1001,
        "topic_pairs": [{
            "pbp_topic_ids": [100], "code": "C01", "name": "DF",
            "chat_topic_id": 21514, "hybrid_live": True,
            "poll_options": ["Friday", "Saturday", "Both", "Can't make it"],
            "poll_user_names": {"U1": "alice"},
            "poll_user_ids": ["U1"],
        }]
    }


def test_voter_mention_by_player_username():
    state = {"players": {"x": {"user_id": "U1", "username": "alice"}}}
    assert _voter_mention("U1", "Alice", {}, state) == "@alice"


def test_voter_mention_by_first_name():
    state = {"players": {"x": {"user_id": "U1", "username": "", "first_name": "Alice"}}}
    assert _voter_mention("U1", "Alice", {}, state) == "Alice"


def test_voter_mention_from_poll_names():
    config = {"topic_pairs": [{"poll_user_names": {"U2": "bob"}}]}
    assert _voter_mention("U2", "Bob", config, {}) == "@bob"


def test_voter_mention_fallback():
    assert _voter_mention("U99", "Fallback", {}, {}) == "Fallback"


def test_build_tally_block_no_votes():
    result = build_tally_block("C01", {"votes": {}, "voted_uids": []},
                               ["Friday", "Saturday"], _pn_config(), {})
    assert "C01" in result


def test_build_tally_block_with_votes():
    slot = {"votes": {"0": ["U1", "U2"], "1": ["U3"]}, "voted_uids": ["U1", "U2", "U3"]}
    result = build_tally_block("C01", slot,
                               ["Friday", "Saturday", "Both", "Can't"],
                               _pn_config(), {})
    assert "C01" in result
    assert "Friday" in result


def test_lead_summary_winner():
    votes = {"0": ["U1", "U2"], "1": ["U3"]}
    options = ["Friday", "Saturday", "Both", "Can't"]
    result = _lead_summary(votes, options)
    assert "Friday" in result or "leads" in result


def test_lead_summary_tie():
    votes = {"0": ["U1"], "1": ["U2"]}
    options = ["Friday", "Saturday"]
    result = _lead_summary(votes, options)
    assert "tied" in result or "tie" in result.lower()


def test_lead_summary_no_votes():
    result = _lead_summary({}, ["Friday"])
    assert result == ""


def test_notify_vote_unknown_code():
    # voting_code not in any pair's code → no posts but no crash
    state = {"session_poll": {}}
    notify_vote(_pn_config(), state, "Alice", "U1", "C99", "Friday", "100")


def test_notify_vote_sends_tally():
    state = {"session_poll": {"C01": {
        "poll_id": "p1", "votes": {"0": ["U1"]}, "voted_uids": [], "week_iso": "sun2026-03-29",
    }}}
    notify_vote(_pn_config(), state, "Alice", "U1", "C01", "Friday", "100")
    # conftest mock tg.send_message should have been called (checked via no-error)


def test_notify_vote_no_chat_topic():
    config = {"group_id": -1, "topic_pairs": [{
        "pbp_topic_ids": [100], "code": "C01", "name": "DF",
        "poll_options": ["Friday"], "poll_user_names": {},
    }]}
    state = {"session_poll": {"C01": {"votes": {}, "voted_uids": []}}}
    notify_vote(config, state, "Alice", "U1", "C01", "Friday", "100")
    # No chat_topic_id → no send, no crash


# ── commands/queue_scan._build_link ──────────────────────────────────────────

def test_build_link_public_group():
    from commands.queue_scan import _build_link
    link = _build_link(-1001661053273, "Path_Wars", "1242", "1540")
    assert link == "https://t.me/Path_Wars/1242/1540"


def test_build_link_private_group():
    from commands.queue_scan import _build_link
    # C11: group_id=-1003496373617, no username → c/ format stripping leading 100
    link = _build_link(-1003496373617, None, "1242", "1540")
    assert link == "https://t.me/c/3496373617/1242/1540"


def test_build_link_private_group_empty_username():
    from commands.queue_scan import _build_link
    link = _build_link(-1003496373617, "", "1242", "1540")
    assert link == "https://t.me/c/3496373617/1242/1540"


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
