"""
Coverage tests for:
  boons/display.py
  scheduled/week_welcome.py
  scheduled/queue_nudge.py
  scheduled/swimming_poll.py
  post_changelog.py
"""
import sys, os, pytest, importlib.util
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

# ═══════════════════════════════════════════════════════════════════════════════
# boons/display.py
# ═══════════════════════════════════════════════════════════════════════════════

from boons.display import build_boons, build_boons_all


def test_build_boons_empty():
    assert "No boons" in build_boons("100", "U1", "Kibwe", {})


def test_build_boons_with_boons():
    state = {"player_boons": {"100": {"U1": [
        {"text": "A turtle", "date": "2026-03-01", "week": "W10", "campaign": "Kibwe"},
        {"text": "A coin",   "date": "2026-03-08", "week": "W11", "campaign": "Kibwe"},
    ]}}}
    result = build_boons("100", "U1", "Kibwe", state)
    assert "A turtle" in result
    assert "A coin" in result
    assert "W10" in result
    assert "Kibwe" in result


def test_build_boons_all_empty():
    assert "No boons" in build_boons_all("U1", {})


def test_build_boons_all_with_boons():
    state = {"player_boons": {
        "100": {"U1": [{"text": "Boon A", "date": "2026-03-01",
                        "week": "W10", "campaign": "Kibwe"}]},
        "200": {"U1": [{"text": "Boon B", "date": "2026-03-08",
                        "week": "W11", "campaign": "Riddleport"}]},
    }}
    result = build_boons_all("U1", state)
    assert "Boon A" in result
    assert "Boon B" in result
    assert "Kibwe" in result
    assert "Riddleport" in result


def test_build_boons_all_other_player_ignored():
    state = {"player_boons": {"100": {
        "U1": [{"text": "Mine", "date": "2026-03-01", "week": "W1", "campaign": "X"}],
        "U2": [{"text": "Theirs", "date": "2026-03-01", "week": "W1", "campaign": "X"}],
    }}}
    result = build_boons_all("U1", state)
    assert "Mine" in result
    assert "Theirs" not in result


# ═══════════════════════════════════════════════════════════════════════════════
# scheduled/week_welcome.py
# ═══════════════════════════════════════════════════════════════════════════════

from scheduled.week_welcome import post_week_welcome

_SUNDAY = datetime(2026, 3, 29, 8, 0, tzinfo=timezone.utc)  # Sunday after 7am
_FRIDAY = datetime(2026, 4, 3, 8, 0, tzinfo=timezone.utc)


def _ww_config():
    return {"group_id": -1001, "bot_topic_id": 999, "poll_post_hour": 7}


def test_week_welcome_skips_non_sunday():
    state = {}
    post_week_welcome(_ww_config(), state, now=_FRIDAY)
    assert "last_week_welcome" not in state


def test_week_welcome_skips_before_post_hour():
    early = datetime(2026, 3, 29, 5, 0, tzinfo=timezone.utc)
    state = {}
    post_week_welcome(_ww_config(), state, now=early)
    assert "last_week_welcome" not in state


def test_week_welcome_skips_if_already_posted():
    state = {"last_week_welcome": "sun2026-03-29"}
    post_week_welcome(_ww_config(), state, now=_SUNDAY)
    assert state["last_week_welcome"] == "sun2026-03-29"


def test_week_welcome_skips_no_bot_topic():
    config = {"group_id": -1001, "poll_post_hour": 7}
    state = {}
    post_week_welcome(config, state, now=_SUNDAY)
    assert "last_week_welcome" not in state


def test_week_welcome_posts_on_sunday():
    state = {}
    post_week_welcome(_ww_config(), state, now=_SUNDAY)
    assert state.get("last_week_welcome") == "sun2026-03-29"


# ═══════════════════════════════════════════════════════════════════════════════
# scheduled/queue_nudge.py
# ═══════════════════════════════════════════════════════════════════════════════

from scheduled.queue_nudge import check_queue_nudge, _gm_mentions


def _qn_config():
    return {
        "group_id": -1001, "bot_topic_id": 999,
        "gm_user_ids": [999],
        "topic_pairs": [
            {"pbp_topic_ids": [100], "code": "C00", "name": "Kibwe",
             "gm_user_ids": [999]}
        ]
    }


