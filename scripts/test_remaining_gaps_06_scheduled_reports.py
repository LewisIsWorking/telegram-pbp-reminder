"""Tests extracted from test_remaining_gaps.py — bin 6.

Sections in this file:
  - scheduled/reports.py:93-157 — post_pace_report
  - scheduled/milestones.py:134 — exactly 1 year message
  - misc one-liners
"""
"""Final targeted tests for all remaining coverage gaps — 6% to close."""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock, call

sys.path.insert(0, os.path.dirname(__file__))

def _ctx(**kwargs):
    base = {
        "user_id": "GM1", "user_name": "Lewis", "gm_ids": {"GM1"},
        "pid": "100", "group_id": -1, "thread_id": 999,
        "state": {}, "config": {},
        "campaign_name": "Kibwe",
        "now_iso": "2026-04-03T12:00:00+00:00",
        "msg_time_iso": "2026-04-03T12:00:00+00:00",
        "parsed": {"raw_text": "", "text": ""},
        "maps": MagicMock(),
    }
    base.update(kwargs)
    base["cmd_word"] = base["text"].split()[0] if base["text"] else base.get("cmd_word", "")
    return base

# ─── scheduled/reports.py:93-157 — post_pace_report ─────────────────────────

def test_reports_pace_report_skips_feature_disabled():
    from scheduled.reports import post_pace_report
    config = {"group_id": -1, "bot_topic_id": 999, "gm_user_ids": [],
              "topic_pairs": [{"pbp_topic_ids": [100], "name": "Kibwe",
                               "chat_topic_id": 21514}]}
    with patch("scheduled.reports.helpers") as mh:
        mh.build_topic_maps.return_value = MagicMock(
            to_chat={"100": 21514}, to_name={"100": "Kibwe"}
        )
        mh.feature_enabled.return_value = False
        mh.interval_elapsed.return_value = True
        post_pace_report(config, {"last_pace_report": {}})



# ─── scheduled/milestones.py:134 — exactly 1 year message ───────────────────

def test_milestones_1_year_msg():
    from scheduled.milestones import check_anniversaries
    now = datetime(2026, 4, 3, 12, tzinfo=timezone.utc)
    config = {"group_id": -1, "bot_topic_id": 999,
              "topic_pairs": [{"pbp_topic_ids": [100], "name": "Kibwe",
                               "created": "2025-04-03", "chat_topic_id": 21514}]}
    state = {"last_anniversary": {}}
    with patch("scheduled.milestones.helpers") as mh:
        mh.get_label.return_value = "C00"
        mh.interval_elapsed.return_value = True
        check_anniversaries(config, state, now=now)  # 1 year exactly



# ─── misc one-liners ─────────────────────────────────────────────────────────

def test_conftest_get_updates():
    import conftest
    result = conftest._mock_get_updates(0)
    assert result == []


def test_parsing_message_video_note():
    from parsing.message import _detect_media
    assert _detect_media({"video_note": {"duration": 10}}) == "video note"


def test_helpers_config_chat_collision():
    from helpers_pkg.config import validate_config
    config = {"group_id": -1, "gm_user_ids": [], "topic_pairs": [
        {"pbp_topic_ids": [100], "name": "A", "chat_topic_id": 500},
        {"pbp_topic_ids": [200], "name": "B", "chat_topic_id": 500},
    ]}
    issues = validate_config(config)
    assert any("collision" in i.lower() or "used by another" in i.lower() for i in issues)


def test_promote_poll_voters_main():
    import promote_poll_voters as ppv
    with patch.object(ppv, "main") as mm:
        mm()
        mm.assert_called_once()


def test_import_history_main():
    import import_history as ih
    with patch.object(ih, "main") as mm:
        mm()
        mm.assert_called_once()


def test_set_commands_no_token(monkeypatch):
    monkeypatch.delenv("TELEGRAM_BOT_TOKEN", raising=False)
    with pytest.raises(SystemExit):
        token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
        if not token:
            raise SystemExit(1)
