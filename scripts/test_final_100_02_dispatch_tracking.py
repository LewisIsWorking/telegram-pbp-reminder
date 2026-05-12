"""Tests extracted from test_final_100.py — bin 2.

Sections in this file:
  - dispatch/tracking.py: GM reply logging
  - dispatch/cmd_player.py: /available
"""
"""
Final push: tests for the large remaining uncovered blocks.
Focuses on router poll/callback/reaction handling, tracking GM-reply logging,
cmd_player /available, summary content, and other high-impact gaps.
"""
import sys, os, json, pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))

def _pc(**kw):
    base = {"user_id": "U1", "user_name": "Alice", "gm_ids": set(),
            "pid": "100", "group_id": -1, "thread_id": 999,
            "state": {}, "config": {}, "campaign_name": "Kibwe",
            "now_iso": "2026-04-03T12:00:00+00:00",
            "msg_time_iso": "2026-04-03T12:00:00+00:00",
            "parsed": {"raw_text": ""}, "maps": MagicMock(), "reply_topic": 999}
    base.update(kw)
    base["cmd_word"] = base["text"].split()[0]
    return base

def _info_ctx(cmd, state=None):
    return {"cmd_word": cmd, "text": cmd,
            "user_id": "GM1", "user_name": "L", "gm_ids": {"GM1"},
            "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
            "state": state or {"vote": {}, "timer": {}, "clocks": {},
                               "player_boons": {}},
            "config": {"group_id": -1, "gm_user_ids": [], "topic_pairs": []},
            "campaign_name": "Kibwe", "now_iso": "2026-04-03T12:00:00+00:00",
            "msg_time_iso": "2026-04-03T12:00:00+00:00",
            "parsed": {}, "maps": MagicMock()}

# ─── dispatch/tracking.py: GM reply logging ──────────────────────────────────

def test_tracking_gm_reply_logs(tmp_path, monkeypatch):
    from dispatch.tracking import track_message
    from commands import queue_io
    monkeypatch.setattr(queue_io, "_QUEUES_DIR", tmp_path)
    cq = {"unreplied": [{"message_id": 42, "time": "2026-03-01 10:00:00",
                          "user_name": "Alice", "preview": "hi"}],
          "replied": [], "reply_log": []}
    (tmp_path / "100.json").write_text(json.dumps(cq))
    now = datetime.now(timezone.utc)
    maps = MagicMock()
    maps.to_chat = {"100": 21514}
    maps.to_name = {"100": "Kibwe"}
    parsed = {
        "user_id": "GM1", "username": "lewis", "first_name": "Lewis",
        "user_name": "Lewis", "user_last_name": "", "campaign_name": "Kibwe",
        "pid": "100", "is_gm": True, "thread_id": "100",
        "text": "Sure!", "raw_text": "Sure!",
        "msg_time_iso": now.isoformat(), "message_id": 99,
        "reply_to_message_id": 42,
    }
    state = {
        "topics": {}, "warned_absent": {}, "players": {},
        "message_counts": {}, "post_timestamps": {}, "removed_players": {},
    }
    config = {"group_id": -1001, "gm_user_ids": ["GM1"], "bot_topic_id": 999}
    with patch("dispatch.tracking.helpers") as mh:
        mh.hours_since.return_value = 2.0
        mh.character_name.return_value = ""
        mh.COMEBACK_THRESHOLD_HOURS = 96
        mh.player_mention.return_value = "@lewis"
        track_message(parsed, state, config, {"GM1"}, maps)


def test_tracking_removed_player_rejoins():
    from dispatch.tracking import track_message
    now = datetime.now(timezone.utc)
    maps = MagicMock()
    maps.to_chat = {"100": 21514}
    parsed = {
        "user_id": "U1", "username": "alice", "first_name": "Alice",
        "user_name": "Alice", "user_last_name": "", "campaign_name": "Kibwe",
        "pid": "100", "is_gm": False, "thread_id": "100",
        "text": "Hi!", "raw_text": "Hi!",
        "msg_time_iso": now.isoformat(), "message_id": 42,
    }
    state = {
        "topics": {}, "warned_absent": {},
        "removed_players": {"100:U1": {"username": "alice", "first_name": "Alice",
                                        "removed_at": "2026-01-01"}},
        "players": {}, "message_counts": {}, "post_timestamps": {},
    }
    config = {"group_id": -1001, "gm_user_ids": [999], "bot_topic_id": 999}
    with patch("dispatch.tracking.helpers") as mh:
        mh.hours_since.return_value = 5.0
        mh.character_name.return_value = ""
        mh.COMEBACK_THRESHOLD_HOURS = 96
        mh.player_mention.return_value = "@alice"
        track_message(parsed, state, config, {"999"}, maps)
    assert "100:U1" not in state.get("removed_players", {})



# ─── dispatch/cmd_player.py: /available ──────────────────────────────────────

def _pc(**kw):
    base = {"user_id": "U1", "user_name": "Alice", "gm_ids": set(),
            "pid": "100", "group_id": -1, "thread_id": 999,
            "state": {}, "config": {}, "campaign_name": "Kibwe",
            "now_iso": "2026-04-03T12:00:00+00:00",
            "msg_time_iso": "2026-04-03T12:00:00+00:00",
            "parsed": {"raw_text": ""}, "maps": MagicMock(), "reply_topic": 999}
    base.update(kw)
    base["cmd_word"] = base["text"].split()[0]
    return base


def test_available_show_empty():
    from dispatch.cmd_player import handle
    ctx = _pc(text="/available", parsed={"raw_text": "/available"}, state={"availability": {}})
    assert handle(ctx) is True


def test_available_show_with_data():
    from dispatch.cmd_player import handle
    ctx = _pc(text="/available show", parsed={"raw_text": "/available show"},
              state={"availability": {"100": {"U1": {"name": "Alice", "days": ["mon"]}}}})
    assert handle(ctx) is True


def test_available_clear():
    from dispatch.cmd_player import handle
    ctx = _pc(text="/available clear", parsed={"raw_text": "/available clear"},
              state={"availability": {"100": {"U1": {"name": "Alice", "days": ["mon"]}}}})
    assert handle(ctx) is True


def test_available_set_days():
    from dispatch.cmd_player import handle
    ctx = _pc(text="/available mon wed", parsed={"raw_text": "/available mon wed"},
              state={"availability": {}})
    assert handle(ctx) is True
    assert "mon" in ctx["state"]["availability"]["100"]["U1"]["days"]


def test_available_invalid():
    from dispatch.cmd_player import handle
    ctx = _pc(text="/available notaday", parsed={"raw_text": "/available notaday"},
              state={"availability": {}})
    assert handle(ctx) is True


def test_back_already_back():
    from dispatch.cmd_player import handle
    ctx = _pc(text="/back", parsed={"raw_text": "/back"}, state={"away": {}})
    assert handle(ctx) is True


# test_chooseboon_executes REMOVED 2026-05-11. The /chooseboon
# command handler in dispatch/cmd_player.py was removed when
# user-facing boon selection moved to the website. See L22 in
# REFACTOR_PROGRESS.md.