def test_gm_mentions_with_username():
    state = {"players": {"x": {"user_id": "999", "username": "pathwars"}}}
    result = _gm_mentions(_qn_config(), state, "100")
    assert "@pathwars" in result


def test_gm_mentions_with_first_name_only():
    state = {"players": {"x": {"user_id": "999", "first_name": "Lewis", "username": ""}}}
    result = _gm_mentions(_qn_config(), state, "100")
    assert "Lewis" in result


def test_gm_mentions_fallback():
    state = {"players": {}}
    result = _gm_mentions(_qn_config(), state, "100")
    assert "@PathWars" in result


def test_gm_mentions_no_gm_ids():
    config = {"group_id": -1, "topic_pairs": [{"pbp_topic_ids": [100], "gm_user_ids": []}]}
    result = _gm_mentions(config, {}, "100")
    assert "@PathWars" in result


def test_queue_nudge_no_bot_topic():
    config = {"group_id": -1001}
    state = {}
    check_queue_nudge(config, state)
    assert "queue_nudged" not in state


@patch("scheduled.queue_nudge.scan_transcripts", return_value={})
def test_queue_nudge_no_entries(mock_scan):
    state = {}
    check_queue_nudge(_qn_config(), state)
    assert state.get("queue_nudged", {}) == {}


@patch("scheduled.queue_nudge.scan_transcripts")
def test_queue_nudge_fresh_entry_not_nudged(mock_scan):
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    fresh = (now - timedelta(hours=10)).strftime("%Y-%m-%d %H:%M:%S")
    mock_scan.return_value = {"100": {
        "campaign": "Kibwe", "code": "C00",
        "entries": [{"name": "Alice", "time": fresh, "link": ""}]
    }}
    state = {}
    check_queue_nudge(_qn_config(), state, now=now)
    assert not state.get("queue_nudged")


@patch("scheduled.queue_nudge.scan_transcripts")
def test_queue_nudge_stale_entry_nudged(mock_scan):
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=55)).strftime("%Y-%m-%d %H:%M:%S")
    mock_scan.return_value = {"100": {
        "campaign": "Kibwe", "code": "C00",
        "entries": [{"name": "Alice", "time": stale, "link": "https://t.me/x"}]
    }}
    state = {}
    check_queue_nudge(_qn_config(), state, now=now)
    assert len(state.get("queue_nudged", {})) == 1


@patch("scheduled.queue_nudge.scan_transcripts")
def test_queue_nudge_already_nudged_skipped(mock_scan):
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=55)).strftime("%Y-%m-%d %H:%M:%S")
    mock_scan.return_value = {"100": {
        "campaign": "Kibwe", "code": "C00",
        "entries": [{"name": "Alice", "time": stale, "link": ""}]
    }}
    state = {"queue_nudged": {"100:Alice": now.isoformat()}}
    check_queue_nudge(_qn_config(), state, now=now)
    # Count should not increase
    assert len(state["queue_nudged"]) == 1


@patch("scheduled.queue_nudge.scan_transcripts")
def test_queue_nudge_invalid_time_skipped(mock_scan):
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    mock_scan.return_value = {"100": {
        "campaign": "Kibwe", "code": "C00",
        "entries": [{"name": "Alice", "time": "not-a-date", "link": ""}]
    }}
    state = {}
    check_queue_nudge(_qn_config(), state, now=now)
    assert not state.get("queue_nudged")


@patch("scheduled.queue_nudge.scan_transcripts")
def test_queue_nudge_trims_old_entries(mock_scan):
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    stale = (now - timedelta(hours=55)).strftime("%Y-%m-%d %H:%M:%S")
    # 205 pre-existing entries + 1 new stale entry triggers the trim
    mock_scan.return_value = {"100": {
        "campaign": "Kibwe", "code": "C00",
        "entries": [{"name": "Zara", "time": stale, "link": ""}]
    }}
    state = {"queue_nudged": {f"k{i}": now.isoformat() for i in range(205)}}
    check_queue_nudge(_qn_config(), state, now=now)
    assert len(state["queue_nudged"]) <= 201  # trimmed to 200 + possibly 1 new


