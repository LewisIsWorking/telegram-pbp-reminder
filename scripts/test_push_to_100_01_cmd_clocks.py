"""Tests extracted from test_push_to_100.py — bin 1.

Sections in this file:
  - cmd_clocks.py
"""
"""Tests for the 4 largest remaining coverage gaps."""
import sys, os
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(__file__))


def _ctx(cmd, text, state, config=None, **kw):
    base = {
        "user_id": "GM1", "user_name": "Lewis", "gm_ids": {"GM1"},
        "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
        "state": state,
        "config": config or {"group_id": -1, "gm_user_ids": [], "topic_pairs": []},
        "campaign_name": "Kibwe", "now_iso": "2026-04-03T12:00:00+00:00",
        "msg_time_iso": "2026-04-03T12:00:00+00:00",
        "parsed": {"raw_text": text}, "maps": MagicMock(),
        "cmd_word": cmd, "text": text,
    }
    base.update(kw)
    return base

def _ic(cmd, state=None):
    return {"user_id": "GM1", "user_name": "Lewis", "gm_ids": {"GM1"},
            "pid": "100", "group_id": -1, "thread_id": 999, "reply_topic": 999,
            "state": state or {}, "campaign_name": "Kibwe",
            "config": {"group_id": -1, "gm_user_ids": [], "topic_pairs": []},
            "now_iso": "2026-04-03T12:00:00+00:00", "msg_time_iso": "2026-04-03T12:00:00+00:00",
            "parsed": {}, "maps": MagicMock(), "cmd_word": cmd, "text": cmd}

def _status(state_extras=None):
    s = {"topics": {}, "post_timestamps": {}, "message_counts": {},
         "players": {}, "paused_campaigns": {}, "current_scenes": {}}
    if state_extras:
        s.update(state_extras)
    return s

def _run_status(state, gm_ids=None, hours=1.0):
    from commands.status import build_status
    with patch("commands.status.helpers") as mh:
        mh.get_label.return_value = "C00"
        mh.get_topic_timestamps.return_value = {}
        mh.hours_since.return_value = hours
        mh.get_characters.return_value = {}
        mh.player_full_name.return_value = "A"
        mh.players_by_campaign.return_value = {}
        mh.pace_split.return_value = {"gm_this": 0, "player_this": 0,
                                       "gm_last": 0, "player_last": 0}
        mh.trend_icon.return_value = "➡️"
        mh.posts_str.return_value = "0"
        return build_status("100", "Kibwe", state, gm_ids or set(), {})

# ── cmd_clocks.py ─────────────────────────────────────────────────────────────

def test_clock_create_no_args():
    from dispatch.cmd_clocks import handle
    assert handle(_ctx("/clock", "/clock", {"clocks": {}})) is True


def test_clock_create_bad_segments():
    from dispatch.cmd_clocks import handle
    ctx = _ctx("/clock", "/clock Investigation 15",
               {"clocks": {}}, parsed={"raw_text": "/clock Investigation 15"})
    assert handle(ctx) is True


def test_clock_create_segments_not_int():
    from dispatch.cmd_clocks import handle
    ctx = _ctx("/clock", "/clock Investigation bad",
               {"clocks": {}}, parsed={"raw_text": "/clock Investigation bad"})
    assert handle(ctx) is True


def test_clock_create_name_only():
    from dispatch.cmd_clocks import handle
    ctx = _ctx("/clock", "/clock Investigation",
               {"clocks": {}}, parsed={"raw_text": "/clock Investigation"})
    assert handle(ctx) is True


def test_clock_tick_not_found():
    from dispatch.cmd_clocks import handle
    ctx = _ctx("/tick", "/tick Ghost",
               {"clocks": {"100": {"Real": {"filled": 1, "segments": 6}}}},
               parsed={"raw_text": "/tick Ghost"})
    assert handle(ctx) is True


def test_clock_tick_with_amount():
    from dispatch.cmd_clocks import handle
    ctx = _ctx("/tick", "/tick Investigation 2",
               {"clocks": {"100": {"Investigation": {"filled": 1, "segments": 6,
                                                      "label": "Investigation"}}}},
               parsed={"raw_text": "/tick Investigation 2"})
    assert handle(ctx) is True


def test_clock_tick_amount_not_int():
    from dispatch.cmd_clocks import handle
    ctx = _ctx("/tick", "/tick Investigation lots",
               {"clocks": {"100": {"Investigation": {"filled": 1, "segments": 6,
                                                      "label": "Investigation"}}}},
               parsed={"raw_text": "/tick Investigation lots"})
    assert handle(ctx) is True


def test_clock_untick_not_found():
    from dispatch.cmd_clocks import handle
    ctx = _ctx("/untick", "/untick Ghost",
               {"clocks": {"100": {}}}, parsed={"raw_text": "/untick Ghost"})
    assert handle(ctx) is True


def test_clock_delclock_not_found():
    from dispatch.cmd_clocks import handle
    ctx = _ctx("/delclock", "/delclock Ghost",
               {"clocks": {"100": {}}}, parsed={"raw_text": "/delclock Ghost"})
    assert handle(ctx) is True

