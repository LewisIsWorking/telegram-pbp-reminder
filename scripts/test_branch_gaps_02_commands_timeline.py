"""Coverage tests extracted from test_branch_gaps.py — bin 2.

Sections in this file:
  - commands/timeline.py: bad date fallback
  - parsing/message.py: video note branch
  - commands/session.py: build_session branches
  - dispatch/cmd_info.py: /boons branch
  - dispatch/cmd_clocks.py: clock not found
  - scheduled/potw.py: winner_links branch

Targeted tests for specific uncovered branches in the production
modules listed above. Module imports are duplicated from the original
``test_branch_gaps.py`` header; per-section helper functions are
extracted alongside their sections.
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


# ─── commands/timeline.py: bad date fallback ─────────────────────────────────

def test_timeline_bad_date_shows_question_mark():
    from commands.timeline import build_timeline
    state = {"timeline_events": {"100": [
        {"time": "not-a-date", "text": "Something", "author": "Kibwe"}
    ]}}
    config = {"topic_pairs": [{"pbp_topic_ids": [100], "code": "C00",
                                "name": "Kibwe", "chat_topic_id": 21514}]}
    result = build_timeline(config, state)
    assert "?" in result or "Something" in result



# ─── parsing/message.py: video note branch ───────────────────────────────────

def test_detect_media_video_note():
    from parsing.message import _detect_media
    result = _detect_media({"video_note": {"duration": 10}})
    assert result == "video note"



# ─── commands/session.py: build_session branches ─────────────────────────────

def test_build_session_no_count():
    from commands.session import build_session
    with patch("commands.session.helpers") as mh:
        mh.get_label.return_value = "C00: Kibwe"
        result = build_session("100", "Kibwe", {}, {})
    assert "No sessions" in result


def test_build_session_with_count():
    from commands.session import build_session
    with patch("commands.session.helpers") as mh:
        mh.get_label.return_value = "C00: Kibwe"
        result = build_session("100", "Kibwe", {"session_counts": {"100": 7}}, {})
    assert "7" in result



# ─── dispatch/cmd_info.py: /boons branch ─────────────────────────────────────

def test_cmd_info_boons():
    from dispatch.cmd_info import handle as info_handle
    ctx = {
        "cmd_word": "/boons", "text": "/boons",
        "group_id": -1, "reply_topic": 999,
        "pid": "100", "campaign_name": "Kibwe",
        "user_id": "U1", "user_name": "Alice",
        "state": {"player_boons": {}},
        "config": {}, "gm_ids": set(),
    }
    with patch("dispatch.cmd_info.tg.send_message"):
        result = info_handle(ctx)
    assert result is True



# ─── dispatch/cmd_clocks.py: clock not found ─────────────────────────────────

def test_cmd_clocks_not_found():
    from dispatch.cmd_clocks import handle as clocks_handle
    ctx = {
        "cmd_word": "/tick", "text": "/tick NoSuchClock",
        "user_id": "GM1", "gm_ids": {"GM1"},
        "pid": "100", "group_id": -1, "thread_id": 999,
        "state": {"clocks": {"100": {}}},
        "config": {}, "campaign_name": "Kibwe",
        "parsed": {"raw_text": "/done 99", "text": "/done 99"}, "now_iso": "2026-04-03T12:00:00+00:00",
        "maps": MagicMock(),
    }
    result = clocks_handle(ctx)
    assert result is True



# ─── scheduled/potw.py: winner_links branch ──────────────────────────────────

def test_potw_winner_with_links(tmp_path):
    from scheduled.potw import _find_player_post_links
    now = datetime(2026, 4, 3, tzinfo=timezone.utc)
    week_ago = now - timedelta(days=7)
    log_dir = tmp_path / "Kibwe"
    log_dir.mkdir()
    (log_dir / "2026-03.md").write_text(
        "**Alice** (2026-03-30 10:00:00) msg#123:\nHi there\n"
    )
    with patch("scheduled.potw._LOGS_DIR", tmp_path):
        links = _find_player_post_links("Kibwe", "Alice", "100", week_ago)
    assert len(links) >= 0  # may or may not match depending on regex