# ═══════════════════════════════════════════════════════════════════════════════
# scheduled/swimming_poll.py
# ═══════════════════════════════════════════════════════════════════════════════

from scheduled.swimming_poll import post_swimming_poll, post_swimming_ping

_SWIM_SUNDAY = datetime(2026, 3, 29, 8, 0, tzinfo=timezone.utc)
_SWIM_MONDAY = datetime(2026, 3, 30, 8, 0, tzinfo=timezone.utc)


def test_swimming_poll_skips_non_sunday():
    state = {}
    post_swimming_poll({}, state, now=_SWIM_MONDAY)
    assert "swimming_poll" not in state


def test_swimming_poll_skips_before_hour():
    early = datetime(2026, 3, 29, 4, 0, tzinfo=timezone.utc)
    state = {}
    post_swimming_poll({"poll_post_hour": 7}, state, now=early)
    assert "swimming_poll" not in state


def test_swimming_poll_skips_already_posted():
    state = {"swimming_poll": {"week_iso": "sun2026-03-29"}}
    post_swimming_poll({"poll_post_hour": 7}, state, now=_SWIM_SUNDAY)
    assert state["swimming_poll"]["week_iso"] == "sun2026-03-29"


def test_swimming_poll_posts_on_sunday():
    state = {}
    post_swimming_poll({"poll_post_hour": 7}, state, now=_SWIM_SUNDAY)
    sp = state.get("swimming_poll", {})
    assert sp.get("week_iso") == "sun2026-03-29"
    assert sp.get("poll_message_id") == 99998  # conftest mock


def test_swimming_poll_send_failure_no_state_update():
    state = {}
    with patch("scheduled.swimming_poll.tg.send_poll", return_value=None):
        post_swimming_poll({"poll_post_hour": 7}, state, now=_SWIM_SUNDAY)
    assert "swimming_poll" not in state or not state.get("swimming_poll", {}).get("week_iso")


def test_swimming_ping_skips_wrong_week():
    state = {"swimming_poll": {"week_iso": "sun2026-03-22"}}  # last week
    post_swimming_ping({}, state, now=_SWIM_MONDAY)
    assert state["swimming_poll"].get("last_ping_day", -1) == -1


def test_swimming_ping_skips_already_pinged():
    today = _SWIM_MONDAY.toordinal()
    state = {"swimming_poll": {
        "week_iso": "sun2026-03-29",
        "last_ping_day": today,
        "voted_uids": [],
    }}
    post_swimming_ping({}, state, now=_SWIM_MONDAY)


def test_swimming_ping_all_voted_no_ping():
    # All swimmers voted
    from scheduled.swimming_poll import _SWIMMERS
    all_uids = [str(uid) for uid, _ in _SWIMMERS]
    state = {"swimming_poll": {
        "week_iso": "sun2026-03-29",
        "last_ping_day": -1,
        "voted_uids": all_uids,
        "poll_message_id": 999,
    }}
    post_swimming_ping({}, state, now=_SWIM_MONDAY)
    # Should not update last_ping_day since nobody to ping
    assert state["swimming_poll"]["last_ping_day"] == -1


def test_swimming_ping_sends_for_unvoted():
    state = {"swimming_poll": {
        "week_iso": "sun2026-03-29",
        "last_ping_day": -1,
        "voted_uids": [],
        "poll_message_id": 1234,
    }}
    post_swimming_ping({}, state, now=_SWIM_MONDAY)
    assert state["swimming_poll"]["last_ping_day"] == _SWIM_MONDAY.toordinal()


# ═══════════════════════════════════════════════════════════════════════════════
# post_changelog.py
# ═══════════════════════════════════════════════════════════════════════════════

_pc_spec = importlib.util.spec_from_file_location(
    "_post_changelog",
    os.path.join(os.path.dirname(__file__), "post_changelog.py")
)
_pc = importlib.util.module_from_spec(_pc_spec)
_pc_spec.loader.exec_module(_pc)


def test_read_latest_entry_empty(tmp_path):
    f = tmp_path / "CHANGELOG.md"
    f.write_text("No version headers here")
    assert _pc.read_latest_entry(f) == ("", "")


def test_read_latest_entry_parses(tmp_path):
    f = tmp_path / "CHANGELOG.md"
    f.write_text("## [1.2.3] - 2026-03-01\n\nSome changes here\n\n## [1.2.2]\nOld")
    header, body = _pc.read_latest_entry(f)
    assert "1.2.3" in header
    assert "Some changes" in body


def test_markdown_to_telegram_basic():
    result = _pc.markdown_to_telegram("## [1.0.0] - 2026-03-01", "Hello world")
    assert "1.0.0" in result
    assert "2026-03-01" in result
    assert "Hello world" in result


def test_markdown_to_telegram_no_date():
    result = _pc.markdown_to_telegram("## [1.0.0]", "Body")
    assert "1.0.0" in result


def test_markdown_to_telegram_escapes_angle_brackets():
    result = _pc.markdown_to_telegram("## [1.0.0]", "Age: <6h")
    assert "&lt;6h" in result or "<6h" not in result


def test_markdown_to_telegram_h3_to_bold():
    result = _pc.markdown_to_telegram("## [1.0.0]", "### Added\nSome stuff")
    assert "<b>Added</b>" in result


def test_markdown_to_telegram_bold():
    result = _pc.markdown_to_telegram("## [1.0.0]", "**important** thing")
    assert "<b>important</b>" in result


def test_markdown_to_telegram_code():
    result = _pc.markdown_to_telegram("## [1.0.0]", "`some_code`")
    assert "<code>some_code</code>" in result


def test_post_to_telegram_success():
    m = MagicMock(); m.status_code = 200; m.json.return_value = {"ok": True}
    with patch.object(_pc.requests, "post", return_value=m):
        result = _pc.post_to_telegram("Hello", "token123")
    assert result is True


def test_post_to_telegram_failure():
    m = MagicMock(); m.status_code = 400
    m.json.return_value = {"ok": False}; m.text = "err"
    with patch.object(_pc.requests, "post", return_value=m):
        result = _pc.post_to_telegram("Hello", "token123")
    assert result is False


def test_post_to_telegram_network_error():
    import requests as _req
    with patch.object(_pc.requests, "post", side_effect=_req.RequestException("x")):
        result = _pc.post_to_telegram("Hello", "token123")
    assert result is False


def test_post_to_telegram_long_message():
    # Build message > 4096 chars with paragraph breaks so it splits
    para = "A" * 2000
    long_msg = f"{para}\n\n{para}\n\n{para}"
    m = MagicMock(); m.status_code = 200; m.json.return_value = {"ok": True}
    with patch.object(_pc.requests, "post", return_value=m) as mp:
        _pc.post_to_telegram(long_msg, "token")
    assert mp.call_count >= 2  # split into multiple chunks


def test_main_no_changelog(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    missing = tmp_path / "CHANGELOG.md"  # does not exist
    with patch.object(_pc, "Path", return_value=missing):
        # Path(__file__) returns missing → .parent.parent / "CHANGELOG.md" won't exist
        # Just use the direct approach: patch changelog_path inside main
        pass
    # Simpler: patch read_latest_entry to return empty
    with patch.object(_pc, "read_latest_entry", return_value=("", "")):
        with patch.object(Path, "exists", return_value=True):
            result = _pc.main()
    assert result == 0


def test_main_success(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    m = MagicMock(); m.status_code = 200; m.json.return_value = {"ok": True}
    with patch.object(_pc, "read_latest_entry", return_value=("## [1.0.0] - 2026-03-01", "Changes")):
        with patch.object(Path, "exists", return_value=True):
            with patch.object(_pc.requests, "post", return_value=m):
                result = _pc.main()
    assert result == 0


def test_main_post_failure(monkeypatch, capsys):
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "tok")
    m = MagicMock(); m.status_code = 400
    m.json.return_value = {"ok": False}; m.text = "err"
    with patch.object(_pc, "read_latest_entry", return_value=("## [1.0.0]", "Body")):
        with patch.object(Path, "exists", return_value=True):
            with patch.object(_pc.requests, "post", return_value=m):
                result = _pc.main()
    assert result == 1
